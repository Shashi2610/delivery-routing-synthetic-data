import itertools
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from generator import ids
from generator.config import (
    ANOMALY_MIN_COUNT,
    ANOMALY_RATES,
    ARRIVAL_EARLY_MINUTES,
    COORDINATE_OFFSET_DEGREES,
    REGION_BOUNDS,
    SHIFT_OVERRUN_MINUTES,
    TIMESTAMP_FORMAT,
)
from generator.routing import build_travel_times, minutes_to_text
from generator.simulation import build_stop_table

MAX_ORDER_WEIGHT_KG = 1000
LABEL_COLUMNS = [
    "record_id", "table", "issue_type", "description", "field",
    "original_value", "injected_value", "anomaly_id",
]


@dataclass
class Workspace:
    rng: object
    tables: dict
    travel: object
    site_index: pd.Series
    labels: list = field(default_factory=list)
    used_routes: set = field(default_factory=set)
    counter: object = field(default_factory=lambda: itertools.count(1))

    def new_anomaly_id(self):
        return f"ANOM-{next(self.counter):04d}"

    def add_label(self, anomaly_id, issue_type, table, record_id, field_name, original, injected, description):
        self.labels.append({
            "record_id": record_id,
            "table": table,
            "issue_type": issue_type,
            "description": description,
            "field": field_name,
            "original_value": original,
            "injected_value": injected,
            "anomaly_id": anomaly_id,
        })

    def choose(self, candidates, count):
        pool = np.array(sorted(candidates))
        return self.rng.choice(pool, size=min(count, len(pool)), replace=False)

    def claim_routes(self, candidates, count):
        chosen = self.choose(set(candidates) - self.used_routes, count)
        self.used_routes.update(chosen)
        return list(chosen)


def target_count(issue_type, table_rows):
    return max(ANOMALY_MIN_COUNT, round(ANOMALY_RATES[issue_type] * table_rows))


def set_cell(table, key_column, key, column, value):
    row = table.index[table[key_column] == key][0]
    original = table.at[row, column]
    table.at[row, column] = value
    return original


def row_text(row):
    return "|".join(f"{name}={value}" for name, value in row.items())


def draw_minutes(rng, bounds):
    return int(rng.integers(bounds[0], bounds[1] + 1))


def timestamp_text(moment):
    return moment.strftime(TIMESTAMP_FORMAT)


def stops_with_loads(tables):
    delivery = tables["delivery"][["delivery_id", "order_id", "weight_kg", "volume_m3", "units"]]
    return tables["route_stop"].merge(delivery, on="delivery_id")


def capacity_by_route(tables):
    routes = tables["route"][["route_id", "route_date", "shift_id"]]
    routes = routes.merge(tables["shift"][["shift_id", "vehicle_id"]], on="shift_id")
    routes = routes.merge(tables["vehicle_capacity"], on="vehicle_id")
    ends = routes["effective_to"].fillna("9999-12-31")
    in_effect = (routes["effective_from"] <= routes["route_date"]) & (routes["route_date"] <= ends)
    return routes[in_effect].set_index("route_id")[["max_weight_kg", "max_volume_m3", "max_units"]]


def inject_route_capacity(work):
    tables = work.tables
    issue_type = "ROUTE_CAPACITY_EXCEEDED"
    stops = stops_with_loads(tables)
    stops["order_weight_kg"] = stops["order_id"].map(tables["order"].set_index("order_id")["weight_kg"])
    heaviest = stops.loc[stops.groupby("route_id")["weight_kg"].idxmax()].set_index("route_id")
    frame = heaviest[["delivery_id", "order_id", "order_weight_kg", "weight_kg"]]
    frame = frame.join(stops.groupby("route_id")["weight_kg"].sum().rename("load_kg"))
    frame = frame.join(capacity_by_route(tables)["max_weight_kg"])
    frame["extra_kg"] = (frame["max_weight_kg"] - frame["load_kg"] + 0.01).round(2)
    eligible = frame[frame["order_weight_kg"] + frame["extra_kg"] <= MAX_ORDER_WEIGHT_KG]
    for route_id in work.claim_routes(eligible.index, target_count(issue_type, len(tables["route"]))):
        row = frame.loc[route_id]
        anomaly_id = work.new_anomaly_id()
        description = f"Route {route_id} load {row.load_kg + row.extra_kg:.2f} kg exceeds capacity {row.max_weight_kg} kg"
        new_delivery_weight = round(row.weight_kg + row.extra_kg, 2)
        new_order_weight = round(row.order_weight_kg + row.extra_kg, 2)
        set_cell(tables["delivery"], "delivery_id", row.delivery_id, "weight_kg", new_delivery_weight)
        set_cell(tables["order"], "order_id", row.order_id, "weight_kg", new_order_weight)
        work.add_label(anomaly_id, issue_type, "delivery", row.delivery_id, "weight_kg", row.weight_kg, new_delivery_weight, description)
        work.add_label(anomaly_id, issue_type, "order", row.order_id, "weight_kg", row.order_weight_kg, new_order_weight, description)


