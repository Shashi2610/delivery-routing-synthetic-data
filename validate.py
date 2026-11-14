import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from generator import ids
from generator.config import LATE_GRACE_MINUTES, REGION_BOUNDS
from generator.schema import ENUMS, FOREIGN_KEYS, PRIMARY_KEYS, TABLES, UNIQUE_CONSTRAINTS, VEHICLE_TYPES
from generator.travel import HOUR_BAND_BASE_FACTORS, HOUR_BAND_START_MINUTES

ROOT = Path(__file__).parent

ID_PATTERNS = {
    "customer_site": r"SITE-\d{6}",
    "order": r"ORD-\d{4}-\d{6}",
    "delivery": r"DEL-\d{4}-\d{6}",
    "vehicle": r"VEH-\d{6}",
    "vehicle_capacity": r"VCAP-\d{6}",
    "driver": r"DRV-\d{6}",
    "shift": r"SHF-\d{4}-\d{6}",
    "time_window": r"TW-\d{4}-\d{6}",
    "route": r"RTE-\d{4}-\d{6}",
    "route_stop": r"STOP-RTE-\d{4}-\d{6}-\d{3}",
    "delivery_outcome": r"OUT-\d{4}-\d{6}",
    "delivery_status_event": r"DEV-\d{4}-\d{6}",
    "traffic_scenario": r"SCN-\d{4}-\d{6}",
}

NUMERIC_RANGES = [
    ("order", "weight_kg", 0.5, 1000), ("order", "volume_m3", 0.01, 8), ("order", "units", 1, 100),
    ("delivery", "weight_kg", 0.5, 1000), ("delivery", "volume_m3", 0.01, 8),
    ("delivery", "units", 1, 100), ("delivery", "service_minutes", 2, 60),
    ("vehicle_capacity", "max_weight_kg", 300, 10000), ("vehicle_capacity", "max_volume_m3", 3, 60),
    ("vehicle_capacity", "max_units", 20, 1000),
    ("shift", "max_driving_minutes", 120, 600), ("shift", "break_minutes_required", 0, 120),
    ("shift", "break_after_driving_minutes", 60, 300),
    ("traffic_scenario", "traffic_factor", 0.8, 2.0),
    ("travel_time_matrix", "distance_km", 0.05, 80), ("travel_time_matrix", "base_travel_minutes", 0.01, 10000),
    ("delivery_outcome", "attempt_no", 1, 3), ("route_stop", "sequence_no", 1, 60),
]

ALLOWED_TRANSITIONS = {
    "planned": {"assigned", "unserved"},
    "assigned": {"in_transit", "unserved", "planned"},
    "in_transit": {"delivered", "failed"},
    "failed": {"planned"},
    "unserved": {"planned"},
    "delivered": set(),
}

ISSUE_TYPES = [
    "ROUTE_CAPACITY_EXCEEDED",
    "STOP_OMITTED_OR_DUPLICATED",
    "ARRIVAL_BEFORE_PREVIOUS_DEPARTURE",
    "DRIVER_SHIFT_EXCEEDED",
    "COORDINATE_OUTSIDE_REGION",
]
DETECTION_COLUMNS = ["record_id", "table", "issue_type"]
GROUND_TRUTH_COLUMNS = ["record_id", "table", "issue_type", "anomaly_id"]

NOT_IMPLEMENTED = [
    "Stored route totals (distance, minutes, load): Route has no total columns because derived values are not stored, so there is nothing to reconcile. Route load is recomputed from the stops only inside the capacity detector.",
    "Stored lateness: lateness is not stored. Lateness rules are checked instead by comparing actual arrival with the window end and the grace period.",
    "Overwritten events: an event whose values were changed in place cannot be detected without a previous snapshot. Only removed events are detected, through gaps in event_seq and event_id.",
    "Break rules and actual driving minutes: not requested and not checked.",
]


@dataclass
class Result:
    group: str
    name: str
    checked: int
    failures: int

    @property
    def passed(self):
        return self.failures == 0


def load_data(data_dir):
    missing = [name for name in TABLES if not (data_dir / f"{name}.csv").exists()]
    if missing:
        raise SystemExit(f"missing tables in {data_dir}: {', '.join(missing)}")
    return {name: pd.read_csv(data_dir / f"{name}.csv") for name in TABLES}


def to_time(series):
    return pd.to_datetime(series)


