# Delivery Routing Synthetic Data

Generator for a synthetic delivery-routing dataset with known, injected anomalies. It runs locally with pandas and numpy only, and output is reproducible from a seed.

## Status

Work in progress. Master data is generated: customer sites, vehicles, vehicle capacity, drivers and shifts. Orders, deliveries, time windows, travel times, routes, outcomes, anomaly injection and validation are not built yet.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```
python generate.py --scale starter
python generate.py --scale full --seed 20261022
```

| Option | Default | Description |
|---|---|---|
| --seed | 20261022 | Seed for the single random generator |
| --scale | starter | starter (50 sites, 200 deliveries, 10 vehicles, 3 days) or full (500 sites, 2000 deliveries, 100 vehicles, 30 days) |

CSV files are written to `data/`. The same seed and scale always give the same files.

## Layout

| Path | Purpose |
|---|---|
| generate.py | Entry point |
| validate.py | Placeholder for the validator |
| generator/ | Config, IDs, seeded RNG and table builders |
| data/ | Generated input tables |
| ground_truth/ | Injected-anomaly labels, kept apart from input tables |
| docs/ | Data dictionary and ER diagram |
| tests/ | Tests |

## Documentation

- [Data dictionary](docs/data_dictionary.md): every table, field, enum, ID format and lifecycle rule
- [ER diagram](docs/er_diagram.md): entities and relationships

## Configuration

Copy `.env.example` to `.env` for optional settings. Do not commit `.env`.
