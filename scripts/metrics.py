import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent

TABLES = [
    "customer_site", "vehicle", "vehicle_capacity", "shift", "travel_time_matrix", "traffic_scenario",
    "order", "delivery", "time_window", "delivery_status_event", "route", "route_stop", "delivery_outcome",
]

ANOMALY_NOTES = {
    "performance": "Omitted stops remove an outcome row, so attempted and on-time counts drop while assigned stays the same. Duplicated stops have no outcome and change nothing here. A moved arrival time can turn a late delivery into an on-time one.",
    "failures": "No anomaly writes a failed outcome or a reason code, so these counts come only from the execution rules. An omitted stop that was a failure would disappear from the table.",
    "utilisation": "A capacity anomaly pushes route weight above 100% of capacity. A shift anomaly pushes actual shift utilisation above 100%. Duplicated stops are counted once, so they do not change route load.",
    "hubs": "Anomalies are spread over all hubs, so a hub with few routes can move by a few points from a single omitted stop or moved arrival time.",
    "lateness": "An arrival moved earlier lowers or removes the lateness of that stop. Shift anomalies change departure times only and have no effect here.",
    "travel": "A moved arrival time gives that leg a shorter or even negative actual travel time and pulls the average difference down. Omitted and duplicated stops are left out because the leg after an omission is not consecutive and a duplicate has no outcome.",
}


def load_data(data_dir):
    missing = [name for name in TABLES if not (data_dir / f"{name}.csv").exists()]
    if missing:
        raise SystemExit(f"missing tables in {data_dir}: {', '.join(missing)}")
    return {name: pd.read_csv(data_dir / f"{name}.csv") for name in TABLES}


def to_time(series):
    return pd.to_datetime(series)


def minutes_between(later, earlier):
    return (to_time(later) - to_time(earlier)).dt.total_seconds() / 60


def percent(numerator, denominator):
    return "n/a" if denominator == 0 else f"{numerator / denominator:.1%}"


def number(value, digits=1):
    return "n/a" if pd.isna(value) else f"{value:.{digits}f}"


def build_delivery_frame(data):
    sites = data["customer_site"][["site_id", "hub_id"]]
    frame = data["delivery"][["delivery_id", "order_id"]].merge(data["order"][["order_id", "site_id"]], on="order_id")
    frame = frame.merge(sites, on="site_id")
    events = data["delivery_status_event"]
    frame["assigned"] = frame["delivery_id"].isin(events.loc[events["status"] == "assigned", "delivery_id"])
    frame["unserved"] = frame["delivery_id"].isin(events.loc[events["status"] == "unserved", "delivery_id"])
    outcomes = data["delivery_outcome"].sort_values(["delivery_id", "attempt_no"]).groupby("delivery_id").tail(1)
    outcomes = outcomes.merge(data["time_window"][["delivery_id", "latest_arrival"]], on="delivery_id")
    columns = ["delivery_id", "status", "reason_code", "actual_arrival", "latest_arrival"]
    frame = frame.merge(outcomes[columns], on="delivery_id", how="left")
    lateness = minutes_between(frame["actual_arrival"], frame["latest_arrival"])
    delivered = frame["status"] == "delivered"
    frame["attempted"] = frame["status"].notna()
    frame["late"] = delivered & (lateness > 0)
    frame["on_time"] = delivered & ~frame["late"]
    frame["failed"] = frame["status"] == "failed"
    frame["lateness_minutes"] = lateness.where(frame["late"])
    return frame


def performance_rows(frame):
    total, assigned, unserved = len(frame), int(frame["assigned"].sum()), int(frame["unserved"].sum())
    attempted, on_time = int(frame["attempted"].sum()), int(frame["on_time"].sum())
    return [
        ("Total deliveries", total),
        ("Assigned", assigned),
        ("Unserved", unserved),
        ("Assigned + unserved equals total", "yes" if assigned + unserved == total else "no"),
        ("Attempted (has an outcome row)", attempted),
        ("Delivered on time", on_time),
        ("Delivered late", int(frame["late"].sum())),
        ("Failed", int(frame["failed"].sum())),
        ("On-time % of attempted", percent(on_time, attempted)),
        ("Service rate (assigned / total)", percent(assigned, total)),
    ]


