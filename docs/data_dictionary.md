# Data dictionary

## Conventions

- Timestamps are local-time ISO 8601 strings without offset: `YYYY-MM-DDTHH:MM:SS`. Dates are `YYYY-MM-DD`. Times of day are `HH:MM`.
- Coordinates are decimal degrees. Valid range is `REGION_BOUNDS` in `generator/config.py` (lat 40.60 to 40.90, lon -74.05 to -73.75).
- IDs are zero-padded, assigned once and never reused or edited. `YYYY` is the calendar year of the record's main date.
- Nothing is updated in place. A change of state or of capacity is a new row.
- Derived values (route load, stop counts, current delivery status, totals, actual travel minutes) are computed from source rows and are not stored.
- "Req" is Y for required (not null), N for optional (nullable).

## ID formats

| Entity | Format | Example |
|---|---|---|
| CustomerSite | SITE-NNNNNN | SITE-000001 |
| Order | ORD-YYYY-NNNNNN | ORD-2026-000001 |
| Delivery | DEL-YYYY-NNNNNN | DEL-2026-000001 |
| Vehicle | VEH-NNNNNN | VEH-000001 |
| VehicleCapacity | VCAP-NNNNNN | VCAP-000001 |
| Driver | DRV-NNNNNN | DRV-000001 |
| Shift | SHF-YYYY-NNNNNN | SHF-2026-000001 |
| TimeWindow | TW-YYYY-NNNNNN | TW-2026-000001 |
| TravelTimeMatrix | composite key (from_site_id, to_site_id) | none |
| TrafficScenario | SCN-YYYY-NNNNNN | SCN-2026-000001 |
| Route | RTE-YYYY-NNNNNN | RTE-2026-000001 |
| RouteStop | STOP-\<route_id\>-NNN | STOP-RTE-2026-000001-001 |
| DeliveryOutcome | OUT-YYYY-NNNNNN | OUT-2026-000001 |
| DeliveryStatusEvent | DEV-YYYY-NNNNNN | DEV-2026-000001 |

Sequence numbers (NNNNNN, NNN) start at 1 and increase by 1 per entity (per year, or per route for stops).

## Entities

### 1. CustomerSite

Delivery locations and hubs. A hub is a site of type `hub`; customer sites point to their hub.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| site_id | string | Y | SITE-NNNNNN | none | PK | matches ID format |
| site_type | enum | Y | hub, customer | none | no | hub rows have hub_id null |
| site_class | enum | Y | residential, commercial, industrial | none | no | hubs are industrial |
| lat | decimal(9,6) | Y | 40.60 to 40.90 | degrees | no | inside region bounds |
| lon | decimal(9,6) | Y | -74.05 to -73.75 | degrees | no | inside region bounds |
| hub_id | string | N | existing site_id | none | no | FK to CustomerSite.site_id; required when site_type is customer; target must have site_type hub |
| restricts_vehicle_types | bool | Y | true, false | none | no | none |
| allowed_vehicle_types | string | N | pipe-separated Vehicle.vehicle_type values | none | no | required when restricts_vehicle_types is true, null otherwise |
| open_time | time | Y | 00:00 to 23:59 | local time | no | earlier than close_time |
| close_time | time | Y | 00:00 to 23:59 | local time | no | later than open_time |

### 2. Order

A customer request for goods to a site.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| order_id | string | Y | ORD-YYYY-NNNNNN | none | PK | matches ID format |
| site_id | string | Y | existing customer site | none | no | FK to CustomerSite.site_id; site_type is customer |
| order_datetime | datetime | Y | within simulation period | local time | no | not after the end of requested_date |
| requested_date | date | Y | within simulation period | date | no | on or after the date of order_datetime |
| weight_kg | decimal(8,2) | Y | 0.5 to 1000 | kg | no | equals the sum of its deliveries' weight_kg |
| volume_m3 | decimal(6,3) | Y | 0.01 to 8 | m3 | no | equals the sum of its deliveries' volume_m3 |
| units | int | Y | 1 to 100 | items | no | equals the sum of its deliveries' units |
| requires_refrigeration | bool | Y | true, false | none | no | true needs a refrigerated vehicle |

### 3. Delivery

One shipment fulfilling all or part of an order. It carries its own load. Its status is not stored here; see DeliveryStatusEvent.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| delivery_id | string | Y | DEL-YYYY-NNNNNN | none | PK | matches ID format |
| order_id | string | Y | existing order_id | none | no | FK to Order.order_id |
| weight_kg | decimal(8,2) | Y | 0.5 to 1000 | kg | no | greater than 0 |
| volume_m3 | decimal(6,3) | Y | 0.01 to 8 | m3 | no | greater than 0 |
| units | int | Y | 1 to 100 | items | no | at least 1 |
| service_minutes | int | Y | 2 to 60 | minutes | no | planned stop duration is at least this |

