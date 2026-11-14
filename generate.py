import argparse
from pathlib import Path

from generator.config import DEFAULT_SEED, SCALES
from generator.master_data import (
    build_drivers,
    build_shifts,
    build_sites,
    build_vehicle_capacity,
    build_vehicles,
)
from generator.rng import make_rng

DATA_DIR = Path(__file__).parent / "data"


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the synthetic delivery-routing dataset.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--scale", choices=sorted(SCALES), default="starter")
    return parser.parse_args()


def build_master_tables(rng, sizes):
    sites = build_sites(rng, sizes["sites"])
    vehicles = build_vehicles(rng, sites, sizes["vehicles"])
    capacities = build_vehicle_capacity(rng, vehicles)
    drivers = build_drivers(rng, sites, vehicles, sizes["drivers"])
    shifts = build_shifts(rng, drivers, vehicles, sizes["days"])
    return {
        "customer_site": sites,
        "vehicle": vehicles,
        "vehicle_capacity": capacities,
        "driver": drivers,
        "shift": shifts,
    }


def with_lowercase_booleans(table):
    table = table.copy()
    for column in table.select_dtypes("bool"):
        table[column] = table[column].map({True: "true", False: "false"})
    return table


def write_tables(tables):
    DATA_DIR.mkdir(exist_ok=True)
    for name, table in tables.items():
        with_lowercase_booleans(table).to_csv(DATA_DIR / f"{name}.csv", index=False)
        print(f"{name}: {len(table)}")


def main():
    args = parse_args()
    rng = make_rng(args.seed)
    write_tables(build_master_tables(rng, SCALES[args.scale]))


if __name__ == "__main__":
    main()
