import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from generator.config import DEFAULT_SEED, SCALES  # noqa: E402
from generator.schema import SQL_TABLE_ORDER  # noqa: E402

REQUIRED_SETTINGS = ["MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB"]
DEFAULT_PORT = "3306"
PLACEHOLDER_PREFIX = "your_"
SAMPLE_SIZE = 5
UNAVAILABLE = 2

JOIN_CHECKS = [
    {
        "name": "Order to Delivery",
        "matched": "SELECT COUNT(*) FROM `delivery` d JOIN `order` o ON o.order_id = d.order_id",
        "orphans": (
            "SELECT order_id FROM `order` WHERE order_id NOT IN (SELECT order_id FROM `delivery`) "
            "UNION ALL SELECT delivery_id FROM `delivery` WHERE order_id NOT IN (SELECT order_id FROM `order`)"
        ),
        "expected": "none",
    },
    {
        "name": "Delivery to RouteStop (assigned deliveries without a stop)",
        "matched": "SELECT COUNT(*) FROM `route_stop` s JOIN `delivery` d ON d.delivery_id = s.delivery_id",
        "orphans": (
            "SELECT DISTINCT e.delivery_id FROM `delivery_status_event` e "
            "LEFT JOIN `route_stop` s ON s.delivery_id = e.delivery_id "
            "WHERE e.status = 'assigned' AND s.stop_id IS NULL"
        ),
        "expected": "deleted_stops",
    },
    {
        "name": "Route to Shift and Vehicle",
        "matched": (
            "SELECT COUNT(*) FROM `route` r JOIN `shift` s ON s.shift_id = r.shift_id "
            "JOIN `vehicle` v ON v.vehicle_id = s.vehicle_id"
        ),
        "orphans": (
            "SELECT r.route_id FROM `route` r LEFT JOIN `shift` s ON s.shift_id = r.shift_id "
            "LEFT JOIN `vehicle` v ON v.vehicle_id = s.vehicle_id WHERE v.vehicle_id IS NULL"
        ),
        "expected": "none",
    },
    {
        "name": "RouteStop to DeliveryOutcome (stops without an outcome)",
        "matched": "SELECT COUNT(*) FROM `route_stop` s JOIN `delivery_outcome` o ON o.stop_id = s.stop_id",
        "orphans": (
            "SELECT s.stop_id FROM `route_stop` s LEFT JOIN `delivery_outcome` o ON o.stop_id = s.stop_id "
            "WHERE o.outcome_id IS NULL "
            "UNION ALL SELECT outcome_id FROM `delivery_outcome` "
            "WHERE stop_id NOT IN (SELECT stop_id FROM `route_stop`)"
        ),
        "expected": "added_stops",
    },
]


def stop_unavailable(message):
    print(f"MySQL check skipped: {message}")
    print("The generator, validator, metrics and reproducibility scripts do not need MySQL.")
    sys.exit(UNAVAILABLE)


def load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def read_settings():
    values = {name: os.environ.get(name, "") for name in REQUIRED_SETTINGS}
    unset = [name for name, value in values.items() if not value or value.startswith(PLACEHOLDER_PREFIX)]
    if unset:
        stop_unavailable(f"set {', '.join(unset)} in .env (copy .env.example) or in the environment")
    if not re.fullmatch(r"\w+", values["MYSQL_DB"]):
        stop_unavailable("MYSQL_DB may only contain letters, digits and underscores")
    values["MYSQL_PORT"] = os.environ.get("MYSQL_PORT", DEFAULT_PORT)
    return values


def import_connector():
    try:
        import mysql.connector
    except ImportError:
        stop_unavailable("mysql-connector-python is not installed (pip install -r requirements-mysql.txt)")
    return mysql.connector