### 4. Vehicle

Fixed attributes of a vehicle. Capacity is held separately.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| vehicle_id | string | Y | VEH-NNNNNN | none | PK | matches ID format |
| vehicle_type | enum | Y | van, truck, refrigerated | none | no | none |
| home_hub_id | string | Y | existing hub site_id | none | no | FK to CustomerSite.site_id; site_type is hub |
| restriction_code | enum | Y | NONE, NO_RESIDENTIAL, DAYTIME_ONLY | none | no | NO_RESIDENTIAL cannot serve residential sites; DAYTIME_ONLY stops must fall between 06:00 and 20:00 |
| commissioned_date | date | Y | within or before simulation period | date | no | none |

### 5. VehicleCapacity

Capacity of a vehicle for a date range. A capacity change adds a row and closes the previous one.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| capacity_id | string | Y | VCAP-NNNNNN | none | PK | matches ID format |
| vehicle_id | string | Y | existing vehicle_id | none | no | FK to Vehicle.vehicle_id |
| max_weight_kg | decimal(8,2) | Y | 300 to 10000 | kg | no | greater than 0 |
| max_volume_m3 | decimal(6,2) | Y | 3 to 60 | m3 | no | greater than 0 |
| max_units | int | Y | 20 to 1000 | items | no | at least 1 |
| effective_from | date | Y | any date | date | unique with vehicle_id | none |
| effective_to | date | N | on or after effective_from | date | no | null means open-ended; ranges for one vehicle never overlap |

### 6. Driver

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| driver_id | string | Y | DRV-NNNNNN | none | PK | matches ID format |
| home_hub_id | string | Y | existing hub site_id | none | no | FK to CustomerSite.site_id; site_type is hub |
| licence_class | enum | Y | standard, heavy | none | no | heavy is needed to drive a truck |
| hire_date | date | Y | on or before first shift | date | no | none |

### 7. Shift

One driver working one vehicle for one period. It is the bridge between Driver and Vehicle.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| shift_id | string | Y | SHF-YYYY-NNNNNN | none | PK | matches ID format |
| driver_id | string | Y | existing driver_id | none | no | FK to Driver.driver_id; no overlapping shifts for the same driver |
| vehicle_id | string | Y | existing vehicle_id | none | no | FK to Vehicle.vehicle_id; no overlapping shifts for the same vehicle |
| shift_start | datetime | Y | within simulation period | local time | no | earlier than shift_end |
| shift_end | datetime | Y | within simulation period | local time | no | at most 14 hours after shift_start |
| max_driving_minutes | int | Y | 120 to 600 | minutes | no | at most the shift length |
| break_minutes_required | int | Y | 0 to 120 | minutes | no | none |
| break_after_driving_minutes | int | Y | 60 to 300 | minutes | no | a break of break_minutes_required is needed after this much continuous driving |

### 8. TravelTimeMatrix

Static travel data for each ordered pair of sites. It has no date or hour band; time-of-day effects come from TrafficScenario. Both values are computed from site coordinates, not drawn independently.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| from_site_id | string | Y | existing site_id | none | part of PK | FK to CustomerSite.site_id |
| to_site_id | string | Y | existing site_id | none | part of PK | FK to CustomerSite.site_id; different from from_site_id |
| distance_km | decimal(7,3) | Y | 0.05 to 80 | km | no | computed from the two sites' coordinates |
| base_travel_minutes | decimal(7,2) | Y | greater than 0 | minutes | no | equals distance_km divided by base speed times 60 (free-flow speed set in config) |

Actual travel minutes for a leg are `base_travel_minutes x traffic_factor`, where the factor comes from the TrafficScenario matching the date and hour band of the departure. This value is computed when needed and is not stored in any table.

### 9. TimeWindow

Arrival window for a delivery.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| window_id | string | Y | TW-YYYY-NNNNNN | none | PK | matches ID format |
| delivery_id | string | Y | existing delivery_id | none | unique | FK to Delivery.delivery_id; one window per delivery |
| earliest_arrival | datetime | Y | within simulation period | local time | no | earlier than latest_arrival |
| latest_arrival | datetime | Y | within simulation period | local time | no | same date as earliest_arrival; window is 30 to 480 minutes |
| priority | enum | Y | low, normal, high, critical | none | no | none |

### 10. Route

