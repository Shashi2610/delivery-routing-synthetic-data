import numpy as np
import pandas as pd

from generator import ids
from generator.config import DATE_FORMAT, START_DATE, TIMESTAMP_FORMAT
from generator.rng import pick

SPLIT_DELIVERY_SHARE = 0.10
REFRIGERATED_ORDER_SHARE = 0.10
SITE_POPULARITY_SIGMA = 0.8
WEEKDAY_WEIGHTS = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.4, 0.2])

WEIGHT_MEDIAN_KG = 35
WEIGHT_SIGMA = 0.9
LARGE_DEMAND_SHARE = 0.05
LARGE_DEMAND_MULTIPLIER = (3.0, 6.0)
DENSITY_MEDIAN_M3_PER_KG = 0.012
DENSITY_SIGMA = 0.3
ITEM_WEIGHT_MEDIAN_KG = 5
ITEM_WEIGHT_SIGMA = 0.4
WEIGHT_RANGE_KG = (0.5, 500)
VOLUME_RANGE_M3 = (0.01, 4)
UNITS_RANGE = (1, 40)

LEAD_DAYS_RANGE = (1, 3)
SAME_DAY_ORDER_MINUTES = (0, 5 * 60)
EARLIER_DAY_ORDER_MINUTES = (6 * 60, 18 * 60)
PLANNING_DELAY_MINUTES = (5, 120)

SERVICE_BASE_MINUTES = {"residential": 6, "commercial": 10, "industrial": 15}
SERVICE_MINUTES_PER_KG = 0.05
SERVICE_NOISE_MINUTES = 1.5
SERVICE_RANGE_MINUTES = (2, 60)

WINDOW_TYPE_SHARES = {"morning": 0.35, "afternoon": 0.35, "all_day": 0.30}
WINDOW_START_MINUTES = {
    "morning": list(range(7 * 60, 10 * 60 + 1, 15)),
    "afternoon": list(range(12 * 60, 15 * 60 + 1, 15)),
    "all_day": [7 * 60, 8 * 60, 9 * 60, 10 * 60],
}
WINDOW_WIDTH_MINUTES = {
    "morning": (120, 150, 180, 240),
    "afternoon": (120, 150, 180, 240),
    "all_day": (420, 480),
}
MIN_WINDOW_MINUTES = 30
PRIORITY_SHARES = {"normal": 0.70, "low": 0.15, "high": 0.12, "critical": 0.03}

DELIVERY_COLUMNS = ["delivery_id", "order_id", "weight_kg", "volume_m3", "units", "service_minutes"]


def add_minutes(days, minutes):
    return np.asarray(days, dtype="datetime64[ns]") + np.asarray(minutes) * np.timedelta64(1, "m")


