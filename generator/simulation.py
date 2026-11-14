import bisect
import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

from generator import ids
from generator.config import (
    INCIDENT_DELAY_MULTIPLIER,
    LATE_GRACE_MINUTES,
    SERVICE_NOISE_SIGMA,
    TIMESTAMP_FORMAT,
    TRAVEL_NOISE_SIGMA,
)
from generator.routing import build_travel_times, minutes_to_text
from generator.transactions import add_minutes, assign_event_ids, minutes_of_day
from generator.travel import HOUR_BAND_BASE_FACTORS, HOUR_BAND_START_MINUTES


@dataclass
class StopResult:
    left_at: int
    arrival: int
    departure: int
    status: str
    reason_code: str


def draw_noise(rng, count, sigma):
    return rng.lognormal(-sigma ** 2 / 2, sigma, count)


def build_incident_lookup(scenarios):
    wide = scenarios.pivot(index="scenario_date", columns="hour_band", values="is_incident")
    wide = wide[list(HOUR_BAND_BASE_FACTORS)]
    return {day: row.tolist() for day, row in wide.iterrows()}


def scaled_minutes(planned_minutes, noise, incident, day, clock):
    band = bisect.bisect_right(HOUR_BAND_START_MINUTES, clock) - 1
    delay = INCIDENT_DELAY_MULTIPLIER if incident[day][band] else 1.0
    return max(0, int(round(planned_minutes * noise * delay)))


def build_stop_table(tables, site_index):
    route = tables["route"][["route_id", "shift_id", "hub_id", "route_date", "planned_start"]]
    route = route.rename(columns={"hub_id": "depot_id"})
    shift = tables["shift"][["shift_id", "shift_start", "shift_end", "max_driving_minutes"]]
    delivery = tables["delivery"][["delivery_id", "order_id", "service_minutes"]]
    window = tables["time_window"][["delivery_id", "earliest_arrival", "latest_arrival"]]
    stops = (
        tables["route_stop"]
        .merge(route, on="route_id")
        .merge(shift, on="shift_id")
        .merge(delivery, on="delivery_id")
        .merge(window, on="delivery_id")
        .merge(tables["order"][["order_id", "site_id"]], on="order_id")
        .merge(tables["customer_site"][["site_id", "close_time"]], on="site_id")
    )
    stops["site_index"] = site_index.loc[stops["site_id"]].to_numpy()
    stops["hub_index"] = site_index.loc[stops["depot_id"]].to_numpy()
    stops["planned_start_min"] = minutes_of_day(stops["planned_start"].str[11:16])
    stops["planned_departure_min"] = minutes_of_day(stops["planned_departure"].str[11:16])
    stops["shift_start_min"] = minutes_of_day(stops["shift_start"].str[11:16])
    stops["shift_end_min"] = minutes_of_day(stops["shift_end"].str[11:16])
    stops["earliest_min"] = minutes_of_day(stops["earliest_arrival"].str[11:16])
    stops["latest_min"] = minutes_of_day(stops["latest_arrival"].str[11:16])
    stops["close_min"] = minutes_of_day(stops["close_time"])
    return stops


def add_noise_columns(rng, stops):
    count = len(stops)
    stops["travel_noise"] = draw_noise(rng, count, TRAVEL_NOISE_SIGMA)
    stops["service_noise"] = draw_noise(rng, count, SERVICE_NOISE_SIGMA)
    stops["return_noise"] = draw_noise(rng, count, TRAVEL_NOISE_SIGMA)
    return stops