def duplicate_candidates(work):
    tables = work.tables
    delivery = tables["delivery"][["delivery_id", "weight_kg", "volume_m3", "units"]]
    stops = build_stop_table(tables, work.site_index).merge(delivery, on="delivery_id")
    last = stops.sort_values(["route_id", "sequence_no"]).groupby("route_id").tail(1)
    loads = stops_with_loads(tables).groupby("route_id")[["weight_kg", "volume_m3", "units"]].sum()
    capacity = capacity_by_route(tables)
    rows = []
    for stop in last.itertuples(index=False):
        arrival = stop.planned_departure_min
        departure = arrival + stop.service_minutes
        back = work.travel.minutes(stop.route_date, stop.site_index, stop.hub_index, departure)
        load, limit = loads.loc[stop.route_id], capacity.loc[stop.route_id]
        fits = (
            load.weight_kg + stop.weight_kg <= limit.max_weight_kg
            and load.volume_m3 + stop.volume_m3 <= limit.max_volume_m3
            and load.units + stop.units <= limit.max_units
        )
        if fits and arrival <= stop.latest_min and departure + back <= stop.shift_end_min:
            rows.append({
                "route_id": stop.route_id,
                "delivery_id": stop.delivery_id,
                "sequence_no": stop.sequence_no + 1,
                "planned_arrival": minutes_to_text([stop.route_date], [arrival])[0],
                "planned_departure": minutes_to_text([stop.route_date], [departure])[0],
            })
    return pd.DataFrame(rows, columns=["route_id", "delivery_id", "sequence_no", "planned_arrival", "planned_departure"]).set_index("route_id")


def add_duplicate_stop(work, route_id, candidate):
    issue_type = "STOP_OMITTED_OR_DUPLICATED"
    new_stop = {
        "stop_id": ids.stop_id(route_id, candidate.sequence_no),
        "route_id": route_id,
        "sequence_no": candidate.sequence_no,
        "delivery_id": candidate.delivery_id,
        "planned_arrival": candidate.planned_arrival,
        "planned_departure": candidate.planned_departure,
    }
    description = f"Delivery {candidate.delivery_id} duplicated in route {route_id} as stop {candidate.sequence_no}"
    work.add_label(work.new_anomaly_id(), issue_type, "route_stop", new_stop["stop_id"], "row", "", row_text(new_stop), description)
    return new_stop


def remove_stop(work, route_id, stop_count):
    issue_type = "STOP_OMITTED_OR_DUPLICATED"
    tables = work.tables
    sequence_no = int(work.rng.integers(1, stop_count))
    stops = tables["route_stop"]
    stop = stops[(stops["route_id"] == route_id) & (stops["sequence_no"] == sequence_no)].iloc[0]
    outcomes = tables["delivery_outcome"]
    outcome = outcomes[outcomes["stop_id"] == stop["stop_id"]].iloc[0]
    anomaly_id = work.new_anomaly_id()
    description = f"Stop {sequence_no} of route {route_id} removed, leaving a sequence gap; delivery {stop['delivery_id']} still references the route"
    work.add_label(anomaly_id, issue_type, "route_stop", stop["stop_id"], "row", row_text(stop), "deleted", description)
    work.add_label(anomaly_id, issue_type, "delivery_outcome", outcome["outcome_id"], "row", row_text(outcome), "deleted", description)
    tables["route_stop"] = stops.drop(stop.name)
    tables["delivery_outcome"] = outcomes.drop(outcome.name)


