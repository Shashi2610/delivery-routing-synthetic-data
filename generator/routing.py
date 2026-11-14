import bisect
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from generator import ids
from generator.config import DATE_FORMAT, TIMESTAMP_FORMAT
from generator.transactions import add_minutes, assign_event_ids, minutes_of_day
from generator.travel import HOUR_BAND_BASE_FACTORS, HOUR_BAND_START_MINUTES

PRIORITY_RANK = {"critical": 0, "high": 1, "normal": 2, "low": 3}
UNSERVED_REASON_ORDER = ("VEHICLE_RESTRICTED", "CAPACITY", "LATE_MISSED_WINDOW", "SHIFT_EXCEEDED")
PLANNING_CUTOFF_MINUTES = 5 * 60


@dataclass
class DeliveryRecord:
    delivery_id: str
    day: str
    hub_id: str
    site_index: int
    weight_kg: float
    volume_m3: float
    units: int
    service_minutes: int
    earliest: int
    latest: int
    priority_rank: int
    needs_refrigeration: bool
    site_class: str
    allowed_types: set


@dataclass
class Visit:
    leg_minutes: int
    start: int
    departure: int
    return_minutes: int


@dataclass
class ShiftPlan:
    shift_id: str
    day: str
    hub_id: str
    hub_index: int
    vehicle_type: str
    restriction_code: str
    max_weight_kg: float
    max_volume_m3: float
    max_units: int
    start: int
    end: int
    max_driving: int
    location: int
    clock: int
    return_minutes: int = 0
    driving: int = 0
    weight_kg: float = 0.0
    volume_m3: float = 0.0
    units: int = 0
    stops: list = field(default_factory=list)


class TravelTimes:
    def __init__(self, base_minutes, factors_by_date):
        self.base_minutes = base_minutes
        self.factors_by_date = factors_by_date

    def minutes(self, day, from_index, to_index, depart):
        band = bisect.bisect_right(HOUR_BAND_START_MINUTES, depart) - 1
        actual = self.base_minutes[from_index, to_index] * self.factors_by_date[day][band]
        return math.ceil(round(actual, 6))


def build_travel_times(site_index, matrix, scenarios):
    count = len(site_index)
    base_minutes = np.zeros((count, count))
    rows = site_index.loc[matrix["from_site_id"]].to_numpy()
    columns = site_index.loc[matrix["to_site_id"]].to_numpy()
    base_minutes[rows, columns] = matrix["base_travel_minutes"].to_numpy()
    wide = scenarios.pivot(index="scenario_date", columns="hour_band", values="traffic_factor")
    wide = wide[list(HOUR_BAND_BASE_FACTORS)]
    return TravelTimes(base_minutes, {day: row.tolist() for day, row in wide.iterrows()})


def parse_allowed_types(text):
    return set(text.split("|")) if isinstance(text, str) else None


def build_delivery_records(tables, site_index):
    table = (
        tables["delivery"]
        .merge(tables["order"][["order_id", "site_id", "requested_date", "requires_refrigeration"]], on="order_id")
        .merge(tables["time_window"][["delivery_id", "earliest_arrival", "latest_arrival", "priority"]], on="delivery_id")
        .merge(tables["customer_site"][["site_id", "hub_id", "site_class", "allowed_vehicle_types"]], on="site_id")
    )
    earliest = minutes_of_day(table["earliest_arrival"].str[11:16])
    latest = minutes_of_day(table["latest_arrival"].str[11:16])
    return [
        DeliveryRecord(
            delivery_id=row.delivery_id,
            day=row.requested_date,
            hub_id=row.hub_id,
            site_index=int(site_index[row.site_id]),
            weight_kg=row.weight_kg,
            volume_m3=row.volume_m3,
            units=row.units,
            service_minutes=row.service_minutes,
            earliest=int(early),
            latest=int(late),
            priority_rank=PRIORITY_RANK[row.priority],
            needs_refrigeration=bool(row.requires_refrigeration),
            site_class=row.site_class,
            allowed_types=parse_allowed_types(row.allowed_vehicle_types),
        )
        for row, early, late in zip(table.itertuples(index=False), earliest, latest)
    ]