def reason_rows(reasons):
    counts = reasons.value_counts().sort_index()
    total = int(counts.sum())
    rows = [(reason, int(count), percent(count, total)) for reason, count in counts.items()]
    return rows or [("none", 0, "n/a")]


def effective_capacity(data):
    routes = data["route"][["route_id", "route_date", "shift_id"]].merge(data["shift"][["shift_id", "vehicle_id"]], on="shift_id")
    routes = routes.merge(data["vehicle_capacity"], on="vehicle_id")
    ends = routes["effective_to"].astype(object).fillna("9999-12-31")
    in_effect = (routes["effective_from"] <= routes["route_date"]) & (routes["route_date"] <= ends)
    return routes[in_effect].set_index("route_id")


def build_load_frame(data):
    stops = data["route_stop"].drop_duplicates(["route_id", "delivery_id"])
    stops = stops.merge(data["delivery"][["delivery_id", "weight_kg", "volume_m3"]], on="delivery_id")
    loads = stops.groupby("route_id")[["weight_kg", "volume_m3"]].sum()
    joined = effective_capacity(data).join(loads)
    joined["weight_utilisation"] = joined["weight_kg"] / joined["max_weight_kg"]
    joined["volume_utilisation"] = joined["volume_m3"] / joined["max_volume_m3"]
    return joined


def distribution_row(label, series):
    quantiles = series.quantile([0.25, 0.5, 0.75])
    over = int((series > 1).sum())
    return (label, len(series), f"{series.mean():.1%}", f"{series.min():.1%}", f"{quantiles[0.25]:.1%}", f"{quantiles[0.5]:.1%}", f"{quantiles[0.75]:.1%}", f"{series.max():.1%}", over)


def load_rows(loads):
    return [
        distribution_row("Weight vs capacity", loads["weight_utilisation"].dropna()),
        distribution_row("Volume vs capacity", loads["volume_utilisation"].dropna()),
    ]


def build_shift_frame(data):
    shifts = data["shift"][["shift_id", "shift_start", "shift_end"]]
    routes = data["route"][["route_id", "shift_id", "planned_start"]].merge(shifts, on="shift_id")
    stops = data["route_stop"].merge(data["delivery_outcome"][["stop_id", "actual_departure"]], on="stop_id", how="left")
    planned_end = stops.groupby("route_id")["planned_departure"].max()
    actual_end = stops.assign(actual_departure=to_time(stops["actual_departure"])).groupby("route_id")["actual_departure"].max()
    routes = routes.set_index("route_id")
    shift_minutes = minutes_between(routes["shift_end"], routes["shift_start"])
    routes["planned_utilisation"] = minutes_between(planned_end.reindex(routes.index), routes["planned_start"]) / shift_minutes
    routes["actual_utilisation"] = minutes_between(actual_end.reindex(routes.index), routes["shift_start"]) / shift_minutes
    return routes


def shift_rows(shift_frame, shift_count):
    idle = shift_count - len(shift_frame)
    rows = [("Shifts", shift_count), ("Shifts with a route", len(shift_frame)), ("Shifts without a route", f"{idle} ({percent(idle, shift_count)})")]
    for label, column in (("Planned", "planned_utilisation"), ("Actual", "actual_utilisation")):
        values = shift_frame[column].dropna()
        rows.append((f"{label} route minutes / shift minutes: mean", f"{values.mean():.1%}"))
        rows.append((f"{label}: median", f"{values.median():.1%}"))
        rows.append((f"{label}: max", f"{values.max():.1%}"))
        rows.append((f"{label}: routes above 100%", int((values > 1).sum())))
    return rows