def minutes_between(later, earlier):
    return (to_time(later) - to_time(earlier)).dt.total_seconds() / 60


def count_true(mask):
    return int(mask.sum())


def check_primary_keys(data):
    results = []
    for table, columns in PRIMARY_KEYS.items():
        frame = data[table]
        failures = frame[columns].isna().any(axis=1).sum() + frame.duplicated(columns).sum()
        results.append(Result("keys", f"primary key {table}", len(frame), int(failures)))
    return results


def check_unique_constraints(data):
    return [
        Result("keys", f"unique {table} ({', '.join(columns)})", len(data[table]), int(data[table].duplicated(columns).sum()))
        for table, columns in UNIQUE_CONSTRAINTS
    ]


def check_foreign_keys(data):
    results = []
    for child, column, parent, parent_column in FOREIGN_KEYS:
        values = data[child][column].dropna()
        orphans = ~values.isin(data[parent][parent_column])
        results.append(Result("foreign keys", f"{child}.{column} -> {parent}.{parent_column}", len(values), count_true(orphans)))
    return results


def check_enums(data):
    results = []
    for table, column, allowed, nullable in ENUMS:
        values = data[table][column]
        invalid = ~values.isin(allowed) & (values.notna() | (not nullable))
        results.append(Result("enums", f"{table}.{column}", len(values), count_true(invalid)))
    return results


def check_site_restrictions(data):
    sites = data["customer_site"]
    tokens = sites["allowed_vehicle_types"].dropna().str.split("|")
    bad_tokens = tokens.apply(lambda items: not set(items) <= VEHICLE_TYPES)
    flag_mismatch = sites["restricts_vehicle_types"] != sites["allowed_vehicle_types"].notna()
    return [
        Result("enums", "customer_site.allowed_vehicle_types values", len(tokens), count_true(bad_tokens)),
        Result("enums", "customer_site restriction flag matches allowed types", len(sites), count_true(flag_mismatch)),
    ]


def check_id_formats(data):
    results = []
    for table, pattern in ID_PATTERNS.items():
        key = PRIMARY_KEYS[table][0]
        valid = data[table][key].astype(str).str.fullmatch(pattern)
        results.append(Result("id formats", f"{table}.{key}", len(valid), count_true(~valid)))
    return results


def check_stop_ids(data):
    stops = data["route_stop"]
    expected = "STOP-" + stops["route_id"] + "-" + stops["sequence_no"].astype(str).str.zfill(3)
    return [Result("id formats", "route_stop.stop_id matches route_id and sequence_no", len(stops), count_true(stops["stop_id"] != expected))]


def check_numeric_ranges(data):
    results = []
    for table, column, low, high in NUMERIC_RANGES:
        values = data[table][column]
        results.append(Result("ranges", f"{table}.{column} in [{low}, {high}]", len(values), count_true((values < low) | (values > high))))
    return results


def check_window_times(data):
    windows = data["time_window"]
    width = minutes_between(windows["latest_arrival"], windows["earliest_arrival"])
    different_day = to_time(windows["earliest_arrival"]).dt.date != to_time(windows["latest_arrival"]).dt.date
    return [Result("time ordering", "time window earliest < latest, same day, 30 to 480 minutes", len(windows), count_true(~width.between(30, 480) | different_day))]


def check_shift_times(data):
    shifts = data["shift"]
    length = minutes_between(shifts["shift_end"], shifts["shift_start"])
    bad = (length <= 0) | (length > 14 * 60) | (shifts["max_driving_minutes"] > length)
    return [Result("time ordering", "shift start < end, at most 14 hours, driving limit within shift", len(shifts), count_true(bad))]


def check_site_hours(data):
    sites = data["customer_site"]
    return [Result("time ordering", "site open_time < close_time", len(sites), count_true(sites["open_time"] >= sites["close_time"]))]


def check_order_dates(data):
    orders = data["order"]
    ordered_day = to_time(orders["order_datetime"]).dt.normalize()
    return [Result("time ordering", "order placed on or before requested_date", len(orders), count_true(ordered_day > to_time(orders["requested_date"])))]


