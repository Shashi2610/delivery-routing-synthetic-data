from datetime import date

DEFAULT_SEED = 20261022

START_DATE = date(2026, 11, 2)

DATE_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"

HUB_SHARES = (0.30, 0.25, 0.20, 0.15, 0.10)

SCALES = {
    "starter": {"sites": 50, "deliveries": 200, "vehicles": 10, "drivers": 12, "days": 3, "availability": {"weekday": 1.0, "weekend": 1.0}},
    "full": {"sites": 500, "deliveries": 2000, "vehicles": 100, "drivers": 120, "days": 30, "availability": {"weekday": 0.40, "weekend": 0.15}},
}

REGION_BOUNDS = {
    "lat_min": 40.60,
    "lat_max": 40.90,
    "lon_min": -74.05,
    "lon_max": -73.75,
}

TRAVEL_NOISE_SIGMA = 0.60
SERVICE_NOISE_SIGMA = 0.35
INCIDENT_DELAY_MULTIPLIER = 2.0
LATE_GRACE_MINUTES = 5

ANOMALY_MIN_COUNT = 3
ANOMALY_RATES = {
    "ROUTE_CAPACITY_EXCEEDED": 0.03,
    "STOP_OMITTED_OR_DUPLICATED": 0.03,
    "ARRIVAL_BEFORE_PREVIOUS_DEPARTURE": 0.02,
    "DRIVER_SHIFT_EXCEEDED": 0.03,
    "COORDINATE_OUTSIDE_REGION": 0.04,
}
ARRIVAL_EARLY_MINUTES = (5, 15)
SHIFT_OVERRUN_MINUTES = (5, 45)
COORDINATE_OFFSET_DEGREES = (0.02, 0.15)

CIRCUITY_FACTOR = 1.3
DISTANCE_BAND_EDGES_KM = (3, 10, 25)
BAND_SPEEDS_KMH = (25, 35, 45, 55)