def open_connection(connector, settings):
    try:
        connection = connector.connect(
            host=settings["MYSQL_HOST"], port=int(settings["MYSQL_PORT"]), user=settings["MYSQL_USER"],
            password=settings["MYSQL_PASSWORD"], connection_timeout=5,
        )
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{settings['MYSQL_DB']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
        cursor.execute(f"USE `{settings['MYSQL_DB']}`")
    except (connector.Error, ValueError) as error:
        stop_unavailable(f"cannot use MySQL at {settings['MYSQL_HOST']}:{settings['MYSQL_PORT']} ({error})")
    return connection, cursor


def run_generator(seed, scale, anomalies, output_dir):
    command = [sys.executable, str(ROOT / "generate.py"), "--seed", str(seed), "--scale", scale, "--output-dir", str(output_dir)]
    if not anomalies:
        command.append("--no-anomalies")
    subprocess.run(command, check=True, capture_output=True, text=True, cwd=ROOT)


def read_statements(path):
    lines = [line for line in path.read_text(encoding="utf-8").splitlines(keepends=True) if not line.startswith("--")]
    return [statement.strip() for statement in "".join(lines).split(";\n") if statement.strip()]


def drop_tables(cursor):
    for name in reversed(SQL_TABLE_ORDER):
        cursor.execute(f"DROP TABLE IF EXISTS `{name}`")


def load_dataset(connector, connection, cursor, sql_dir):
    try:
        drop_tables(cursor)
        for statement in read_statements(sql_dir / "schema.sql") + read_statements(sql_dir / "seed.sql"):
            cursor.execute(statement)
        connection.commit()
    except connector.Error as error:
        connection.rollback()
        return str(error)
    return None


def table_counts(cursor):
    counts = {}
    for name in SQL_TABLE_ORDER:
        cursor.execute(f"SELECT COUNT(*) FROM `{name}`")
        counts[name] = cursor.fetchone()[0]
    return counts


def manifest_counts(dataset_dir):
    manifest = json.loads((dataset_dir / "data" / "manifest.json").read_text(encoding="utf-8"))
    return {Path(entry["path"]).stem: entry["rows"] for entry in manifest["files"] if entry["path"].endswith(".csv") and entry["path"].startswith("data/") and "/json/" not in entry["path"]}


def expected_orphans(ground_truth_path):
    expected = {"none": 0, "deleted_stops": 0, "added_stops": 0}
    if not ground_truth_path.exists():
        return expected
    labels = pd.read_csv(ground_truth_path)
    stops = labels[labels["table"] == "route_stop"]
    expected["deleted_stops"] = int((stops["injected_value"] == "deleted").sum())
    expected["added_stops"] = int((stops["injected_value"] != "deleted").sum())
    return expected


def run_join_check(cursor, check, expected):
    cursor.execute(check["matched"])
    matched = cursor.fetchone()[0]
    cursor.execute(check["orphans"])
    orphans = [row[0] for row in cursor.fetchall()]
    wanted = expected[check["expected"]]
    return {"name": check["name"], "matched": matched, "orphans": orphans, "expected": wanted, "ok": len(orphans) == wanted}


def foreign_key_checks_on(cursor):
    cursor.execute("SELECT @@foreign_key_checks")
    return bool(cursor.fetchone()[0])


def check_dataset(connector, connection, cursor, label, dataset_dir):
    error = load_dataset(connector, connection, cursor, dataset_dir / "sql")
    result = {"label": label, "load_error": error, "joins": [], "count_mismatches": [], "foreign_keys": foreign_key_checks_on(cursor)}
    if error:
        return result
    counts, wanted = table_counts(cursor), manifest_counts(dataset_dir)
    result["count_mismatches"] = [name for name, rows in wanted.items() if counts.get(name) != rows]
    expected = expected_orphans(dataset_dir / "ground_truth" / "ground_truth.csv")
    result["joins"] = [run_join_check(cursor, check, expected) for check in JOIN_CHECKS]
    result["rows"] = sum(counts.values())
    return result


def dataset_passed(result):
    return (
        result["load_error"] is None and result["foreign_keys"] and not result["count_mismatches"]
        and all(join["ok"] for join in result["joins"])
    )


def print_dataset(result):
    print(f"--- {result['label']} dataset")
    if result["load_error"]:
        print(f"load failed: {result['load_error']}")
        return
    print(f"rows loaded: {result['rows']}, foreign key checks on: {result['foreign_keys']}, tables not matching the manifest: {len(result['count_mismatches'])}")
    for join in result["joins"]:
        status = "ok" if join["ok"] else "UNEXPECTED"
        print(f"{join['name']}: matched {join['matched']}, orphans {len(join['orphans'])}, expected {join['expected']} [{status}]")
        if join["orphans"]:
            print(f"  sample orphans: {', '.join(map(str, join['orphans'][:SAMPLE_SIZE]))}")


def parse_args():
    parser = argparse.ArgumentParser(description="Optional check: load the SQL export into MySQL 8 and run join checks.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--scale", choices=sorted(SCALES), default="starter")
    return parser.parse_args()


def main():
    args = parse_args()
    load_env_file(ROOT / ".env")
    settings = read_settings()
    connector = import_connector()
    connection, cursor = open_connection(connector, settings)
    results = []
    with tempfile.TemporaryDirectory() as folder:
        for label, anomalies in (("clean", False), ("anomalies", True)):
            dataset_dir = Path(folder) / label
            run_generator(args.seed, args.scale, anomalies, dataset_dir)
            results.append(check_dataset(connector, connection, cursor, label, dataset_dir))
            print_dataset(results[-1])
    connection.close()
    passed = all(dataset_passed(result) for result in results)
    print("result: " + ("PASS" if passed else "FAIL"))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