def check_route_times(data):
    routes = data["route"].merge(data["shift"][["shift_id", "shift_start", "shift_end"]], on="shift_id")
    start = to_time(routes["planned_start"])
    outside = (start < to_time(routes["shift_start"])) | (start >= to_time(routes["shift_end"]))
    other_day = routes["route_date"] != routes["shift_start"].str[:10]
    return [Result("time ordering", "route planned_start inside shift and route_date matches", len(routes), count_true(outside | other_day))]


def check_planned_stop_times(data):
    stops = data["route_stop"].merge(data["delivery"][["delivery_id", "service_minutes"]], on="delivery_id")
    stops = stops.merge(data["route"][["route_id", "shift_id"]], on="route_id").merge(data["shift"][["shift_id", "shift_start", "shift_end"]], on="shift_id")
    short_service = minutes_between(stops["planned_departure"], stops["planned_arrival"]) < stops["service_minutes"]
    outside = (to_time(stops["planned_arrival"]) < to_time(stops["shift_start"])) | (to_time(stops["planned_departure"]) > to_time(stops["shift_end"]))
    return [Result("time ordering", "planned stop: service time fits and stop is inside the shift", len(stops), count_true(short_service | outside))]


def band_labels(departures):
    minutes = departures.dt.hour * 60 + departures.dt.minute
    index = np.searchsorted(HOUR_BAND_START_MINUTES, minutes, side="right") - 1
    return np.array(list(HOUR_BAND_BASE_FACTORS))[index]


def build_leg_frame(data):
    stops = data["route_stop"].merge(data["delivery"][["delivery_id", "order_id"]], on="delivery_id")
    stops = stops.merge(data["order"][["order_id", "site_id"]], on="order_id")
    stops = stops.merge(data["route"][["route_id", "hub_id", "route_date", "planned_start"]], on="route_id")
    stops = stops.sort_values(["route_id", "sequence_no"], ignore_index=True)
    by_route = stops.groupby("route_id")
    first = by_route.cumcount() == 0
    stops["previous_sequence"] = by_route["sequence_no"].shift(1).where(~first, 0)
    stops["previous_site"] = by_route["site_id"].shift(1).where(~first, stops["hub_id"])
    stops["previous_departure"] = by_route["planned_departure"].shift(1).where(~first, stops["planned_start"])
    return stops


def check_planned_travel(data):
    stops = build_leg_frame(data)
    stops = stops.merge(data["travel_time_matrix"], left_on=["previous_site", "site_id"], right_on=["from_site_id", "to_site_id"], how="left")
    base = stops["base_travel_minutes"].where(stops["previous_site"] != stops["site_id"], 0.0)
    departure = to_time(stops["previous_departure"])
    index = pd.MultiIndex.from_arrays([stops["route_date"], band_labels(departure)])
    factor = data["traffic_scenario"].set_index(["scenario_date", "hour_band"])["traffic_factor"].reindex(index).to_numpy()
    required = base.to_numpy() * factor
    gap = minutes_between(stops["planned_arrival"], stops["previous_departure"]).to_numpy()
    consecutive = (stops["sequence_no"] == stops["previous_sequence"] + 1).to_numpy()
    too_fast = consecutive & (np.isnan(required) | (gap + 1e-6 < required))
    return [Result("time ordering", "planned arrival at least previous departure plus travel time", int(consecutive.sum()), int(too_fast.sum()))]


def check_actual_times(data):
    outcomes = data["delivery_outcome"]
    arrival, departure = outcomes["actual_arrival"], outcomes["actual_departure"]
    one_missing = arrival.isna() != departure.isna()
    reversed_times = departure.notna() & arrival.notna() & (to_time(departure) < to_time(arrival))
    return [Result("time ordering", "actual arrival <= actual departure, both set or both empty", len(outcomes), count_true(one_missing | reversed_times))]


def count_overlaps(shifts, column):
    ordered = shifts.assign(start=to_time(shifts["shift_start"]), end=to_time(shifts["shift_end"])).sort_values([column, "start"])
    previous_end = ordered.groupby(column)["end"].shift(1)
    return count_true(ordered["start"] < previous_end)


def check_no_overlapping_shifts(data):
    shifts = data["shift"]
    return [
        Result("time ordering", f"no overlapping shifts per {column}", len(shifts), count_overlaps(shifts, column))
        for column in ("driver_id", "vehicle_id")
    ]