def hub_rows(frame):
    rows = []
    for hub_id, group in frame.groupby("hub_id"):
        attempted, on_time = int(group["attempted"].sum()), int(group["on_time"].sum())
        assigned = int(group["assigned"].sum())
        rows.append((hub_id, len(group), assigned, percent(assigned, len(group)), attempted, on_time, percent(on_time, attempted)))
    return rows


def lateness_rows(frame):
    late = frame["lateness_minutes"].dropna()
    delivered = int(frame["on_time"].sum() + frame["late"].sum())
    return [
        ("Late deliveries", len(late)),
        ("Share of delivered", percent(len(late), delivered)),
        ("Average lateness (minutes)", number(late.mean())),
        ("Median lateness (minutes)", number(late.median())),
        ("Maximum lateness (minutes)", number(late.max())),
    ]


def build_leg_frame(data):
    stops = data["route_stop"].merge(data["delivery"][["delivery_id", "order_id"]], on="delivery_id")
    stops = stops.merge(data["order"][["order_id", "site_id"]], on="order_id")
    stops = stops.merge(data["route"][["route_id", "hub_id", "route_date", "shift_id", "planned_start"]], on="route_id")
    stops = stops.merge(data["shift"][["shift_id", "shift_start"]], on="shift_id")
    stops = stops.merge(data["time_window"][["delivery_id", "earliest_arrival"]], on="delivery_id")
    stops = stops.merge(data["delivery_outcome"][["stop_id", "actual_arrival", "actual_departure"]], on="stop_id", how="left")
    stops = stops.sort_values(["route_id", "sequence_no"], ignore_index=True)
    by_route = stops.groupby("route_id")
    first = by_route.cumcount() == 0
    stops["previous_sequence"] = by_route["sequence_no"].shift(1).where(~first, 0)
    stops["previous_site"] = by_route["site_id"].shift(1).where(~first, stops["hub_id"])
    stops["previous_planned_departure"] = by_route["planned_departure"].shift(1).where(~first, stops["planned_start"])
    stops["previous_actual_departure"] = by_route["actual_departure"].shift(1).where(~first, stops["shift_start"])
    return stops


def band_labels(data, departures):
    labels = sorted(data["traffic_scenario"]["hour_band"].unique())
    starts = [int(label[:2]) * 60 for label in labels]
    minutes = departures.dt.hour * 60 + departures.dt.minute
    return np.array(labels)[np.searchsorted(starts, minutes, side="right") - 1]


def planned_leg_minutes(data, legs):
    merged = legs.merge(data["travel_time_matrix"], left_on=["previous_site", "site_id"], right_on=["from_site_id", "to_site_id"], how="left")
    base = merged["base_travel_minutes"].where(merged["previous_site"] != merged["site_id"], 0.0)
    index = pd.MultiIndex.from_arrays([merged["route_date"], band_labels(data, to_time(merged["previous_planned_departure"]))])
    factor = data["traffic_scenario"].set_index(["scenario_date", "hour_band"])["traffic_factor"].reindex(index).to_numpy()
    return pd.Series(np.ceil(np.round(base.to_numpy() * factor, 6)), index=legs.index)


def travel_rows(data):
    legs = build_leg_frame(data)
    legs["planned_minutes"] = planned_leg_minutes(data, legs)
    legs["actual_minutes"] = minutes_between(legs["actual_arrival"], legs["previous_actual_departure"])
    consecutive = legs["sequence_no"] == legs["previous_sequence"] + 1
    waited = to_time(legs["actual_arrival"]) <= to_time(legs["earliest_arrival"])
    measured = legs[consecutive & ~waited & legs["actual_minutes"].notna()]
    difference = measured["actual_minutes"] - measured["planned_minutes"]
    return [
        ("Legs measured (consecutive stops, no waiting)", len(measured)),
        ("Average planned travel (minutes)", number(measured["planned_minutes"].mean())),
        ("Average actual travel (minutes)", number(measured["actual_minutes"].mean())),
        ("Average difference, actual - planned (minutes)", number(difference.mean(), 2)),
        ("Median difference (minutes)", number(difference.median(), 2)),
        ("Legs slower than planned", percent(int((difference > 0).sum()), len(difference))),
    ]


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def section(title, headers, rows, note_key):
    return f"## {title}\n\n{markdown_table(headers, rows)}\n\nMy reading:\n\nAnomaly note: {ANOMALY_NOTES[note_key]}"


