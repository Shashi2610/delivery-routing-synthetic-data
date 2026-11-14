import argparse
from pathlib import Path

from generator.anomalies import inject_anomalies
from generator.config import DEFAULT_SEED, SCALES
from generator.export import export_dataset
from generator.master_data import (
    build_drivers,
    build_shifts,
    build_sites,
    build_vehicle_capacity,
    build_vehicles,
)
from generator.rng import make_rng
from generator.routing import plan_routes
from generator.simulation import count_late_deliveries, simulate_execution
from generator.transactions import (
    build_orders_and_deliveries,
    build_status_events,
    build_time_windows,
)
from generator.travel import build_traffic_scenarios, build_travel_time_matrix


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the synthetic delivery-routing dataset.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--scale", choices=sorted(SCALES), default="starter")
    parser.add_argument("--no-anomalies", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent)
    return parser.parse_args()


def build_tables(rng, sizes):
    sites = build_sites(rng, sizes["sites"])
    vehicles = build_vehicles(rng, sites, sizes["vehicles"])
    capacities = build_vehicle_capacity(rng, vehicles)
    drivers = build_drivers(rng, sites, vehicles, sizes["drivers"])
    shifts = build_shifts(rng, drivers, vehicles, sizes["days"], sizes["availability"])
    travel_matrix = build_travel_time_matrix(sites)
    scenarios = build_traffic_scenarios(rng, sizes["days"])
    orders, deliveries = build_orders_and_deliveries(rng, sites, sizes["deliveries"], sizes["days"])
    windows = build_time_windows(rng, deliveries, orders, sites)
    status_events = build_status_events(rng, deliveries, orders)
    tables = {
        "customer_site": sites,
        "vehicle": vehicles,
        "vehicle_capacity": capacities,
        "driver": drivers,
        "shift": shifts,
        "travel_time_matrix": travel_matrix,
        "traffic_scenario": scenarios,
        "order": orders,
        "delivery": deliveries,
        "time_window": windows,
        "delivery_status_event": status_events,
    }
    tables.update(plan_routes(tables))
    tables.update(simulate_execution(rng, tables))
    return tables


def print_row_counts(tables):
    for name, table in tables.items():
        print(f"{name}: {len(table)}")


def print_assignment_counts(status_events):
    unserved = status_events[status_events["status"] == "unserved"]
    print(f"assigned: {(status_events['status'] == 'assigned').sum()}")
    print(f"unserved: {len(unserved)}")
    for reason, count in unserved["reason_code"].value_counts().sort_index().items():
        print(f"unserved {reason}: {count}")


def print_outcome_counts(outcomes, windows):
    for status, count in outcomes["status"].value_counts().sort_index().items():
        print(f"outcome {status}: {count}")
    print(f"outcome delivered late: {count_late_deliveries(outcomes, windows)}")
    for reason, count in outcomes["reason_code"].value_counts().sort_index().items():
        print(f"outcome failed {reason}: {count}")


def print_anomaly_counts(ground_truth):
    for issue_type, count in ground_truth.groupby("issue_type")["anomaly_id"].nunique().items():
        print(f"anomaly {issue_type}: {count}")


def main():
    args = parse_args()
    rng = make_rng(args.seed)
    clean_tables = build_tables(rng, SCALES[args.scale])
    if args.no_anomalies:
        tables, ground_truth = clean_tables, None
    else:
        tables, ground_truth = inject_anomalies(rng, clean_tables)
    export_dataset(tables, ground_truth, args.output_dir, args.seed, args.scale)
    print_row_counts(tables)
    print_assignment_counts(clean_tables["delivery_status_event"])
    print_outcome_counts(clean_tables["delivery_outcome"], clean_tables["time_window"])
    if ground_truth is not None:
        print_anomaly_counts(ground_truth)


if __name__ == "__main__":
    main()
