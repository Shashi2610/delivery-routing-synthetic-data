# Validation report

Data folder: `C:\Users\pc\OneDrive\Documents\delivery-routing-synthetic-data\data`

## Summary

Overall: PASS
- 115 of 115 structural checks passed
- 15 anomalies detected by the rule checks

## Structural checks

| Group | Check | Rows checked | Failures | Status |
|---|---|---|---|---|
| keys | primary key customer_site | 55 | 0 | pass |
| keys | primary key vehicle | 10 | 0 | pass |
| keys | primary key vehicle_capacity | 10 | 0 | pass |
| keys | primary key driver | 12 | 0 | pass |
| keys | primary key shift | 30 | 0 | pass |
| keys | primary key travel_time_matrix | 2970 | 0 | pass |
| keys | primary key traffic_scenario | 15 | 0 | pass |
| keys | primary key order | 180 | 0 | pass |
| keys | primary key delivery | 200 | 0 | pass |
| keys | primary key time_window | 200 | 0 | pass |
| keys | primary key delivery_status_event | 614 | 0 | pass |
| keys | primary key route | 29 | 0 | pass |
| keys | primary key route_stop | 106 | 0 | pass |
| keys | primary key delivery_outcome | 105 | 0 | pass |
| keys | unique vehicle_capacity (vehicle_id, effective_from) | 10 | 0 | pass |
| keys | unique time_window (delivery_id) | 200 | 0 | pass |
| keys | unique route_stop (route_id, sequence_no) | 106 | 0 | pass |
| keys | unique delivery_outcome (stop_id) | 105 | 0 | pass |
| keys | unique delivery_outcome (delivery_id, attempt_no) | 105 | 0 | pass |
| keys | unique delivery_status_event (delivery_id, event_seq) | 614 | 0 | pass |
| keys | unique traffic_scenario (scenario_date, hour_band) | 15 | 0 | pass |
| foreign keys | customer_site.hub_id -> customer_site.site_id | 50 | 0 | pass |
| foreign keys | order.site_id -> customer_site.site_id | 180 | 0 | pass |
| foreign keys | delivery.order_id -> order.order_id | 200 | 0 | pass |
| foreign keys | time_window.delivery_id -> delivery.delivery_id | 200 | 0 | pass |
| foreign keys | delivery_status_event.delivery_id -> delivery.delivery_id | 614 | 0 | pass |
| foreign keys | delivery_status_event.route_id -> route.route_id | 321 | 0 | pass |
| foreign keys | vehicle.home_hub_id -> customer_site.site_id | 10 | 0 | pass |
| foreign keys | vehicle_capacity.vehicle_id -> vehicle.vehicle_id | 10 | 0 | pass |
| foreign keys | driver.home_hub_id -> customer_site.site_id | 12 | 0 | pass |
| foreign keys | shift.driver_id -> driver.driver_id | 30 | 0 | pass |
| foreign keys | shift.vehicle_id -> vehicle.vehicle_id | 30 | 0 | pass |
| foreign keys | travel_time_matrix.from_site_id -> customer_site.site_id | 2970 | 0 | pass |
| foreign keys | travel_time_matrix.to_site_id -> customer_site.site_id | 2970 | 0 | pass |
| foreign keys | route.shift_id -> shift.shift_id | 29 | 0 | pass |
| foreign keys | route.hub_id -> customer_site.site_id | 29 | 0 | pass |
| foreign keys | route_stop.route_id -> route.route_id | 106 | 0 | pass |
| foreign keys | route_stop.delivery_id -> delivery.delivery_id | 106 | 0 | pass |
| foreign keys | delivery_outcome.stop_id -> route_stop.stop_id | 105 | 0 | pass |
| foreign keys | delivery_outcome.delivery_id -> delivery.delivery_id | 105 | 0 | pass |
| enums | customer_site.site_type | 55 | 0 | pass |
| enums | customer_site.site_class | 55 | 0 | pass |
| enums | vehicle.vehicle_type | 10 | 0 | pass |
| enums | vehicle.restriction_code | 10 | 0 | pass |
| enums | driver.licence_class | 12 | 0 | pass |
| enums | traffic_scenario.hour_band | 15 | 0 | pass |
| enums | time_window.priority | 200 | 0 | pass |
| enums | delivery_outcome.status | 105 | 0 | pass |
| enums | delivery_outcome.reason_code | 105 | 0 | pass |
| enums | delivery_status_event.status | 614 | 0 | pass |
| enums | delivery_status_event.reason_code | 614 | 0 | pass |
| enums | customer_site.allowed_vehicle_types values | 6 | 0 | pass |
| enums | customer_site restriction flag matches allowed types | 55 | 0 | pass |
| id formats | customer_site.site_id | 55 | 0 | pass |
| id formats | order.order_id | 180 | 0 | pass |
| id formats | delivery.delivery_id | 200 | 0 | pass |
| id formats | vehicle.vehicle_id | 10 | 0 | pass |
| id formats | vehicle_capacity.capacity_id | 10 | 0 | pass |
| id formats | driver.driver_id | 12 | 0 | pass |
| id formats | shift.shift_id | 30 | 0 | pass |
| id formats | time_window.window_id | 200 | 0 | pass |
| id formats | route.route_id | 29 | 0 | pass |
| id formats | route_stop.stop_id | 106 | 0 | pass |
| id formats | delivery_outcome.outcome_id | 105 | 0 | pass |
| id formats | delivery_status_event.event_id | 614 | 0 | pass |
| id formats | traffic_scenario.scenario_id | 15 | 0 | pass |
| id formats | route_stop.stop_id matches route_id and sequence_no | 106 | 0 | pass |
| ranges | order.weight_kg in [0.5, 1000] | 180 | 0 | pass |
| ranges | order.volume_m3 in [0.01, 8] | 180 | 0 | pass |
| ranges | order.units in [1, 100] | 180 | 0 | pass |
| ranges | delivery.weight_kg in [0.5, 1000] | 200 | 0 | pass |
| ranges | delivery.volume_m3 in [0.01, 8] | 200 | 0 | pass |
| ranges | delivery.units in [1, 100] | 200 | 0 | pass |
| ranges | delivery.service_minutes in [2, 60] | 200 | 0 | pass |
| ranges | vehicle_capacity.max_weight_kg in [300, 10000] | 10 | 0 | pass |
| ranges | vehicle_capacity.max_volume_m3 in [3, 60] | 10 | 0 | pass |
| ranges | vehicle_capacity.max_units in [20, 1000] | 10 | 0 | pass |
| ranges | shift.max_driving_minutes in [120, 600] | 30 | 0 | pass |
| ranges | shift.break_minutes_required in [0, 120] | 30 | 0 | pass |
| ranges | shift.break_after_driving_minutes in [60, 300] | 30 | 0 | pass |
| ranges | traffic_scenario.traffic_factor in [0.8, 2.0] | 15 | 0 | pass |
| ranges | travel_time_matrix.distance_km in [0.05, 80] | 2970 | 0 | pass |
| ranges | travel_time_matrix.base_travel_minutes in [0.01, 10000] | 2970 | 0 | pass |
| ranges | delivery_outcome.attempt_no in [1, 3] | 105 | 0 | pass |
| ranges | route_stop.sequence_no in [1, 60] | 106 | 0 | pass |
| time ordering | time window earliest < latest, same day, 30 to 480 minutes | 200 | 0 | pass |
| time ordering | shift start < end, at most 14 hours, driving limit within shift | 30 | 0 | pass |
| time ordering | site open_time < close_time | 55 | 0 | pass |
| time ordering | order placed on or before requested_date | 180 | 0 | pass |
| time ordering | route planned_start inside shift and route_date matches | 29 | 0 | pass |
| time ordering | planned stop: service time fits and stop is inside the shift | 106 | 0 | pass |
| time ordering | planned arrival at least previous departure plus travel time | 104 | 0 | pass |
| time ordering | actual arrival <= actual departure, both set or both empty | 105 | 0 | pass |
| time ordering | no overlapping shifts per driver_id | 30 | 0 | pass |
| time ordering | no overlapping shifts per vehicle_id | 30 | 0 | pass |
| hub rules | route hub equals the vehicle's home hub | 29 | 0 | pass |
| hub rules | stop delivery site belongs to the route's hub | 106 | 0 | pass |
| lifecycle | event_seq runs 1..n per delivery (no event removed) | 614 | 0 | pass |
| lifecycle | first event of every delivery is planned | 200 | 0 | pass |
| lifecycle | event times never go backwards | 614 | 0 | pass |
| lifecycle | status transitions are allowed | 414 | 0 | pass |
| lifecycle | assigned and in_transit events carry a route_id | 614 | 0 | pass |
| lifecycle | reason_code present exactly on unserved events | 614 | 0 | pass |
| lifecycle | event ids are consecutive per year (no event removed) | 614 | 0 | pass |
| lifecycle | unserved deliveries have no outcome | 93 | 0 | pass |
| lifecycle | latest event status matches the outcome status | 105 | 0 | pass |
| coverage | every delivery is assigned or unserved | 200 | 0 | pass |
| coverage | no delivery is both assigned and unserved | 200 | 0 | pass |
| coverage | reason_code present exactly on failed outcomes | 105 | 0 | pass |
| reconciliation | order weight_kg equals the sum of its deliveries | 180 | 0 | pass |
| reconciliation | order volume_m3 equals the sum of its deliveries | 180 | 0 | pass |
| reconciliation | order units equals the sum of its deliveries | 180 | 0 | pass |
| reconciliation | delivered lateness within the grace period | 98 | 0 | pass |
| reconciliation | LATE_MISSED_WINDOW lateness above the grace period | 3 | 0 | pass |
| reconciliation | SITE_CLOSED arrival after the closing time | 0 | 0 | pass |

