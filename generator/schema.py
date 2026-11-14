from generator.travel import HOUR_BAND_BASE_FACTORS

TABLES = [
    "customer_site", "vehicle", "vehicle_capacity", "driver", "shift", "travel_time_matrix",
    "traffic_scenario", "order", "delivery", "time_window", "delivery_status_event",
    "route", "route_stop", "delivery_outcome",
]

PRIMARY_KEYS = {
    "customer_site": ["site_id"], "vehicle": ["vehicle_id"], "vehicle_capacity": ["capacity_id"],
    "driver": ["driver_id"], "shift": ["shift_id"], "travel_time_matrix": ["from_site_id", "to_site_id"],
    "traffic_scenario": ["scenario_id"], "order": ["order_id"], "delivery": ["delivery_id"],
    "time_window": ["window_id"], "delivery_status_event": ["event_id"], "route": ["route_id"],
    "route_stop": ["stop_id"], "delivery_outcome": ["outcome_id"],
}

UNIQUE_CONSTRAINTS = [
    ("vehicle_capacity", ["vehicle_id", "effective_from"]),
    ("time_window", ["delivery_id"]),
    ("route_stop", ["route_id", "sequence_no"]),
    ("delivery_outcome", ["stop_id"]),
    ("delivery_outcome", ["delivery_id", "attempt_no"]),
    ("delivery_status_event", ["delivery_id", "event_seq"]),
    ("traffic_scenario", ["scenario_date", "hour_band"]),
]

FOREIGN_KEYS = [
    ("customer_site", "hub_id", "customer_site", "site_id"),
    ("order", "site_id", "customer_site", "site_id"),
    ("delivery", "order_id", "order", "order_id"),
    ("time_window", "delivery_id", "delivery", "delivery_id"),
    ("delivery_status_event", "delivery_id", "delivery", "delivery_id"),
    ("delivery_status_event", "route_id", "route", "route_id"),
    ("vehicle", "home_hub_id", "customer_site", "site_id"),
    ("vehicle_capacity", "vehicle_id", "vehicle", "vehicle_id"),
    ("driver", "home_hub_id", "customer_site", "site_id"),
    ("shift", "driver_id", "driver", "driver_id"),
    ("shift", "vehicle_id", "vehicle", "vehicle_id"),
    ("travel_time_matrix", "from_site_id", "customer_site", "site_id"),
    ("travel_time_matrix", "to_site_id", "customer_site", "site_id"),
    ("route", "shift_id", "shift", "shift_id"),
    ("route", "hub_id", "customer_site", "site_id"),
    ("route_stop", "route_id", "route", "route_id"),
    ("route_stop", "delivery_id", "delivery", "delivery_id"),
    ("delivery_outcome", "stop_id", "route_stop", "stop_id"),
    ("delivery_outcome", "delivery_id", "delivery", "delivery_id"),
]

REASON_CODES = {"LATE_MISSED_WINDOW", "SHIFT_EXCEEDED", "CAPACITY", "SITE_CLOSED", "VEHICLE_RESTRICTED"}
VEHICLE_TYPES = {"van", "truck", "refrigerated"}
DELIVERY_STATUSES = {"planned", "assigned", "unserved", "in_transit", "delivered", "failed"}

ENUMS = [
    ("customer_site", "site_type", {"hub", "customer"}, False),
    ("customer_site", "site_class", {"residential", "commercial", "industrial"}, False),
    ("vehicle", "vehicle_type", VEHICLE_TYPES, False),
    ("vehicle", "restriction_code", {"NONE", "NO_RESIDENTIAL", "DAYTIME_ONLY"}, False),
    ("driver", "licence_class", {"standard", "heavy"}, False),
    ("traffic_scenario", "hour_band", set(HOUR_BAND_BASE_FACTORS), False),
    ("time_window", "priority", {"low", "normal", "high", "critical"}, False),
    ("delivery_outcome", "status", {"delivered", "failed"}, False),
    ("delivery_outcome", "reason_code", REASON_CODES, True),
    ("delivery_status_event", "status", DELIVERY_STATUSES, False),
    ("delivery_status_event", "reason_code", REASON_CODES, True),
]

OPTIONAL_COLUMNS = {
    "customer_site": {"hub_id", "allowed_vehicle_types"},
    "vehicle_capacity": {"effective_to"},
    "delivery_status_event": {"route_id", "reason_code"},
    "delivery_outcome": {"actual_arrival", "actual_departure", "reason_code"},
}

SQL_TABLE_ORDER = [
    "customer_site", "vehicle", "vehicle_capacity", "driver", "shift", "travel_time_matrix",
    "traffic_scenario", "order", "delivery", "time_window", "route", "route_stop",
    "delivery_status_event", "delivery_outcome",
]

ENUM_VALUES = {(table, column): allowed for table, column, allowed, _ in ENUMS}

ID_LENGTHS = {
    "site": 11, "order": 15, "delivery": 15, "vehicle": 10, "capacity": 11, "driver": 10, "shift": 15,
    "window": 14, "route": 15, "stop": 24, "outcome": 15, "event": 15, "scenario": 15,
}

COLUMN_ID_KIND = {
    "site_id": "site", "hub_id": "site", "home_hub_id": "site", "from_site_id": "site", "to_site_id": "site",
    "order_id": "order", "delivery_id": "delivery", "vehicle_id": "vehicle", "capacity_id": "capacity",
    "driver_id": "driver", "shift_id": "shift", "window_id": "window", "route_id": "route",
    "stop_id": "stop", "outcome_id": "outcome", "event_id": "event", "scenario_id": "scenario",
}

BOOLEAN_TYPE = "TINYINT(1)"

COLUMN_TYPES = {
    "lat": "DECIMAL(9,6)", "lon": "DECIMAL(9,6)",
    "restricts_vehicle_types": BOOLEAN_TYPE, "requires_refrigeration": BOOLEAN_TYPE, "is_incident": BOOLEAN_TYPE,
    "allowed_vehicle_types": "VARCHAR(32)", "open_time": "TIME", "close_time": "TIME",
    "commissioned_date": "DATE", "hire_date": "DATE", "effective_from": "DATE", "effective_to": "DATE",
    "scenario_date": "DATE", "requested_date": "DATE", "route_date": "DATE",
    "max_weight_kg": "DECIMAL(8,2)", "max_volume_m3": "DECIMAL(6,2)", "max_units": "INT",
    "weight_kg": "DECIMAL(8,2)", "volume_m3": "DECIMAL(6,3)", "units": "INT", "service_minutes": "INT",
    "max_driving_minutes": "INT", "break_minutes_required": "INT", "break_after_driving_minutes": "INT",
    "distance_km": "DECIMAL(7,3)", "base_travel_minutes": "DECIMAL(7,2)", "traffic_factor": "DECIMAL(4,2)",
    "sequence_no": "INT", "event_seq": "INT", "attempt_no": "INT",
    "shift_start": "DATETIME", "shift_end": "DATETIME", "order_datetime": "DATETIME",
    "earliest_arrival": "DATETIME", "latest_arrival": "DATETIME", "planned_start": "DATETIME",
    "planned_arrival": "DATETIME", "planned_departure": "DATETIME", "event_time": "DATETIME",
    "actual_arrival": "DATETIME", "actual_departure": "DATETIME",
}
