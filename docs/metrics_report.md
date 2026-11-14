# Metrics report

All numbers are computed from the CSV tables. Each section has a line for your own reading and a note on how the injected anomalies can affect it.

## Definitions

- Attempted: a delivery with an outcome row.
- On time: delivered with actual arrival at or before the window end. Late: delivered after the window end, inside the grace period.
- Route load: weight and volume of the distinct deliveries on a route divided by the vehicle capacity in effect on the route date.
- Route minutes: from route start to the last stop's departure. The return leg to the hub is not included.
- Travel legs: only consecutive stops where the vehicle did not wait for the window to open, so travel time can be read from the times.

## Delivery performance

| Metric | Value |
|---|---|
| Total deliveries | 200 |
| Assigned | 107 |
| Unserved | 93 |
| Assigned + unserved equals total | yes |
| Attempted (has an outcome row) | 105 |
| Delivered on time | 98 |
| Delivered late | 0 |
| Failed | 7 |
| On-time % of attempted | 93.3% |
| Service rate (assigned / total) | 53.5% |

My reading:

Anomaly note: Omitted stops remove an outcome row, so attempted and on-time counts drop while assigned stays the same. Duplicated stops have no outcome and change nothing here. A moved arrival time can turn a late delivery into an on-time one.

## Failures by reason code

| Reason code | Count | Share |
|---|---|---|
| LATE_MISSED_WINDOW | 3 | 42.9% |
| SHIFT_EXCEEDED | 4 | 57.1% |

My reading:

Anomaly note: No anomaly writes a failed outcome or a reason code, so these counts come only from the execution rules. An omitted stop that was a failure would disappear from the table.

## Unserved by reason code

| Reason code | Count | Share |
|---|---|---|
| CAPACITY | 3 | 3.2% |
| LATE_MISSED_WINDOW | 49 | 52.7% |
| SHIFT_EXCEEDED | 13 | 14.0% |
| VEHICLE_RESTRICTED | 28 | 30.1% |

My reading:

Anomaly note: No anomaly writes a failed outcome or a reason code, so these counts come only from the execution rules. An omitted stop that was a failure would disappear from the table.

## Vehicle utilisation: route load vs capacity

| Measure | Routes | Mean | Min | 25th | Median | 75th | Max | Routes above 100% |
|---|---|---|---|---|---|---|---|---|
| Weight vs capacity | 29 | 49.3% | 1.7% | 13.3% | 46.6% | 73.1% | 100.0% | 3 |
| Volume vs capacity | 29 | 53.9% | 4.4% | 21.5% | 57.5% | 84.0% | 95.3% | 0 |

My reading:

Anomaly note: A capacity anomaly pushes route weight above 100% of capacity. A shift anomaly pushes actual shift utilisation above 100%. Duplicated stops are counted once, so they do not change route load.

## Shift utilisation

| Metric | Value |
|---|---|
| Shifts | 30 |
| Shifts with a route | 29 |
| Shifts without a route | 1 (3.3%) |
| Planned route minutes / shift minutes: mean | 75.0% |
| Planned: median | 80.7% |
| Planned: max | 97.5% |
| Planned: routes above 100% | 0 |
| Actual route minutes / shift minutes: mean | 77.4% |
| Actual: median | 80.4% |
| Actual: max | 107.0% |
| Actual: routes above 100% | 3 |

My reading:

Anomaly note: A capacity anomaly pushes route weight above 100% of capacity. A shift anomaly pushes actual shift utilisation above 100%. Duplicated stops are counted once, so they do not change route load.

## Per hub

| Hub | Deliveries | Assigned | Service rate | Attempted | On time | On-time % |
|---|---|---|---|---|---|---|
| SITE-000001 | 62 | 41 | 66.1% | 40 | 36 | 90.0% |
| SITE-000002 | 54 | 31 | 57.4% | 31 | 28 | 90.3% |
| SITE-000003 | 44 | 24 | 54.5% | 23 | 23 | 100.0% |
| SITE-000004 | 26 | 6 | 23.1% | 6 | 6 | 100.0% |
| SITE-000005 | 14 | 5 | 35.7% | 5 | 5 | 100.0% |

My reading:

Anomaly note: Anomalies are spread over all hubs, so a hub with few routes can move by a few points from a single omitted stop or moved arrival time.

## Lateness of late deliveries

| Metric | Value |
|---|---|
| Late deliveries | 0 |
| Share of delivered | 0.0% |
| Average lateness (minutes) | n/a |
| Median lateness (minutes) | n/a |
| Maximum lateness (minutes) | n/a |

My reading:

Anomaly note: An arrival moved earlier lowers or removes the lateness of that stop. Shift anomalies change departure times only and have no effect here.

## Planned vs actual travel time

| Metric | Value |
|---|---|
| Legs measured (consecutive stops, no waiting) | 54 |
| Average planned travel (minutes) | 5.9 |
| Average actual travel (minutes) | 9.1 |
| Average difference, actual - planned (minutes) | 3.20 |
| Median difference (minutes) | 0.00 |
| Legs slower than planned | 27.8% |

My reading:

Anomaly note: A moved arrival time gives that leg a shorter or even negative actual travel time and pulls the average difference down. Omitted and duplicated stops are left out because the leg after an omission is not consecutive and a duplicate has no outcome.