def build_sections(data, frame):
    loads, shifts = build_load_frame(data), build_shift_frame(data)
    unserved = data["delivery_status_event"]
    unserved = unserved.loc[unserved["status"] == "unserved", "reason_code"]
    reason_headers = ["Reason code", "Count", "Share"]
    return [
        section("Delivery performance", ["Metric", "Value"], performance_rows(frame), "performance"),
        section("Failures by reason code", reason_headers, reason_rows(frame.loc[frame["failed"], "reason_code"]), "failures"),
        section("Unserved by reason code", reason_headers, reason_rows(unserved), "failures"),
        section("Vehicle utilisation: route load vs capacity", ["Measure", "Routes", "Mean", "Min", "25th", "Median", "75th", "Max", "Routes above 100%"], load_rows(loads), "utilisation"),
        section("Shift utilisation", ["Metric", "Value"], shift_rows(shifts, len(data["shift"])), "utilisation"),
        section("Per hub", ["Hub", "Deliveries", "Assigned", "Service rate", "Attempted", "On time", "On-time %"], hub_rows(frame), "hubs"),
        section("Lateness of late deliveries", ["Metric", "Value"], lateness_rows(frame), "lateness"),
        section("Planned vs actual travel time", ["Metric", "Value"], travel_rows(data), "travel"),
    ]


def build_report(sections):
    intro = "# Metrics report\n\nAll numbers are computed from the CSV tables. Each section has a line for your own reading and a note on how the injected anomalies can affect it."
    definitions = (
        "## Definitions\n\n"
        "- Attempted: a delivery with an outcome row.\n"
        "- On time: delivered with actual arrival at or before the window end. Late: delivered after the window end, inside the grace period.\n"
        "- Route load: weight and volume of the distinct deliveries on a route divided by the vehicle capacity in effect on the route date.\n"
        "- Route minutes: from route start to the last stop's departure. The return leg to the hub is not included.\n"
        "- Travel legs: only consecutive stops where the vehicle did not wait for the window to open, so travel time can be read from the times."
    )
    return "\n\n".join([intro, definitions] + sections) + "\n"


def print_summary(frame, loads):
    attempted = int(frame["attempted"].sum())
    print(f"deliveries: {len(frame)}, assigned: {int(frame['assigned'].sum())}, unserved: {int(frame['unserved'].sum())}")
    print(f"attempted: {attempted}, on time: {int(frame['on_time'].sum())}, late: {int(frame['late'].sum())}, failed: {int(frame['failed'].sum())}")
    print(f"on-time % of attempted: {percent(int(frame['on_time'].sum()), attempted)}")
    print(f"service rate: {percent(int(frame['assigned'].sum()), len(frame))}")
    print(f"mean weight utilisation: {loads['weight_utilisation'].mean():.1%}, mean volume utilisation: {loads['volume_utilisation'].mean():.1%}")
    print(f"average lateness of late deliveries: {number(frame['lateness_minutes'].mean())} minutes")


def parse_args():
    parser = argparse.ArgumentParser(description="Write a metrics report from the generated CSV files.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "metrics_report.md")
    return parser.parse_args()


def main():
    args = parse_args()
    data = load_data(args.data_dir)
    frame = build_delivery_frame(data)
    args.report.write_text(build_report(build_sections(data, frame)), encoding="utf-8", newline="\n")
    print_summary(frame, build_load_frame(data))


if __name__ == "__main__":
    main()
