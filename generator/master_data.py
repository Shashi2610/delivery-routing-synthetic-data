import math

import numpy as np
import pandas as pd

from generator import ids
from generator.config import HUB_SHARES, REGION_BOUNDS, START_DATE

DATE_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"

HUB_MARGIN_SHARE = 0.20
SITE_SPREAD_DEGREES = 0.03
RESTRICTED_SITE_SHARE = 0.10
HEAVY_DRIVER_RATIO = 1.3

SITE_CLASS_SHARES = {"residential": 0.50, "commercial": 0.35, "industrial": 0.15}
ALLOWED_TYPES_SHARES = {"van": 0.50, "van|refrigerated": 0.25, "van|truck": 0.25}
OPENING_HOURS = {
    "residential": (("07:00", "08:00"), ("20:00", "21:00")),
    "commercial": (("08:00", "09:00"), ("17:00", "18:00")),
    "industrial": (("06:00", "07:00"), ("15:00", "16:00")),
}

VEHICLE_TYPE_SHARES = {"van": 0.55, "truck": 0.25, "refrigerated": 0.20}
RESTRICTION_SHARES = {
    "van": {"NONE": 0.85, "DAYTIME_ONLY": 0.15},
    "truck": {"NONE": 0.50, "NO_RESIDENTIAL": 0.40, "DAYTIME_ONLY": 0.10},
    "refrigerated": {"NONE": 0.80, "NO_RESIDENTIAL": 0.10, "DAYTIME_ONLY": 0.10},
}
CAPACITY_RANGES = {
    "van": {"weight": (600, 1200), "volume": (6, 12), "units": (60, 150)},
    "truck": {"weight": (4000, 10000), "volume": (25, 60), "units": (300, 1000)},
    "refrigerated": {"weight": (500, 1000), "volume": (5, 10), "units": (40, 120)},
}

SHIFT_START_MINUTES = list(range(6 * 60, 9 * 60 + 1, 30))
SHIFT_LENGTH_MINUTES = (480, 540, 600)
MAX_DRIVING_MINUTES = (360, 420, 480)
BREAK_MINUTES = (30, 45, 60)
BREAK_AFTER_DRIVING_MINUTES = (180, 240, 270)


def pick(rng, shares, size):
    return rng.choice(list(shares), size=size, p=list(shares.values()))


def hub_ids(sites):
    return sites.loc[sites["site_type"] == "hub", "site_id"].to_numpy()


def dates_before_start(rng, count, min_days, max_days):
    offsets = rng.integers(min_days, max_days + 1, count)
    earlier = pd.Timestamp(START_DATE) - pd.to_timedelta(offsets, unit="D")
    return earlier.strftime(DATE_FORMAT)


def is_inside_region(lat, lon):
    bounds = REGION_BOUNDS
    return (
        (lat >= bounds["lat_min"]) & (lat <= bounds["lat_max"])
        & (lon >= bounds["lon_min"]) & (lon <= bounds["lon_max"])
    )


def offsets_inside_region(rng, center_lat, center_lon):
    lat = center_lat.copy()
    lon = center_lon.copy()
    pending = np.ones(len(lat), dtype=bool)
    while pending.any():
        count = pending.sum()
        lat[pending] = center_lat[pending] + rng.normal(0, SITE_SPREAD_DEGREES, count)
        lon[pending] = center_lon[pending] + rng.normal(0, SITE_SPREAD_DEGREES, count)
        pending = ~is_inside_region(lat, lon)
    return lat, lon


def draw_opening_times(rng, site_class):
    opens = np.empty(len(site_class), dtype=object)
    closes = np.empty(len(site_class), dtype=object)
    for name, (open_options, close_options) in OPENING_HOURS.items():
        mask = site_class == name
        opens[mask] = rng.choice(open_options, size=mask.sum())
        closes[mask] = rng.choice(close_options, size=mask.sum())
    return opens, closes


def build_hub_rows(rng):
    bounds = REGION_BOUNDS
    lat_margin = (bounds["lat_max"] - bounds["lat_min"]) * HUB_MARGIN_SHARE
    lon_margin = (bounds["lon_max"] - bounds["lon_min"]) * HUB_MARGIN_SHARE
    count = len(HUB_SHARES)
    return pd.DataFrame({
        "site_id": [ids.site_id(n) for n in range(1, count + 1)],
        "site_type": "hub",
        "site_class": "industrial",
        "lat": rng.uniform(bounds["lat_min"] + lat_margin, bounds["lat_max"] - lat_margin, count).round(6),
        "lon": rng.uniform(bounds["lon_min"] + lon_margin, bounds["lon_max"] - lon_margin, count).round(6),
        "hub_id": None,
        "restricts_vehicle_types": False,
        "allowed_vehicle_types": None,
        "open_time": "05:00",
        "close_time": "22:00",
    })


def build_customer_rows(rng, hubs, count):
    hub_index = rng.choice(len(hubs), size=count, p=HUB_SHARES)
    lat, lon = offsets_inside_region(
        rng, hubs["lat"].to_numpy()[hub_index], hubs["lon"].to_numpy()[hub_index]
    )
    site_class = pick(rng, SITE_CLASS_SHARES, count)
    restricted = rng.random(count) < RESTRICTED_SITE_SHARE
    allowed = np.full(count, None, dtype=object)
    allowed[restricted] = pick(rng, ALLOWED_TYPES_SHARES, restricted.sum())
    opens, closes = draw_opening_times(rng, site_class)
    first_number = len(hubs) + 1
    return pd.DataFrame({
        "site_id": [ids.site_id(n) for n in range(first_number, first_number + count)],
        "site_type": "customer",
        "site_class": site_class,
        "lat": lat.round(6),
        "lon": lon.round(6),
        "hub_id": hubs["site_id"].to_numpy()[hub_index],
        "restricts_vehicle_types": restricted,
        "allowed_vehicle_types": allowed,
        "open_time": opens,
        "close_time": closes,
    })