def check_route_hubs(data):
    routes = data["route"].merge(data["shift"][["shift_id", "vehicle_id"]], on="shift_id")
    routes = routes.merge(data["vehicle"][["vehicle_id", "home_hub_id"]], on="vehicle_id")
    stops = data["route_stop"].merge(data["delivery"][["delivery_id", "order_id"]], on="delivery_id")
    stops = stops.merge(data["order"][["order_id", "site_id"]], on="order_id").merge(data["customer_site"][["site_id", "hub_id"]], on="site_id")
    stops = stops.merge(data["route"][["route_id", "hub_id"]], on="route_id", suffixes=("_site", "_route"))
    return [
        Result("hub rules", "route hub equals the vehicle's home hub", len(routes), count_true(routes["hub_id"] != routes["home_hub_id"])),
        Result("hub rules", "stop delivery site belongs to the route's hub", len(stops), count_true(stops["hub_id_site"] != stops["hub_id_route"])),
    ]


def sorted_events(data):
    events = data["delivery_status_event"].sort_values(["delivery_id", "event_seq"], ignore_index=True)
    events["position"] = events.groupby("delivery_id").cumcount() + 1
    return events


def check_event_sequences(data):
    events = sorted_events(data)
    gaps = events["event_seq"] != events["position"]
    wrong_first = (events["position"] == 1) & (events["status"] != "planned")
    earlier = events.groupby("delivery_id")["event_time"].transform(lambda times: to_time(times).diff().dt.total_seconds()) < 0
    return [
        Result("lifecycle", "event_seq runs 1..n per delivery (no event removed)", len(events), count_true(gaps)),
        Result("lifecycle", "first event of every delivery is planned", int((events["position"] == 1).sum()), count_true(wrong_first)),
        Result("lifecycle", "event times never go backwards", len(events), count_true(earlier)),
    ]


def check_event_transitions(data):
    events = sorted_events(data)
    previous = events.groupby("delivery_id")["status"].shift(1)
    has_previous = previous.notna()
    invalid = [current not in ALLOWED_TRANSITIONS[before] for before, current in zip(previous[has_previous], events["status"][has_previous])]
    return [Result("lifecycle", "status transitions are allowed", int(has_previous.sum()), sum(invalid))]


def check_event_fields(data):
    events = data["delivery_status_event"]
    needs_route = events["status"].isin(["assigned", "in_transit"]) & events["route_id"].isna()
    reason_mismatch = (events["status"] == "unserved") != events["reason_code"].notna()
    return [
        Result("lifecycle", "assigned and in_transit events carry a route_id", len(events), count_true(needs_route)),
        Result("lifecycle", "reason_code present exactly on unserved events", len(events), count_true(reason_mismatch)),
    ]


def check_event_ids(data):
    parts = data["delivery_status_event"]["event_id"].str.extract(r"DEV-(\d{4})-(\d{6})").astype(float)
    gaps = 0
    for _, numbers in parts.groupby(0)[1]:
        gaps += int(numbers.max()) - len(numbers)
    return [Result("lifecycle", "event ids are consecutive per year (no event removed)", len(parts), gaps)]


def check_unserved_outcomes(data):
    events = data["delivery_status_event"]
    unserved = set(events.loc[events["status"] == "unserved", "delivery_id"])
    return [Result("lifecycle", "unserved deliveries have no outcome", len(unserved), count_true(data["delivery_outcome"]["delivery_id"].isin(unserved)))]


def check_final_status(data):
    events = sorted_events(data)
    latest = events.groupby("delivery_id").tail(1).set_index("delivery_id")["status"]
    outcomes = data["delivery_outcome"].sort_values(["delivery_id", "attempt_no"]).groupby("delivery_id").tail(1)
    mismatch = outcomes["status"].to_numpy() != latest.reindex(outcomes["delivery_id"]).to_numpy()
    return [Result("lifecycle", "latest event status matches the outcome status", len(outcomes), int(mismatch.sum()))]


def check_deliveries_resolved(data):
    events = data["delivery_status_event"]
    assigned = set(events.loc[events["status"] == "assigned", "delivery_id"])
    unserved = set(events.loc[events["status"] == "unserved", "delivery_id"])
    unresolved = set(data["delivery"]["delivery_id"]) - assigned - unserved
    return [
        Result("coverage", "every delivery is assigned or unserved", len(data["delivery"]), len(unresolved)),
        Result("coverage", "no delivery is both assigned and unserved", len(data["delivery"]), len(assigned & unserved)),
    ]