## Rule detectors

| Issue type | Detections |
|---|---|
| ROUTE_CAPACITY_EXCEEDED | 3 |
| STOP_OMITTED_OR_DUPLICATED | 3 |
| ARRIVAL_BEFORE_PREVIOUS_DEPARTURE | 3 |
| DRIVER_SHIFT_EXCEEDED | 3 |
| COORDINATE_OUTSIDE_REGION | 3 |

## Scoring

| Issue type | Injected | Detected | Recall | Detections | True positives | Precision | False positives | Missed |
|---|---|---|---|---|---|---|---|---|
| ROUTE_CAPACITY_EXCEEDED | 3 | 3 | 100.0% | 3 | 3 | 100.0% | 0 | 0 |
| STOP_OMITTED_OR_DUPLICATED | 3 | 3 | 100.0% | 3 | 3 | 100.0% | 0 | 0 |
| ARRIVAL_BEFORE_PREVIOUS_DEPARTURE | 3 | 3 | 100.0% | 3 | 3 | 100.0% | 0 | 0 |
| DRIVER_SHIFT_EXCEEDED | 3 | 3 | 100.0% | 3 | 3 | 100.0% | 0 | 0 |
| COORDINATE_OUTSIDE_REGION | 3 | 3 | 100.0% | 3 | 3 | 100.0% | 0 | 0 |

No missed anomalies and no false positives.

## Not implemented

- Stored route totals (distance, minutes, load): Route has no total columns because derived values are not stored, so there is nothing to reconcile. Route load is recomputed from the stops only inside the capacity detector.
- Stored lateness: lateness is not stored. Lateness rules are checked instead by comparing actual arrival with the window end and the grace period.
- Overwritten events: an event whose values were changed in place cannot be detected without a previous snapshot. Only removed events are detected, through gaps in event_seq and event_id.
- Break rules and actual driving minutes: not requested and not checked.