def minutes_of_day(times):
    return (pd.to_timedelta(times + ":00").dt.total_seconds() // 60).to_numpy().astype(int)


def draw_request_days(rng, count, days):
    weekday = (np.arange(days) + START_DATE.weekday()) % 7
    weights = WEEKDAY_WEIGHTS[weekday]
    chosen = rng.choice(days, size=count, p=weights / weights.sum())
    return pd.Timestamp(START_DATE).to_datetime64() + chosen * np.timedelta64(1, "D")


def draw_order_datetimes(rng, requested_days):
    count = len(requested_days)
    first_day = pd.Timestamp(START_DATE).to_datetime64()
    lead = rng.integers(LEAD_DAYS_RANGE[0], LEAD_DAYS_RANGE[1] + 1, count)
    order_days = np.maximum(requested_days - lead * np.timedelta64(1, "D"), first_day)
    same_day_minutes = rng.integers(*SAME_DAY_ORDER_MINUTES, count)
    earlier_day_minutes = rng.integers(*EARLIER_DAY_ORDER_MINUTES, count)
    minutes = np.where(order_days == requested_days, same_day_minutes, earlier_day_minutes)
    return add_minutes(order_days, minutes)


def draw_order_sites(rng, sites, count):
    customers = sites.loc[sites["site_type"] == "customer", "site_id"].to_numpy()
    popularity = rng.lognormal(0, SITE_POPULARITY_SIGMA, len(customers))
    return rng.choice(customers, size=count, p=popularity / popularity.sum())


def draw_raw_orders(rng, sites, delivery_count, days):
    split_count = round(SPLIT_DELIVERY_SHARE * delivery_count)
    order_count = delivery_count - split_count
    parts = np.ones(order_count, dtype=int)
    parts[rng.choice(order_count, size=split_count, replace=False)] = 2
    requested_days = draw_request_days(rng, order_count, days)
    raw = pd.DataFrame({
        "site_id": draw_order_sites(rng, sites, order_count),
        "requested_day": requested_days,
        "order_datetime": draw_order_datetimes(rng, requested_days),
        "requires_refrigeration": rng.random(order_count) < REFRIGERATED_ORDER_SHARE,
        "parts": parts,
    })
    raw = raw.sort_values("order_datetime", kind="stable", ignore_index=True)
    raw["order_id"] = ids.assign_yearly(ids.order_id, raw["order_datetime"].dt.year)
    return raw


def draw_loads(rng, count):
    weight = rng.lognormal(np.log(WEIGHT_MEDIAN_KG), WEIGHT_SIGMA, count)
    is_large = rng.random(count) < LARGE_DEMAND_SHARE
    weight[is_large] *= rng.uniform(*LARGE_DEMAND_MULTIPLIER, is_large.sum())
    weight = weight.clip(*WEIGHT_RANGE_KG).round(2)
    density = rng.lognormal(np.log(DENSITY_MEDIAN_M3_PER_KG), DENSITY_SIGMA, count)
    item_weight = rng.lognormal(np.log(ITEM_WEIGHT_MEDIAN_KG), ITEM_WEIGHT_SIGMA, count)
    volume = (weight * density).clip(*VOLUME_RANGE_M3).round(3)
    units = np.round(weight / item_weight).clip(*UNITS_RANGE).astype(int)
    return weight, volume, units


def draw_service_minutes(rng, site_class, weight):
    base = site_class.map(SERVICE_BASE_MINUTES).to_numpy()
    noise = rng.normal(0, SERVICE_NOISE_MINUTES, len(weight))
    return np.round(base + SERVICE_MINUTES_PER_KG * weight + noise).clip(*SERVICE_RANGE_MINUTES).astype(int)


def build_deliveries(rng, sites, raw):
    deliveries = raw.loc[raw.index.repeat(raw["parts"]), ["order_id", "site_id", "requested_day"]]
    deliveries = deliveries.reset_index(drop=True)
    weight, volume, units = draw_loads(rng, len(deliveries))
    site_class = deliveries["site_id"].map(sites.set_index("site_id")["site_class"])
    deliveries["delivery_id"] = ids.assign_yearly(ids.delivery_id, deliveries["requested_day"].dt.year)
    deliveries["weight_kg"] = weight
    deliveries["volume_m3"] = volume
    deliveries["units"] = units
    deliveries["service_minutes"] = draw_service_minutes(rng, site_class, weight)
    return deliveries


def build_orders(raw, deliveries):
    totals = deliveries.groupby("order_id")[["weight_kg", "volume_m3", "units"]].sum()
    orders = raw.join(totals, on="order_id")
    return pd.DataFrame({
        "order_id": orders["order_id"],
        "site_id": orders["site_id"],
        "order_datetime": orders["order_datetime"].dt.strftime(TIMESTAMP_FORMAT),
        "requested_date": orders["requested_day"].dt.strftime(DATE_FORMAT),
        "weight_kg": orders["weight_kg"].round(2),
        "volume_m3": orders["volume_m3"].round(3),
        "units": orders["units"],
        "requires_refrigeration": orders["requires_refrigeration"],
    })


def build_orders_and_deliveries(rng, sites, delivery_count, days):
    raw = draw_raw_orders(rng, sites, delivery_count, days)
    deliveries = build_deliveries(rng, sites, raw)
    return build_orders(raw, deliveries), deliveries[DELIVERY_COLUMNS]


def draw_window_shape(rng, window_type):
    start = np.zeros(len(window_type), dtype=int)
    width = np.zeros(len(window_type), dtype=int)
    for name in WINDOW_TYPE_SHARES:
        mask = window_type == name
        start[mask] = rng.choice(WINDOW_START_MINUTES[name], size=mask.sum())
        width[mask] = rng.choice(WINDOW_WIDTH_MINUTES[name], size=mask.sum())
    return start, width


def fit_to_site_hours(start, width, opens, closes):
    earliest = np.maximum(start, opens)
    latest = np.minimum(start + width, closes)
    too_narrow = latest - earliest < MIN_WINDOW_MINUTES
    earliest[too_narrow] = np.maximum(opens, closes - width)[too_narrow]
    latest[too_narrow] = closes[too_narrow]
    return earliest, latest


def build_time_windows(rng, deliveries, orders, sites):
    context = deliveries[["delivery_id", "order_id"]]
    context = context.merge(orders[["order_id", "site_id", "requested_date"]], on="order_id", how="left")
    context = context.merge(sites[["site_id", "open_time", "close_time"]], on="site_id", how="left")
    window_type = pick(rng, WINDOW_TYPE_SHARES, len(context))
    start, width = draw_window_shape(rng, window_type)
    earliest, latest = fit_to_site_hours(
        start, width, minutes_of_day(context["open_time"]), minutes_of_day(context["close_time"])
    )
    days = pd.to_datetime(context["requested_date"])
    return pd.DataFrame({
        "window_id": ids.assign_yearly(ids.window_id, days.dt.year),
        "delivery_id": context["delivery_id"],
        "earliest_arrival": pd.DatetimeIndex(add_minutes(days, earliest)).strftime(TIMESTAMP_FORMAT),
        "latest_arrival": pd.DatetimeIndex(add_minutes(days, latest)).strftime(TIMESTAMP_FORMAT),
        "priority": pick(rng, PRIORITY_SHARES, len(context)),
    })


def build_status_events(rng, deliveries, orders):
    context = deliveries[["delivery_id", "order_id"]]
    context = context.merge(orders[["order_id", "order_datetime"]], on="order_id", how="left")
    delay = rng.integers(PLANNING_DELAY_MINUTES[0], PLANNING_DELAY_MINUTES[1] + 1, len(context))
    event_time = pd.DatetimeIndex(add_minutes(pd.to_datetime(context["order_datetime"]), delay))
    return pd.DataFrame({
        "event_id": ids.assign_yearly(ids.status_event_id, event_time.year),
        "delivery_id": context["delivery_id"],
        "event_seq": 1,
        "status": "planned",
        "event_time": event_time.strftime(TIMESTAMP_FORMAT),
        "route_id": None,
        "reason_code": None,
    })
