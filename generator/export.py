import hashlib
import json
from pathlib import Path

from generator.schema import (
    BOOLEAN_TYPE,
    COLUMN_ID_KIND,
    COLUMN_TYPES,
    ENUM_VALUES,
    FOREIGN_KEYS,
    ID_LENGTHS,
    OPTIONAL_COLUMNS,
    PRIMARY_KEYS,
    SQL_TABLE_ORDER,
    UNIQUE_CONSTRAINTS,
)

INSERT_BATCH_ROWS = 500
SYNTHETIC_NOTE = "All data in this dataset is synthetic and was generated locally. No external data sources were used."
STATIC_FILES = {"sql/schema.sql"}
TABLE_OPTIONS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin"


def sort_tables(tables):
    return {
        name: table.sort_values(PRIMARY_KEYS[name], kind="stable", ignore_index=True)
        for name, table in tables.items()
    }


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def with_lowercase_booleans(table):
    table = table.copy()
    for column in table.select_dtypes("bool"):
        table[column] = table[column].map({True: "true", False: "false"})
    return table


def csv_text(table):
    return with_lowercase_booleans(table).to_csv(index=False, lineterminator="\n")


def native_frame(table):
    return table.astype(object).where(table.notna(), None)


def json_text(table):
    return json.dumps(native_frame(table).to_dict("records"), indent=2) + "\n"


def quote(name):
    return "`" + name + "`"


def sql_value(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def column_type(table_name, column):
    allowed = ENUM_VALUES.get((table_name, column))
    if allowed:
        return "ENUM(" + ", ".join(sql_value(value) for value in sorted(allowed)) + ")"
    if column in COLUMN_ID_KIND:
        return f"VARCHAR({ID_LENGTHS[COLUMN_ID_KIND[column]]})"
    return COLUMN_TYPES[column]


def column_lines(name, table):
    optional = OPTIONAL_COLUMNS.get(name, set())
    return [
        f"{quote(column)} {column_type(name, column)}" + ("" if column in optional else " NOT NULL")
        for column in table.columns
    ]


def constraint_lines(name, table):
    columns = lambda names: ", ".join(quote(column) for column in names)
    lines = [f"PRIMARY KEY ({columns(PRIMARY_KEYS[name])})"]
    lines += [f"UNIQUE ({columns(cols)})" for owner, cols in UNIQUE_CONSTRAINTS if owner == name]
    lines += [
        f"FOREIGN KEY ({quote(column)}) REFERENCES {quote(parent)} ({quote(parent_column)})"
        for child, column, parent, parent_column in FOREIGN_KEYS if child == name
    ]
    lines += [f"CHECK ({quote(column)} IN (0, 1))" for column in table.columns if column_type(name, column) == BOOLEAN_TYPE]
    return lines


def create_table_sql(name, table):
    body = column_lines(name, table) + constraint_lines(name, table)
    return f"CREATE TABLE {quote(name)} (\n  " + ",\n  ".join(body) + f"\n) {TABLE_OPTIONS};"


def schema_sql(tables):
    header = "-- Synthetic delivery-routing dataset schema for MySQL 8 (InnoDB, utf8mb4).\n\n"
    return header + "\n\n".join(create_table_sql(name, tables[name]) for name in SQL_TABLE_ORDER) + "\n"


def sql_ready_frame(name, table):
    frame = native_frame(table)
    for column in table.columns:
        if column_type(name, column) == "DATETIME":
            frame[column] = frame[column].map(lambda value: value.replace("T", " ") if isinstance(value, str) else value)
    return frame


def insert_statements(name, table):
    rows = list(sql_ready_frame(name, table).itertuples(index=False, name=None))
    columns = ", ".join(quote(column) for column in table.columns)
    for start in range(0, len(rows), INSERT_BATCH_ROWS):
        batch = rows[start:start + INSERT_BATCH_ROWS]
        values = ",\n".join("(" + ", ".join(sql_value(value) for value in row) + ")" for row in batch)
        yield f"INSERT INTO {quote(name)} ({columns}) VALUES\n{values};"


def seed_sql(tables):
    statements = [statement for name in SQL_TABLE_ORDER for statement in insert_statements(name, tables[name])]
    return "START TRANSACTION;\n" + "\n".join(statements) + "\nCOMMIT;\n"


def write_table_files(tables, data_dir):
    files = []
    for name, table in tables.items():
        write_text(data_dir / f"{name}.csv", csv_text(table))
        write_text(data_dir / "json" / f"{name}.json", json_text(table))
        files += [(data_dir / f"{name}.csv", len(table)), (data_dir / "json" / f"{name}.json", len(table))]
    return files


def write_sql_files(tables, sql_dir):
    write_text(sql_dir / "schema.sql", schema_sql(tables))
    write_text(sql_dir / "seed.sql", seed_sql(tables))
    total_rows = sum(len(table) for table in tables.values())
    return [(sql_dir / "schema.sql", None), (sql_dir / "seed.sql", total_rows)]


def write_ground_truth(ground_truth, path):
    if ground_truth is None:
        path.unlink(missing_ok=True)
        return []
    write_text(path, ground_truth.to_csv(index=False, lineterminator="\n"))
    return [(path, len(ground_truth))]


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(root, files, seed, scale, anomalies):
    command = f"python generate.py --seed {seed} --scale {scale}" + ("" if anomalies else " --no-anomalies")
    entries = sorted(
        ({"path": path.relative_to(root).as_posix(), "rows": rows, "sha256": sha256_of(path)} for path, rows in files),
        key=lambda entry: entry["path"],
    )
    return {
        "synthetic": True,
        "note": SYNTHETIC_NOTE,
        "seed": seed,
        "scale": scale,
        "command": command,
        "anomalies_injected": anomalies,
        "files": entries,
    }


def export_dataset(tables, ground_truth, output_dir, seed, scale):
    root = Path(output_dir)
    sorted_tables = sort_tables(tables)
    files = write_table_files(sorted_tables, root / "data")
    files += write_sql_files(sorted_tables, root / "sql")
    files += write_ground_truth(ground_truth, root / "ground_truth" / "ground_truth.csv")
    manifest = build_manifest(root, files, seed, scale, ground_truth is not None)
    write_text(root / "data" / "manifest.json", json.dumps(manifest, indent=2) + "\n")
