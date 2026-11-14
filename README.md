# Delivery Routing Synthetic Data

## Business problem

A delivery operation has to plan routes: each customer order must reach a site inside a time window, each vehicle has weight, volume and unit limits, and each driver works a fixed shift with a driving limit. This project generates a synthetic dataset for that problem: the plan (routes and stops), what happened when the plan was executed (outcomes), and a set of injected errors with labels.

The data is intended for:
- **Planners**, to check whether a plan respects capacity, windows and shifts.
- **Analysts**, to measure service level and to test data-quality and anomaly detection against known labels.
- **Operations managers**, to look at on-time delivery, failure reasons and vehicle and shift utilisation.

## Quick start

Tested on Windows with PowerShell, Python 3.14.3, pandas 3.1.1 and numpy 2.5.4. Run every command from the repository root.

**1. Get the code**

```
git clone <repository-url>
cd delivery-routing-synthetic-data
```

**2. Create the environment and install the requirements**

```
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and activate again. Or skip the activation and start each command below with `.venv\Scripts\` (for example `.venv\Scripts\python generate.py`).

**3. Generate the dataset (about 2 seconds)**

```
python generate.py --seed 20261022 --scale starter
```

The data files are not stored in the repository, so run this step first. The next steps read its output. It prints the row count of each of the 14 tables (from `customer_site: 55` to `delivery_outcome: 105`), then the assigned, unserved and outcome counts and five `anomaly ...: 3` lines.

**4. Validate (about 2 seconds)**

```
python validate.py
```

```
structural checks: 115/115 passed
ROUTE_CAPACITY_EXCEEDED: detections 3, recall 100.0%, precision 100.0%
STOP_OMITTED_OR_DUPLICATED: detections 3, recall 100.0%, precision 100.0%
ARRIVAL_BEFORE_PREVIOUS_DEPARTURE: detections 3, recall 100.0%, precision 100.0%
DRIVER_SHIFT_EXCEEDED: detections 3, recall 100.0%, precision 100.0%
COORDINATE_OUTSIDE_REGION: detections 3, recall 100.0%, precision 100.0%
result: PASS
```

This writes `validation_report.md`.

**5. Metrics (about 1 second)**

```
python scripts/metrics.py
```

```
deliveries: 200, assigned: 107, unserved: 93
attempted: 105, on time: 98, late: 0, failed: 7
on-time % of attempted: 93.3%
service rate: 53.5%
mean weight utilisation: 49.3%, mean volume utilisation: 53.9%
average lateness of late deliveries: n/a minutes
```

This writes `docs/metrics_report.md`.

**6. Reproducibility check (about 7 seconds)**

```
python scripts/check_reproducibility.py --scale starter
```

```
same seed, 32 files: all identical
different seed: checksums changed as expected
manifest checksums match files: True
result: PASS
```

This writes `docs/reproducibility_report.md`.

**Full dataset (optional)**

The full dataset (2000 deliveries) takes about 7 seconds to generate and is about 61 MB, so write it to a separate folder:

```
python generate.py --seed 20261022 --scale full --output-dir <folder>
python validate.py --data-dir <folder>\data --ground-truth <folder>\ground_truth\ground_truth.csv
python scripts/metrics.py --data-dir <folder>\data
```

Add `--no-anomalies` to `generate.py` for a clean dataset without ground truth. Use `--seed <number>` for a different dataset.

## What the project produces

Row counts with anomalies injected (the default), for seed 20261022:

| Table | Starter | Full |
|---|---|---|
| customer_site | 55 | 505 |
| vehicle | 10 | 100 |
| vehicle_capacity | 10 | 100 |
| driver | 12 | 120 |
| shift | 30 | 1068 |
| travel_time_matrix | 2970 | 254520 |
| traffic_scenario | 15 | 150 |
| order | 180 | 1800 |
| delivery | 200 | 2000 |
| time_window | 200 | 2000 |
| delivery_status_event | 614 | 7800 |
| route | 29 | 629 |
| route_stop | 106 | 1899 |
| delivery_outcome | 105 | 1871 |

Outputs of `generate.py`:

| Output | Location |
|---|---|
| One CSV per table (created by step 3, not stored in the repository) | `data/*.csv` |
| The same tables as JSON records | `data/json/*.json` |
| Manifest with seed, scale, command, row counts and SHA-256 of every file | `data/manifest.json` |
| SQL schema and seed statements (generated, not loaded by the pipeline) | `sql/schema.sql`, `sql/seed.sql` |
| Labels for the injected anomalies (23 rows starter, 219 rows full) | `ground_truth/ground_truth.csv` |

Reports written by the other scripts: `validation_report.md`, `docs/metrics_report.md`, `docs/reproducibility_report.md`.

## Repository structure

```
generate.py          entry point: builds all tables and writes the outputs
validate.py          structural checks, anomaly detectors and scoring
app.py               optional Streamlit page for the results (needs requirements-ui.txt)
requirements.txt     pandas and numpy
generator/           config, ids, seeded rng, master_data, transactions, travel, routing,
                     simulation, anomalies, schema, export
scripts/             check_reproducibility.py and metrics.py
docs/                data dictionary, ER diagram, metrics and reproducibility reports
data/                generated CSV and JSON files and the manifest
sql/                 generated schema.sql and seed.sql
ground_truth/        generated anomaly labels, kept apart from the input tables
ai_prompts/          log of the prompts used
tests/               empty
```

## Optional: web UI

`app.py` is a Streamlit page for browsing the results. It reads the files in `data/` (run step 3 first) and needs one extra package (tested with Streamlit 1.67.0). The generator, validator and scripts do not need it.

```
pip install -r requirements-ui.txt
streamlit run app.py
```

Tabs: Overview (manifest, seed, command, files), Data (browse any table), Metrics (the numbers from `scripts/metrics.py` with charts), Validation (structural checks, rule detectors and scoring against the ground truth) and Reproducibility (the report and a button that runs the check). The sidebar has a Generate button that replaces the files in `data/`, `sql/` and `ground_truth/` with a new dataset.

## Data model

Full field lists, enums, ID formats, lifecycle rules and anomaly rules are in [docs/data_dictionary.md](docs/data_dictionary.md). The entity-relationship diagram is in [docs/er_diagram.md](docs/er_diagram.md).

Key relationships:

| Relationship | Cardinality |
|---|---|
| CustomerSite (hub) to CustomerSite (customer), through `hub_id` | 1:N |
| CustomerSite to Order | 1:N |
| Order to Delivery | 1:N (split shipments) |
| Delivery to TimeWindow | 1:1 |
| Delivery to DeliveryStatusEvent | 1:N (append-only history) |
| Vehicle to VehicleCapacity | 1:N (dated rows) |
| Driver to Vehicle, through Shift | N:M |
| Shift to Route | 1:N |
| Route to RouteStop | 1:N, ordered by `sequence_no` |
| Delivery to Route, through RouteStop | N:M |
| RouteStop to DeliveryOutcome | 1:0..1 |
| Delivery to DeliveryOutcome | 1:N (one row per attempt) |
| CustomerSite to CustomerSite, through TravelTimeMatrix | N:M |

A hub is a CustomerSite row and acts as the depot. A route's hub must equal its vehicle's home hub, and a delivery is only served by vehicles from its site's hub.

## Pipeline order

1. **Master data** (`generator/master_data.py`, `generator/travel.py`): sites clustered around five hubs, vehicles, capacities, drivers and daily shifts (at full scale not every vehicle works every day), then the static travel matrix and the traffic scenarios.
2. **Transactions** (`generator/transactions.py`): orders, deliveries, time windows and the initial `planned` status event.
3. **Routing** (`generator/routing.py`): a greedy planner, per day and per hub, that adds the feasible delivery with the lowest extra travel time to each shift; deliveries that do not fit become `unserved` with a reason code.
4. **Simulation** (`generator/simulation.py`): executes the routes with seeded noise on travel and service times and applies the outcome rules (shift, site closed, late) to write one outcome per stop.
5. **Anomalies** (`generator/anomalies.py`): injects five labelled error types into the finished tables and writes the labels to `ground_truth/`.
6. **Export** (`generator/export.py`): writes CSV, JSON, SQL and the manifest, with rows sorted by primary key.

## Validation summary

`python validate.py` runs 115 structural checks and five rule detectors, and writes `validation_report.md`. The detectors never read `ground_truth/`; it is used only afterwards to score them.

Result on the starter dataset (the report in the repository): all 115 structural checks pass.

| Issue type | Injected | Detected | Recall | Precision |
|---|---|---|---|---|
| ROUTE_CAPACITY_EXCEEDED | 3 | 3 | 100.0% | 100.0% |
| STOP_OMITTED_OR_DUPLICATED | 3 | 3 | 100.0% | 100.0% |
| ARRIVAL_BEFORE_PREVIOUS_DEPARTURE | 3 | 3 | 100.0% | 100.0% |
| DRIVER_SHIFT_EXCEEDED | 3 | 3 | 100.0% | 100.0% |
| COORDINATE_OUTSIDE_REGION | 3 | 3 | 100.0% | 100.0% |

On the full dataset the same command also passes all 115 structural checks and detects 152 anomalies (19, 57, 37, 19 and 20 per type in the order above) with 100% recall and precision. The report lists the checks that are not implemented.

## Reproducibility

Seed: 20261022 (the default). `python scripts/check_reproducibility.py` runs the generator twice with the same seed and once with seed 20261023, then compares SHA-256 checksums and row counts of every output file.

Result at both starter and full scale: PASS. The 32 output files are identical across the two runs with the same seed, every checksum listed in `data/manifest.json` matches its file, and the other seed changes every file except `sql/schema.sql`. Details per file are in [docs/reproducibility_report.md](docs/reproducibility_report.md). Exact random values can differ between numpy versions, so compare checksums only within one environment.

## Metrics

Headline numbers from `python scripts/metrics.py`, computed from the CSV files (starter is the report in the repository):

| Metric | Starter | Full |
|---|---|---|
| Deliveries | 200 | 2000 |
| Assigned / unserved | 107 / 93 | 1900 / 100 |
| Service rate (assigned / total) | 53.5% | 95.0% |
| Attempted (has an outcome row) | 105 | 1871 |
| Delivered on time / late / failed | 98 / 0 / 7 | 1801 / 6 / 64 |
| On-time % of attempted | 93.3% | 96.3% |
| Average lateness of late deliveries | n/a | 2.5 minutes |
| Mean route weight vs capacity | 49.3% | 42.4% |
| Mean route volume vs capacity | 53.9% | 46.7% |

These numbers include the injected anomalies. Per vehicle per day the starter dataset has about ten times the demand of the full dataset (200 deliveries for 10 vehicles over 3 days against 2000 for 100 vehicles over 30 days), so its service rate is lower. The report has more sections: reasons for failure and for unserved deliveries, shift utilisation, a per-hub breakdown and planned versus actual travel time. Each section has a note on how the anomalies affect it.

## Requirement deviations

Two entities were added to the original 12:

- **DeliveryStatusEvent**: the delivery lifecycle (planned, assigned, unserved, in_transit, delivered, failed) is stored as append-only rows, because a status field on Delivery would be overwritten. This follows the rule that state changes are new rows.
- **TrafficScenario**: a travel matrix with one row per date and hour band would need about 37 million rows at full scale. The matrix is static (about 250,000 rows) and traffic is a separate table of 150 rows, so actual travel time is computed as `base_travel_minutes x traffic_factor`.

Two fields were also added to the dictionary: `reason_code` on DeliveryStatusEvent (an unserved delivery has no stop, so it cannot have an outcome row to hold its reason) and `is_incident` on TrafficScenario (the simulation adds delay on incident days).

## Data provenance

All data is synthetic and generated locally from a seed. No external datasets or APIs are used, and the data contains no personal data: there are no names or contact details, only generated IDs, coordinates and times.

## Data size note

The files generated by `python generate.py` are about 1.2 MB at starter scale and about 61 MB at full scale (CSV 10 MB, JSON 37 MB, SQL 13 MB, ground truth 0.1 MB). The travel matrix is most of that.

The repository holds code, documentation and the reports. The datasets are not committed: `data/*.csv` is git-ignored, and every generated file can be recreated with the commands above. Reviewers who want the full dataset should run `python generate.py --seed 20261022 --scale full`.

