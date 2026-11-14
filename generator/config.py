from datetime import date

DEFAULT_SEED = 20261022

START_DATE = date(2026, 11, 2)

HUB_SHARES = (0.30, 0.25, 0.20, 0.15, 0.10)

SCALES = {
    "starter": {"sites": 50, "deliveries": 200, "vehicles": 10, "drivers": 12, "days": 3},
    "full": {"sites": 500, "deliveries": 2000, "vehicles": 100, "drivers": 120, "days": 30},
}

REGION_BOUNDS = {
    "lat_min": 40.60,
    "lat_max": 40.90,
    "lon_min": -74.05,
    "lon_max": -73.75,
}