def inject_stop_errors(work):
    tables = work.tables
    count = target_count("STOP_OMITTED_OR_DUPLICATED", len(tables["route_stop"]))
    candidates = duplicate_candidates(work)
    duplicate_routes = work.claim_routes(candidates.index, count // 2)
    sizes = tables["route_stop"].groupby("route_id").size()
    omission_routes = work.claim_routes(sizes[sizes >= 3].index, count - len(duplicate_routes))
    added = [add_duplicate_stop(work, route_id, candidates.loc[route_id]) for route_id in duplicate_routes]
    for route_id in omission_routes:
        remove_stop(work, route_id, int(sizes[route_id]))
    stops = pd.concat([tables["route_stop"], pd.DataFrame(added)], ignore_index=True)
    tables["route_stop"] = stops.sort_values(["route_id", "sequence_no"], ignore_index=True)
    tables["delivery_outcome"] = tables["delivery_outcome"].reset_index(drop=True)


def outcomes_in_route_order(tables):
    outcomes = tables["delivery_outcome"].merge(tables["route_stop"][["stop_id", "route_id", "sequence_no"]], on="stop_id")
    return outcomes.sort_values(["route_id", "sequence_no"], ignore_index=True)


def inject_arrival_before_departure(work):
    issue_type = "ARRIVAL_BEFORE_PREVIOUS_DEPARTURE"
    tables = work.tables
    outcomes = outcomes_in_route_order(tables)
    outcomes["previous_departure"] = outcomes.groupby("route_id")["actual_departure"].shift(1)
    eligible = outcomes[outcomes["previous_departure"].notna() & outcomes["actual_arrival"].notna()]
    target = target_count(issue_type, len(outcomes))
    for route_id in work.claim_routes(eligible["route_id"].unique(), target):
        rows = eligible[eligible["route_id"] == route_id]
        row = rows.iloc[int(work.rng.integers(len(rows)))]
        early = pd.Timedelta(minutes=draw_minutes(work.rng, ARRIVAL_EARLY_MINUTES))
        injected = timestamp_text(pd.Timestamp(row["previous_departure"]) - early)
        set_cell(tables["delivery_outcome"], "outcome_id", row["outcome_id"], "actual_arrival", injected)
        description = f"Arrival at stop {row['sequence_no']} of route {route_id} is before the previous stop's departure"
        work.add_label(work.new_anomaly_id(), issue_type, "delivery_outcome", row["outcome_id"], "actual_arrival", row["actual_arrival"], injected, description)


def inject_shift_exceeded(work):
    issue_type = "DRIVER_SHIFT_EXCEEDED"
    tables = work.tables
    outcomes = outcomes_in_route_order(tables)
    last = outcomes.groupby("route_id").tail(1)
    last = last[last["status"] == "delivered"]
    shift_end = tables["route"][["route_id", "shift_id"]].merge(tables["shift"][["shift_id", "shift_end"]], on="shift_id")
    last = last.merge(shift_end[["route_id", "shift_end"]], on="route_id").set_index("route_id")
    for route_id in work.claim_routes(last.index, target_count(issue_type, len(tables["route"]))):
        row = last.loc[route_id]
        overrun = pd.Timedelta(minutes=draw_minutes(work.rng, SHIFT_OVERRUN_MINUTES))
        injected = timestamp_text(pd.Timestamp(row["shift_end"]) + overrun)
        anomaly_id = work.new_anomaly_id()
        description = f"Last stop of route {route_id} departs {injected} after shift end {row['shift_end']} but is still delivered"
        set_cell(tables["delivery_outcome"], "outcome_id", row["outcome_id"], "actual_departure", injected)
        work.add_label(anomaly_id, issue_type, "delivery_outcome", row["outcome_id"], "actual_departure", row["actual_departure"], injected, description)
        events = tables["delivery_status_event"]
        event = events[(events["delivery_id"] == row["delivery_id"]) & (events["status"] == "delivered")].iloc[0]
        events.at[event.name, "event_time"] = injected
        work.add_label(anomaly_id, issue_type, "delivery_status_event", event["event_id"], "event_time", event["event_time"], injected, description)


def inject_outside_region(work):
    issue_type = "COORDINATE_OUTSIDE_REGION"
    sites = work.tables["customer_site"]
    customers = sites.loc[sites["site_type"] == "customer", "site_id"]
    for site_id in work.choose(customers, target_count(issue_type, len(sites))):
        axis = str(work.rng.choice(["lat", "lon"]))
        direction = int(work.rng.choice([-1, 1]))
        offset = work.rng.uniform(*COORDINATE_OFFSET_DEGREES)
        bound = REGION_BOUNDS[f"{axis}_{'max' if direction > 0 else 'min'}"]
        injected = round(bound + direction * offset, 6)
        original = set_cell(sites, "site_id", site_id, axis, injected)
        description = f"Site {site_id} {axis} moved outside the region bounds"
        work.add_label(work.new_anomaly_id(), issue_type, "customer_site", site_id, axis, original, injected, description)


def inject_anomalies(rng, tables):
    sites = tables["customer_site"]
    site_index = pd.Series(np.arange(len(sites)), index=sites["site_id"])
    travel = build_travel_times(site_index, tables["travel_time_matrix"], tables["traffic_scenario"])
    work = Workspace(rng, {name: table.copy() for name, table in tables.items()}, travel, site_index)
    inject_route_capacity(work)
    inject_stop_errors(work)
    inject_arrival_before_departure(work)
    inject_shift_exceeded(work)
    inject_outside_region(work)
    return work.tables, pd.DataFrame(work.labels, columns=LABEL_COLUMNS)