def build_shift_plans(tables, site_index):
    shifts = tables["shift"].merge(tables["vehicle"], on="vehicle_id").merge(tables["vehicle_capacity"], on="vehicle_id")
    shifts["day"] = shifts["shift_start"].str[:10]
    in_effect = (shifts["effective_from"] <= shifts["day"]) & (shifts["day"] <= shifts["effective_to"].fillna("9999-12-31"))
    shifts = shifts[in_effect].sort_values(["day", "home_hub_id", "shift_start", "shift_id"])
    starts = minutes_of_day(shifts["shift_start"].str[11:16])
    ends = minutes_of_day(shifts["shift_end"].str[11:16])
    return [
        ShiftPlan(
            shift_id=row.shift_id,
            day=row.day,
            hub_id=row.home_hub_id,
            hub_index=int(site_index[row.home_hub_id]),
            vehicle_type=row.vehicle_type,
            restriction_code=row.restriction_code,
            max_weight_kg=row.max_weight_kg,
            max_volume_m3=row.max_volume_m3,
            max_units=row.max_units,
            start=int(start),
            end=int(end),
            max_driving=row.max_driving_minutes,
            location=int(site_index[row.home_hub_id]),
            clock=int(start),
        )
        for row, start, end in zip(shifts.itertuples(index=False), starts, ends)
    ]


def group_by_day_and_hub(items):
    groups = {}
    for item in items:
        groups.setdefault((item.day, item.hub_id), []).append(item)
    return groups


def sort_for_planning(records):
    return sorted(records, key=lambda record: (record.priority_rank, record.earliest, record.delivery_id))


def violates_restrictions(plan, delivery):
    if delivery.needs_refrigeration and plan.vehicle_type != "refrigerated":
        return True
    if delivery.allowed_types is not None and plan.vehicle_type not in delivery.allowed_types:
        return True
    return plan.restriction_code == "NO_RESIDENTIAL" and delivery.site_class == "residential"


def exceeds_capacity(plan, delivery):
    return (
        plan.weight_kg + delivery.weight_kg > plan.max_weight_kg
        or plan.volume_m3 + delivery.volume_m3 > plan.max_volume_m3
        or plan.units + delivery.units > plan.max_units
    )


def check_visit(plan, delivery, travel):
    if violates_restrictions(plan, delivery):
        return "VEHICLE_RESTRICTED", None
    if exceeds_capacity(plan, delivery):
        return "CAPACITY", None
    leg = travel.minutes(plan.day, plan.location, delivery.site_index, plan.clock)
    start = max(plan.clock + leg, delivery.earliest)
    if start > delivery.latest:
        return "LATE_MISSED_WINDOW", None
    departure = start + delivery.service_minutes
    back = travel.minutes(plan.day, delivery.site_index, plan.hub_index, departure)
    if departure + back > plan.end or plan.driving + leg + back > plan.max_driving:
        return "SHIFT_EXCEEDED", None
    return None, Visit(leg, start, departure, back)


def add_stop(plan, delivery, visit):
    plan.stops.append((delivery.delivery_id, visit.start, visit.departure))
    plan.location = delivery.site_index
    plan.clock = visit.departure
    plan.driving += visit.leg_minutes
    plan.return_minutes = visit.return_minutes
    plan.weight_kg += delivery.weight_kg
    plan.volume_m3 += delivery.volume_m3
    plan.units += delivery.units


def cheapest_feasible(plan, pending, travel):
    best = None
    best_extra = None
    for delivery in pending:
        reason, visit = check_visit(plan, delivery, travel)
        if reason is not None:
            continue
        extra = visit.leg_minutes + visit.return_minutes - plan.return_minutes
        if best is None or extra < best_extra:
            best, best_extra = (delivery, visit), extra
    return best