def check_failed_reasons(data):
    outcomes = data["delivery_outcome"]
    mismatch = (outcomes["status"] == "failed") != outcomes["reason_code"].notna()
    return [Result("coverage", "reason_code present exactly on failed outcomes", len(outcomes), count_true(mismatch))]


def check_order_totals(data):
    totals = data["delivery"].groupby("order_id")[["weight_kg", "volume_m3", "units"]].sum()
    orders = data["order"].set_index("order_id")
    aligned = totals.reindex(orders.index)
    return [
        Result("reconciliation", f"order {column} equals the sum of its deliveries", len(orders), count_true(~np.isclose(orders[column], aligned[column], atol=0.006)))
        for column in ("weight_kg", "volume_m3", "units")
    ]


def check_lateness_rules(data):
    outcomes = data["delivery_outcome"].merge(data["delivery"][["delivery_id", "order_id"]], on="delivery_id", suffixes=("", "_delivery"))
    outcomes = outcomes.merge(data["order"][["order_id", "site_id"]], on="order_id").merge(data["customer_site"][["site_id", "close_time"]], on="site_id")
    outcomes = outcomes.merge(data["time_window"][["delivery_id", "latest_arrival"]], on="delivery_id")
    arrived = outcomes[outcomes["actual_arrival"].notna()]
    lateness = minutes_between(arrived["actual_arrival"], arrived["latest_arrival"])
    delivered = arrived["status"] == "delivered"
    late_failure = arrived["reason_code"] == "LATE_MISSED_WINDOW"
    closed_failure = arrived["reason_code"] == "SITE_CLOSED"
    after_close = to_time(arrived["actual_arrival"]).dt.strftime("%H:%M") > arrived["close_time"]
    return [
        Result("reconciliation", "delivered lateness within the grace period", count_true(delivered), count_true(delivered & (lateness > LATE_GRACE_MINUTES))),
        Result("reconciliation", "LATE_MISSED_WINDOW lateness above the grace period", count_true(late_failure), count_true(late_failure & (lateness <= LATE_GRACE_MINUTES))),
        Result("reconciliation", "SITE_CLOSED arrival after the closing time", count_true(closed_failure), count_true(closed_failure & ~after_close)),
    ]


STRUCTURAL_CHECKS = [
    check_primary_keys, check_unique_constraints, check_foreign_keys, check_enums, check_site_restrictions,
    check_id_formats, check_stop_ids, check_numeric_ranges, check_window_times, check_shift_times,
    check_site_hours, check_order_dates, check_route_times, check_planned_stop_times, check_planned_travel,
    check_actual_times, check_no_overlapping_shifts, check_route_hubs, check_event_sequences,
    check_event_transitions, check_event_fields, check_event_ids, check_unserved_outcomes,
    check_final_status, check_deliveries_resolved, check_failed_reasons, check_order_totals,
    check_lateness_rules,
]


def run_structural_checks(data):
    return [result for check in STRUCTURAL_CHECKS for result in check(data)]


def as_detections(record_ids, table, issue_type):
    return pd.DataFrame({"record_id": list(record_ids), "table": table, "issue_type": issue_type}, columns=DETECTION_COLUMNS)


def detect_route_capacity(data):
    stops = data["route_stop"].drop_duplicates(["route_id", "delivery_id"])
    stops = stops.merge(data["delivery"][["delivery_id", "weight_kg", "volume_m3", "units"]], on="delivery_id")
    loads = stops.groupby("route_id")[["weight_kg", "volume_m3", "units"]].sum()
    routes = data["route"][["route_id", "route_date", "shift_id"]].merge(data["shift"][["shift_id", "vehicle_id"]], on="shift_id")
    routes = routes.merge(data["vehicle_capacity"], on="vehicle_id")
    ends = routes["effective_to"].astype(object).fillna("9999-12-31")
    routes = routes[(routes["effective_from"] <= routes["route_date"]) & (routes["route_date"] <= ends)].set_index("route_id")
    joined = routes.join(loads)
    over = (joined["weight_kg"] > joined["max_weight_kg"]) | (joined["volume_m3"] > joined["max_volume_m3"]) | (joined["units"] > joined["max_units"])
    return as_detections(joined.index[over], "route", "ROUTE_CAPACITY_EXCEEDED")


