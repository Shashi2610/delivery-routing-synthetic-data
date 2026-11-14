import numpy as np
import pandas as pd

from generator import ids
from generator.config import (
    BAND_SPEEDS_KMH,
    CIRCUITY_FACTOR,
    DATE_FORMAT,
    DISTANCE_BAND_EDGES_KM,
    START_DATE,
)

EARTH_RADIUS_KM = 6371.0088
MIN_DISTANCE_KM = 0.05

HOUR_BAND_BASE_FACTORS = {
    "00-06": 0.90,
    "06-10": 1.45,
    "10-16": 1.10,
    "16-20": 1.55,
    "20-24": 1.00,
}
HOUR_BAND_START_MINUTES = (0, 360, 600, 960, 1200)
WEEKEND_MULTIPLIER = 0.90
INCIDENT_DAY_SHARE = 0.10
INCIDENT_MULTIPLIER = 1.25
INCIDENT_BANDS = ("06-10", "10-16", "16-20")
NOISE_SIGMA = 0.04
FACTOR_RANGE = (0.8, 2.0)
FIRST_WEEKEND_WEEKDAY = 5


def haversine_matrix_km(lat, lon):
    lat_radians = np.radians(lat)
    lon_radians = np.radians(lon)
    half_lat = (lat_radians[:, None] - lat_radians[None, :]) / 2
    half_lon = (lon_radians[:, None] - lon_radians[None, :]) / 2
    haversine = np.sin(half_lat) ** 2 + np.cos(lat_radians)[:, None] * np.cos(lat_radians)[None, :] * np.sin(half_lon) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(haversine))


def build_travel_time_matrix(sites):
    straight_line = haversine_matrix_km(sites["lat"].to_numpy(), sites["lon"].to_numpy())
    distance = np.maximum(straight_line * CIRCUITY_FACTOR, MIN_DISTANCE_KM).round(3)
    speed = np.array(BAND_SPEEDS_KMH)[np.searchsorted(DISTANCE_BAND_EDGES_KM, distance, side="right")]
    base_minutes = (distance / speed * 60).round(2)
    from_index, to_index = np.nonzero(~np.eye(len(sites), dtype=bool))
    site_ids = sites["site_id"].to_numpy()
    return pd.DataFrame({
        "from_site_id": site_ids[from_index],
        "to_site_id": site_ids[to_index],
        "distance_km": distance[from_index, to_index],
        "base_travel_minutes": base_minutes[from_index, to_index],
    })


def build_traffic_scenarios(rng, days):
    bands = list(HOUR_BAND_BASE_FACTORS)
    day_index = np.repeat(np.arange(days), len(bands))
    band_names = np.tile(bands, days)
    dates = pd.Timestamp(START_DATE) + pd.to_timedelta(day_index, unit="D")
    incident_days = rng.choice(days, size=round(INCIDENT_DAY_SHARE * days), replace=False)
    is_weekend = dates.weekday >= FIRST_WEEKEND_WEEKDAY
    is_incident = np.isin(day_index, incident_days) & np.isin(band_names, INCIDENT_BANDS)
    factor = (
        np.array(list(HOUR_BAND_BASE_FACTORS.values()))[np.tile(np.arange(len(bands)), days)]
        * np.where(is_weekend, WEEKEND_MULTIPLIER, 1.0)
        * np.where(is_incident, INCIDENT_MULTIPLIER, 1.0)
        * (1 + rng.normal(0, NOISE_SIGMA, len(day_index)))
    )
    return pd.DataFrame({
        "scenario_id": ids.assign_yearly(ids.scenario_id, dates.year),
        "scenario_date": dates.strftime(DATE_FORMAT),
        "hour_band": band_names,
        "traffic_factor": factor.clip(*FACTOR_RANGE).round(2),
    })