One planned trip for a shift, starting and ending at a hub. Vehicle and driver come from the shift.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| route_id | string | Y | RTE-YYYY-NNNNNN | none | PK | matches ID format |
| shift_id | string | Y | existing shift_id | none | no | FK to Shift.shift_id |
| hub_id | string | Y | existing hub site_id | none | no | FK to CustomerSite.site_id; site_type is hub |
| route_date | date | Y | within simulation period | date | no | equals the date of the shift's shift_start |
| planned_start | datetime | Y | within the shift | local time | no | not before shift_start, before shift_end |

### 11. RouteStop

One planned visit. It is the bridge between Route and Delivery.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| stop_id | string | Y | STOP-\<route_id\>-NNN | none | PK | matches ID format; NNN equals sequence_no |
| route_id | string | Y | existing route_id | none | no | FK to Route.route_id |
| sequence_no | int | Y | 1 to 60 | position | unique with route_id | starts at 1 with no gaps |
| delivery_id | string | Y | existing delivery_id | none | unique with route_id | FK to Delivery.delivery_id; a delivery appears at most once per route |
| planned_arrival | datetime | Y | within the shift | local time | no | not before the previous stop's planned_departure plus actual travel minutes (base_travel_minutes x traffic_factor) |
| planned_departure | datetime | Y | within the shift | local time | no | at least planned_arrival plus the delivery's service_minutes |

### 12. DeliveryOutcome

One row per delivery attempt. Rows are never edited; a retry is a new row with the next attempt_no.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| outcome_id | string | Y | OUT-YYYY-NNNNNN | none | PK | matches ID format |
| stop_id | string | Y | existing stop_id | none | unique | FK to RouteStop.stop_id; one outcome per executed stop |
| delivery_id | string | Y | existing delivery_id | none | unique with attempt_no | FK to Delivery.delivery_id; must match the stop's delivery_id |
| attempt_no | int | Y | 1 to 3 | count | unique with delivery_id | starts at 1, increases by 1 per delivery |
| actual_arrival | datetime | N | within simulation period | local time | no | required unless the stop was never reached |
| actual_departure | datetime | N | within simulation period | local time | no | not before actual_arrival; required when actual_arrival is set |
| status | enum | Y | delivered, failed | none | no | none |
| reason_code | enum | N | LATE_MISSED_WINDOW, SHIFT_EXCEEDED, CAPACITY, SITE_CLOSED, VEHICLE_RESTRICTED | none | no | required when status is failed, null when delivered |

### 13. DeliveryStatusEvent (added)

Not in the original list of 12. It holds the delivery lifecycle as append-only rows, because Delivery has no status field to overwrite.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| event_id | string | Y | DEV-YYYY-NNNNNN | none | PK | matches ID format |
| delivery_id | string | Y | existing delivery_id | none | no | FK to Delivery.delivery_id |
| event_seq | int | Y | 1 or more | count | unique with delivery_id | starts at 1, increases by 1 per delivery |
| status | enum | Y | planned, assigned, unserved, in_transit, delivered, failed | none | no | must be an allowed transition from the previous event's status |
| event_time | datetime | Y | within simulation period | local time | no | not before the previous event's event_time |
| route_id | string | N | existing route_id | none | no | FK to Route.route_id; required for assigned and in_transit |

### 14. TrafficScenario (added)

Not in the original list of 12. It holds the traffic multiplier for one date and hour band, applied to every site pair.

| Field | Type | Req | Allowed values / range | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| scenario_id | string | Y | SCN-YYYY-NNNNNN | none | PK | matches ID format |
| scenario_date | date | Y | within simulation period | date | unique with hour_band | none |
| hour_band | enum | Y | 00-06, 06-10, 10-16, 16-20, 20-24 | local hours | unique with scenario_date | none |
| traffic_factor | decimal(4,2) | Y | 0.8 to 2.0 | multiplier | no | 1.0 is free flow; below 1.0 is lighter than free-flow baseline |

Every date in the simulation period has one row per hour band, so a leg always finds its factor.

## Delivery lifecycle

The current status of a delivery is the status of its latest DeliveryStatusEvent. The first event is always `planned`.

| From | Allowed to |
|---|---|
| planned | assigned, unserved |
| assigned | in_transit, unserved, planned |
| in_transit | delivered, failed |
| failed | planned |
| unserved | planned |
| delivered | none (final) |

- `failed` leads to `planned` for a retry. After attempt 3 a failed delivery gets no further events and stays failed.
- `in_transit` to `delivered` or `failed` is written together with a DeliveryOutcome row for that attempt.
- `assigned` to `planned` covers reassignment to another route.

## Relationships