def build_sites(rng, customer_count):
    hubs = build_hub_rows(rng)
    customers = build_customer_rows(rng, hubs, customer_count)
    return pd.concat([hubs, customers], ignore_index=True)


def build_vehicles(rng, sites, count):
    vehicle_type = pick(rng, VEHICLE_TYPE_SHARES, count)
    restriction = np.empty(count, dtype=object)
    for name, shares in RESTRICTION_SHARES.items():
        mask = vehicle_type == name
        restriction[mask] = pick(rng, shares, mask.sum())
    return pd.DataFrame({
        "vehicle_id": [ids.vehicle_id(n) for n in range(1, count + 1)],
        "vehicle_type": vehicle_type,
        "home_hub_id": rng.choice(hub_ids(sites), size=count, p=HUB_SHARES),
        "restriction_code": restriction,
        "commissioned_date": dates_before_start(rng, count, 30, 1500),
    })


def interpolate_capacity(vehicle_type, position, dimension):
    low = vehicle_type.map(lambda name: CAPACITY_RANGES[name][dimension][0]).to_numpy()
    high = vehicle_type.map(lambda name: CAPACITY_RANGES[name][dimension][1]).to_numpy()
    return low + position * (high - low)


def build_vehicle_capacity(rng, vehicles):
    position = rng.random(len(vehicles))
    vehicle_type = vehicles["vehicle_type"]
    return pd.DataFrame({
        "capacity_id": [ids.capacity_id(n) for n in range(1, len(vehicles) + 1)],
        "vehicle_id": vehicles["vehicle_id"].to_numpy(),
        "max_weight_kg": interpolate_capacity(vehicle_type, position, "weight").round(2),
        "max_volume_m3": interpolate_capacity(vehicle_type, position, "volume").round(2),
        "max_units": interpolate_capacity(vehicle_type, position, "units").round().astype(int),
        "effective_from": vehicles["commissioned_date"].to_numpy(),
        "effective_to": None,
    })


def build_drivers(rng, sites, vehicles, count):
    truck_count = (vehicles["vehicle_type"] == "truck").sum()
    heavy_count = min(count, math.ceil(HEAVY_DRIVER_RATIO * truck_count))
    licence_class = np.full(count, "standard", dtype=object)
    licence_class[rng.choice(count, size=heavy_count, replace=False)] = "heavy"
    return pd.DataFrame({
        "driver_id": [ids.driver_id(n) for n in range(1, count + 1)],
        "home_hub_id": rng.choice(hub_ids(sites), size=count, p=HUB_SHARES),
        "licence_class": licence_class,
        "hire_date": dates_before_start(rng, count, 60, 3000),
    })


def assign_drivers_for_day(rng, drivers, vehicles):
    is_truck = (vehicles["vehicle_type"] == "truck").to_numpy()
    is_heavy = (drivers["licence_class"] == "heavy").to_numpy()
    heavy = rng.permutation(drivers["driver_id"].to_numpy()[is_heavy])
    standard = drivers["driver_id"].to_numpy()[~is_heavy]
    truck_count = is_truck.sum()
    remaining = rng.permutation(np.concatenate([heavy[truck_count:], standard]))
    assigned = np.empty(len(vehicles), dtype=object)
    assigned[is_truck] = heavy[:truck_count]
    assigned[~is_truck] = remaining[:(~is_truck).sum()]
    return assigned


def build_day_shifts(rng, day, drivers, vehicles):
    count = len(vehicles)
    start_minutes = rng.choice(SHIFT_START_MINUTES, size=count)
    length_minutes = rng.choice(SHIFT_LENGTH_MINUTES, size=count)
    shift_start = pd.Timestamp(day) + pd.to_timedelta(start_minutes, unit="m")
    shift_end = shift_start + pd.to_timedelta(length_minutes, unit="m")
    return pd.DataFrame({
        "driver_id": assign_drivers_for_day(rng, drivers, vehicles),
        "vehicle_id": vehicles["vehicle_id"].to_numpy(),
        "shift_start": shift_start.strftime(TIMESTAMP_FORMAT),
        "shift_end": shift_end.strftime(TIMESTAMP_FORMAT),
        "max_driving_minutes": rng.choice(MAX_DRIVING_MINUTES, size=count),
        "break_minutes_required": rng.choice(BREAK_MINUTES, size=count),
        "break_after_driving_minutes": rng.choice(BREAK_AFTER_DRIVING_MINUTES, size=count),
    })


def build_shifts(rng, drivers, vehicles, days):
    first_day = pd.Timestamp(START_DATE)
    day_frames = [
        build_day_shifts(rng, first_day + pd.Timedelta(days=offset), drivers, vehicles)
        for offset in range(days)
    ]
    shifts = pd.concat(day_frames, ignore_index=True)
    years = pd.to_datetime(shifts["shift_start"]).dt.year
    numbers = years.groupby(years).cumcount() + 1
    shifts.insert(0, "shift_id", [ids.shift_id(year, number) for year, number in zip(years, numbers)])
    return shifts