def fill_shift(plan, pending, travel):
    choice = cheapest_feasible(plan, pending, travel)
    while choice is not None:
        delivery, visit = choice
        add_stop(plan, delivery, visit)
        pending.remove(delivery)
        choice = cheapest_feasible(plan, pending, travel)


def unserved_reason(delivery, plans, travel):
    reasons = [check_visit(plan, delivery, travel)[0] for plan in plans]
    return max(reasons, key=UNSERVED_REASON_ORDER.index)


def plan_hub_day(plans, pending, travel):
    for plan in plans:
        fill_shift(plan, pending, travel)
    return {delivery.delivery_id: unserved_reason(delivery, plans, travel) for delivery in pending}


def minutes_to_text(days, minutes):
    return pd.DatetimeIndex(add_minutes(pd.to_datetime(days), minutes)).strftime(TIMESTAMP_FORMAT)


def build_route_tables(plans):
    used = [plan for plan in plans if plan.stops]
    years = pd.to_datetime([plan.day for plan in used]).year
    route_ids = ids.assign_yearly(ids.route_id, years)
    routes = pd.DataFrame({
        "route_id": route_ids,
        "shift_id": [plan.shift_id for plan in used],
        "hub_id": [plan.hub_id for plan in used],
        "route_date": [plan.day for plan in used],
        "planned_start": minutes_to_text([plan.day for plan in used], [plan.start for plan in used]),
    })
    stop_rows = [
        (route_id, plan.day, number, delivery_id, arrival, departure)
        for route_id, plan in zip(route_ids, used)
        for number, (delivery_id, arrival, departure) in enumerate(plan.stops, start=1)
    ]
    stops = pd.DataFrame(stop_rows, columns=["route_id", "day", "sequence_no", "delivery_id", "arrival", "departure"])
    stops.insert(0, "stop_id", [ids.stop_id(r, n) for r, n in zip(stops["route_id"], stops["sequence_no"])])
    stops["planned_arrival"] = minutes_to_text(stops["day"], stops["arrival"])
    stops["planned_departure"] = minutes_to_text(stops["day"], stops["departure"])
    stops = stops[["stop_id", "route_id", "sequence_no", "delivery_id", "planned_arrival", "planned_departure"]]
    return routes, stops


def append_routing_events(planned, day_of, route_of, reason_of):
    delivery_ids = planned["delivery_id"]
    cutoff = add_minutes(pd.to_datetime(delivery_ids.map(day_of)), PLANNING_CUTOFF_MINUTES)
    event_time = np.maximum(pd.to_datetime(planned["event_time"]).to_numpy(), cutoff)
    new_events = pd.DataFrame({
        "event_id": None,
        "delivery_id": delivery_ids,
        "event_seq": planned["event_seq"] + 1,
        "status": np.where(delivery_ids.isin(list(reason_of)), "unserved", "assigned"),
        "event_time": pd.DatetimeIndex(event_time).strftime(TIMESTAMP_FORMAT),
        "route_id": delivery_ids.map(route_of),
        "reason_code": delivery_ids.map(reason_of),
    })
    return assign_event_ids(pd.concat([planned, new_events], ignore_index=True))


def plan_routes(tables):
    sites = tables["customer_site"]
    site_index = pd.Series(np.arange(len(sites)), index=sites["site_id"])
    travel = build_travel_times(site_index, tables["travel_time_matrix"], tables["traffic_scenario"])
    records = build_delivery_records(tables, site_index)
    plans = build_shift_plans(tables, site_index)
    pending_by_group = group_by_day_and_hub(sort_for_planning(records))
    unserved = {}
    for group, hub_plans in group_by_day_and_hub(plans).items():
        unserved.update(plan_hub_day(hub_plans, pending_by_group.get(group, []), travel))
    routes, stops = build_route_tables(plans)
    route_of = dict(zip(stops["delivery_id"], stops["route_id"]))
    events = append_routing_events(
        tables["delivery_status_event"], {record.delivery_id: record.day for record in records}, route_of, unserved
    )
    return {"route": routes, "route_stop": stops, "delivery_status_event": events}