def detect_sequence_errors(data):
    record_ids = []
    for route_id, stops in data["route_stop"].sort_values("sequence_no").groupby("route_id"):
        present = set(stops["sequence_no"])
        record_ids += [ids.stop_id(route_id, number) for number in range(1, max(present) + 1) if number not in present]
        record_ids += list(stops.loc[stops["delivery_id"].duplicated(), "stop_id"])
    return as_detections(record_ids, "route_stop", "STOP_OMITTED_OR_DUPLICATED")


def detect_arrival_before_departure(data):
    outcomes = data["delivery_outcome"].merge(data["route_stop"][["stop_id", "route_id", "sequence_no"]], on="stop_id")
    outcomes = outcomes.sort_values(["route_id", "sequence_no"], ignore_index=True)
    previous = outcomes.groupby("route_id")["actual_departure"].shift(1)
    previous = previous.groupby(outcomes["route_id"]).ffill()
    early = outcomes["actual_arrival"].notna() & previous.notna() & (to_time(outcomes["actual_arrival"]) < to_time(previous))
    return as_detections(outcomes.loc[early, "outcome_id"], "delivery_outcome", "ARRIVAL_BEFORE_PREVIOUS_DEPARTURE")


def detect_shift_exceeded(data):
    outcomes = data["delivery_outcome"].merge(data["route_stop"][["stop_id", "route_id"]], on="stop_id")
    outcomes = outcomes.merge(data["route"][["route_id", "shift_id"]], on="route_id").merge(data["shift"][["shift_id", "shift_end"]], on="shift_id")
    late = outcomes["actual_departure"].notna() & (to_time(outcomes["actual_departure"]) > to_time(outcomes["shift_end"]))
    return as_detections(outcomes.loc[late, "outcome_id"], "delivery_outcome", "DRIVER_SHIFT_EXCEEDED")


def detect_outside_region(data):
    sites = data["customer_site"]
    bounds = REGION_BOUNDS
    inside = sites["lat"].between(bounds["lat_min"], bounds["lat_max"]) & sites["lon"].between(bounds["lon_min"], bounds["lon_max"])
    return as_detections(sites.loc[~inside, "site_id"], "customer_site", "COORDINATE_OUTSIDE_REGION")


DETECTORS = [
    detect_route_capacity, detect_sequence_errors, detect_arrival_before_departure,
    detect_shift_exceeded, detect_outside_region,
]


def run_detectors(data):
    return pd.concat([detector(data) for detector in DETECTORS], ignore_index=True)


def label_keys(table, record_id, issue_type, data):
    if issue_type != "ROUTE_CAPACITY_EXCEEDED":
        return {(table, record_id)}
    deliveries = data["delivery"].loc[data["delivery"]["order_id"] == record_id, "delivery_id"] if table == "order" else [record_id]
    routes = data["route_stop"].loc[data["route_stop"]["delivery_id"].isin(deliveries), "route_id"]
    return {("route", route) for route in routes}


def score_issue_type(issue_type, detections, labels, data):
    found = set(zip(detections["table"], detections["record_id"]))
    anomaly_keys = {}
    for row in labels.itertuples(index=False):
        keys = label_keys(row.table, row.record_id, issue_type, data)
        anomaly_keys.setdefault(row.anomaly_id, set()).update(keys)
    labelled = set().union(*anomaly_keys.values()) if anomaly_keys else set()
    missed = sorted(anomaly for anomaly, keys in anomaly_keys.items() if not keys & found)
    return {
        "issue_type": issue_type,
        "anomalies": len(anomaly_keys),
        "detected": len(anomaly_keys) - len(missed),
        "detections": len(found),
        "true_positives": len(found & labelled),
        "false_positives": sorted(found - labelled),
        "missed": missed,
    }


def score_detections(detections, ground_truth, data):
    scores = []
    for issue_type in ISSUE_TYPES:
        found = detections[detections["issue_type"] == issue_type]
        labels = ground_truth[ground_truth["issue_type"] == issue_type]
        scores.append(score_issue_type(issue_type, found, labels, data))
    return scores


def ratio(numerator, denominator):
    return None if denominator == 0 else numerator / denominator


def format_ratio(value):
    return "n/a" if value is None else f"{value:.1%}"