| Parent | Child | Cardinality | Foreign key | Optional | Notes |
|---|---|---|---|---|---|
| CustomerSite (hub) | CustomerSite (customer) | 1:N | CustomerSite.hub_id | hubs have no parent | self-reference |
| CustomerSite | Order | 1:N | Order.site_id | a site may have no orders | |
| Order | Delivery | 1:N | Delivery.order_id | an order has at least one delivery | split shipments |
| Delivery | TimeWindow | 1:1 | TimeWindow.delivery_id | window required for every delivery | |
| Delivery | DeliveryStatusEvent | 1:N | DeliveryStatusEvent.delivery_id | at least one (planned) | |
| Route | DeliveryStatusEvent | 1:N | DeliveryStatusEvent.route_id | optional | null before assignment |
| Vehicle | VehicleCapacity | 1:N | VehicleCapacity.vehicle_id | at least one | dated, non-overlapping |
| Vehicle | Shift | 1:N | Shift.vehicle_id | a vehicle may have no shifts | |
| Driver | Shift | 1:N | Shift.driver_id | a driver may have no shifts | |
| Driver / Vehicle | each other | N:M | through Shift | optional | Shift is the bridge |
| Shift | Route | 1:N | Route.shift_id | a shift may have no route | usually one route |
| CustomerSite (hub) | Route | 1:N | Route.hub_id | | |
| CustomerSite (hub) | Vehicle, Driver | 1:N | home_hub_id | | |
| Route | RouteStop | 1:N | RouteStop.route_id | a route has at least one stop | ordered by sequence_no |
| Delivery / Route | each other | N:M | through RouteStop | a delivery may be on no route (unserved) | RouteStop is the bridge; a retry appears on a later route |
| Delivery | RouteStop | 1:N | RouteStop.delivery_id | optional | |
| RouteStop | DeliveryOutcome | 1:0..1 | DeliveryOutcome.stop_id | optional | absent until executed |
| Delivery | DeliveryOutcome | 1:N | DeliveryOutcome.delivery_id | optional | one per attempt |
| CustomerSite | TravelTimeMatrix | 1:N twice | from_site_id, to_site_id | optional | N:M between sites with the matrix row as bridge |
| TrafficScenario | none | no foreign key | none | | looked up by date and hour band at computation time; it applies to every site pair, so there is no row-level relationship |

## Anomaly types

Anomalies are injected after clean generation and recorded in `ground_truth/ground_truth.csv`. They never appear as columns in the input tables.

| Issue type | What is wrong | Tables and fields touched |
|---|---|---|
| ROUTE_CAPACITY_EXCEEDED | Summed delivery load on a route is over the vehicle's capacity on route_date | Route, RouteStop.delivery_id, Delivery.weight_kg / volume_m3 / units, VehicleCapacity.max_weight_kg / max_volume_m3 / max_units |
| STOP_OMITTED_OR_DUPLICATED | A planned delivery has no stop, or a delivery appears twice in one route, or sequence_no has a gap | RouteStop.sequence_no, RouteStop.delivery_id, DeliveryStatusEvent |
| ARRIVAL_BEFORE_PREVIOUS_DEPARTURE | A stop's arrival is earlier than the previous stop's departure | RouteStop.planned_arrival / planned_departure, DeliveryOutcome.actual_arrival / actual_departure |
| DRIVER_SHIFT_EXCEEDED | Stops end after shift_end or driving exceeds max_driving_minutes | Shift.shift_end / max_driving_minutes, RouteStop.planned_arrival / planned_departure, DeliveryOutcome.actual_departure |
| COORDINATE_OUTSIDE_REGION | A site's coordinates are outside the region bounds | CustomerSite.lat / lon |

### ground_truth.csv fields

| Field | Type | Description |
|---|---|---|
| record_id | string | primary key of the affected row (for a composite key, values joined with a pipe) |
| table | string | name of the affected table |
| issue_type | enum | one of the five issue types above |
| description | string | short plain-text explanation of what was changed |

The split of TravelTimeMatrix and TrafficScenario does not change the anomaly list. The arrival-before-departure and shift-exceeded checks use actual travel minutes, computed from both tables, but no anomaly is injected into either table.

## Deviation from the original 12 entities

Two entities were added to the original 12:

- **DeliveryStatusEvent:** Delivery has no status field, so the lifecycle is stored as append-only event rows. This follows the rule that state changes are new rows.
- **TrafficScenario:** a per-date, per-hour-band matrix would need about 37 million rows at full scale. Keeping the matrix static (about 250,000 rows) and storing only 150 traffic scenarios (30 days times 5 bands) removes that problem. It also keeps actual travel time derived from source records.

## Assumptions and trade-offs