def simulate_route(stops, travel, incident):
    first = stops[0]
    clock = first.shift_start_min
    location = first.hub_index
    planned_clock = first.planned_start_min
    planned_location = first.hub_index
    driving = 0
    stopped = False
    results = []
    for stop in stops:
        left_at = clock
        if stopped:
            results.append(StopResult(left_at, None, None, "failed", "SHIFT_EXCEEDED"))
            continue
        planned_leg = travel.minutes(stop.route_date, planned_location, stop.site_index, planned_clock)
        leg = scaled_minutes(planned_leg, stop.travel_noise, incident, stop.route_date, clock)
        arrival = max(clock + leg, stop.earliest_min)
        service = max(1, int(round(stop.service_minutes * stop.service_noise)))
        finish = arrival + service
        planned_back = travel.minutes(stop.route_date, stop.site_index, stop.hub_index, stop.planned_departure_min)
        back = scaled_minutes(planned_back, stop.return_noise, incident, stop.route_date, finish)
        if finish + back > stop.shift_end_min or driving + leg + back > stop.max_driving_minutes:
            stopped = True
            results.append(StopResult(left_at, None, None, "failed", "SHIFT_EXCEEDED"))
            continue
        if arrival > stop.close_min:
            status, reason, departure = "failed", "SITE_CLOSED", arrival
        elif arrival > stop.latest_min + LATE_GRACE_MINUTES:
            status, reason, departure = "failed", "LATE_MISSED_WINDOW", arrival
        else:
            status, reason, departure = "delivered", None, finish
        results.append(StopResult(left_at, arrival, departure, status, reason))
        driving += leg
        location, clock = stop.site_index, departure
        planned_location, planned_clock = stop.site_index, stop.planned_departure_min
    return results


def simulate_routes(stops, travel, incident):
    results = []
    for _, route_stops in itertools.groupby(stops.itertuples(index=False), key=lambda stop: stop.route_id):
        results.extend(simulate_route(list(route_stops), travel, incident))
    return results


def optional_text(days, minutes):
    present = np.array([minute is not None for minute in minutes])
    text = np.full(len(minutes), None, dtype=object)
    text[present] = minutes_to_text(np.asarray(days)[present], [m for m in minutes if m is not None])
    return text


def build_outcomes(stops, results):
    days = stops["route_date"].tolist()
    years = pd.to_datetime(stops["route_date"]).dt.year
    return pd.DataFrame({
        "outcome_id": ids.assign_yearly(ids.outcome_id, years),
        "stop_id": stops["stop_id"],
        "delivery_id": stops["delivery_id"],
        "attempt_no": 1,
        "actual_arrival": optional_text(days, [result.arrival for result in results]),
        "actual_departure": optional_text(days, [result.departure for result in results]),
        "status": [result.status for result in results],
        "reason_code": [result.reason_code for result in results],
    })


def build_event_rows(stops, sequence, status, times, reasons):
    return pd.DataFrame({
        "event_id": None,
        "delivery_id": stops["delivery_id"].to_numpy(),
        "event_seq": sequence,
        "status": status,
        "event_time": pd.DatetimeIndex(times).strftime(TIMESTAMP_FORMAT),
        "route_id": stops["route_id"].to_numpy(),
        "reason_code": reasons,
    })


def append_execution_events(events, stops, results):
    latest = events.sort_values("event_seq").groupby("delivery_id").tail(1).set_index("delivery_id")
    previous = latest.loc[stops["delivery_id"]]
    days = pd.to_datetime(stops["route_date"])
    left_at = [result.left_at for result in results]
    ended_at = [left if result.departure is None else result.departure for left, result in zip(left_at, results)]
    in_transit_time = np.maximum(add_minutes(days, left_at), pd.to_datetime(previous["event_time"]).to_numpy())
    ended_time = np.maximum(add_minutes(days, ended_at), in_transit_time)
    sequence = previous["event_seq"].to_numpy()
    in_transit = build_event_rows(stops, sequence + 1, "in_transit", in_transit_time, None)
    ended = build_event_rows(stops, sequence + 2, [result.status for result in results], ended_time, None)
    return assign_event_ids(pd.concat([events, in_transit, ended], ignore_index=True))


def count_late_deliveries(outcomes, windows):
    delivered = outcomes[outcomes["status"] == "delivered"]
    delivered = delivered.merge(windows[["delivery_id", "latest_arrival"]], on="delivery_id")
    return int((delivered["actual_arrival"] > delivered["latest_arrival"]).sum())


def simulate_execution(rng, tables):
    sites = tables["customer_site"]
    site_index = pd.Series(np.arange(len(sites)), index=sites["site_id"])
    travel = build_travel_times(site_index, tables["travel_time_matrix"], tables["traffic_scenario"])
    incident = build_incident_lookup(tables["traffic_scenario"])
    stops = add_noise_columns(rng, build_stop_table(tables, site_index))
    results = simulate_routes(stops, travel, incident)
    return {
        "delivery_outcome": build_outcomes(stops, results),
        "delivery_status_event": append_execution_events(tables["delivery_status_event"], stops, results),
    }