def scoring_passes(scores, has_ground_truth):
    if not has_ground_truth:
        return all(score["detections"] == 0 for score in scores)
    return all(score["detected"] == score["anomalies"] for score in scores)


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def structural_section(results):
    rows = [(r.group, r.name, r.checked, r.failures, "pass" if r.passed else "FAIL") for r in results]
    return "## Structural checks\n\n" + markdown_table(["Group", "Check", "Rows checked", "Failures", "Status"], rows)


def detection_section(detections):
    counts = detections.groupby("issue_type").size()
    rows = [(issue_type, int(counts.get(issue_type, 0))) for issue_type in ISSUE_TYPES]
    return "## Rule detectors\n\n" + markdown_table(["Issue type", "Detections"], rows)


def scoring_section(scores, has_ground_truth):
    if not has_ground_truth:
        return "## Scoring\n\nNo ground truth file was found, so detections are not scored. On a clean dataset every detector should report zero detections."
    rows = [
        (
            s["issue_type"], s["anomalies"], s["detected"], format_ratio(ratio(s["detected"], s["anomalies"])),
            s["detections"], s["true_positives"], format_ratio(ratio(s["true_positives"], s["detections"])),
            len(s["false_positives"]), len(s["missed"]),
        )
        for s in scores
    ]
    headers = ["Issue type", "Injected", "Detected", "Recall", "Detections", "True positives", "Precision", "False positives", "Missed"]
    return "## Scoring\n\n" + markdown_table(headers, rows) + "\n\n" + missed_lines(scores)


def missed_lines(scores):
    lines = [f"- {s['issue_type']} missed: {', '.join(s['missed'][:10])}" for s in scores if s["missed"]]
    lines += [f"- {s['issue_type']} false positives: {', '.join(map(str, s['false_positives'][:10]))}" for s in scores if s["false_positives"]]
    return "\n".join(lines) if lines else "No missed anomalies and no false positives."


def summary_section(results, scores, has_ground_truth, passed):
    failed = [r.name for r in results if not r.passed]
    structural = f"{len(results) - len(failed)} of {len(results)} structural checks passed"
    detected = sum(s["detections"] for s in scores)
    lines = [f"Overall: {'PASS' if passed else 'FAIL'}", f"- {structural}", f"- {detected} anomalies detected by the rule checks"]
    lines += [f"- failed: {name}" for name in failed]
    return "## Summary\n\n" + "\n".join(lines)


def not_implemented_section():
    return "## Not implemented\n\n" + "\n".join(f"- {item}" for item in NOT_IMPLEMENTED)


def write_report(path, data_dir, results, detections, scores, has_ground_truth, passed):
    sections = [
        f"# Validation report\n\nData folder: `{data_dir}`",
        summary_section(results, scores, has_ground_truth, passed),
        structural_section(results),
        detection_section(detections),
        scoring_section(scores, has_ground_truth),
        not_implemented_section(),
    ]
    path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")


def print_summary(results, scores, has_ground_truth, passed):
    failed = [r for r in results if not r.passed]
    print(f"structural checks: {len(results) - len(failed)}/{len(results)} passed")
    for result in failed:
        print(f"  FAIL {result.name}: {result.failures}")
    for score in scores:
        recall = format_ratio(ratio(score["detected"], score["anomalies"]))
        precision = format_ratio(ratio(score["true_positives"], score["detections"]))
        print(f"{score['issue_type']}: detections {score['detections']}, recall {recall}, precision {precision}")
    print("result: " + ("PASS" if passed else "FAIL"))


def parse_args():
    parser = argparse.ArgumentParser(description="Validate the generated delivery-routing dataset.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--ground-truth", type=Path, default=ROOT / "ground_truth" / "ground_truth.csv")
    parser.add_argument("--report", type=Path, default=ROOT / "validation_report.md")
    return parser.parse_args()


def main():
    args = parse_args()
    data = load_data(args.data_dir)
    results = run_structural_checks(data)
    detections = run_detectors(data)
    has_ground_truth = args.ground_truth.exists()
    ground_truth = pd.read_csv(args.ground_truth) if has_ground_truth else pd.DataFrame(columns=GROUND_TRUTH_COLUMNS)
    scores = score_detections(detections, ground_truth, data)
    passed = all(r.passed for r in results) and scoring_passes(scores, has_ground_truth)
    write_report(args.report, args.data_dir, results, detections, scores, has_ground_truth, passed)
    print_summary(results, scores, has_ground_truth, passed)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
