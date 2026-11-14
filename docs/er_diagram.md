# ER diagram

Keys and foreign keys only. Full field lists are in [data_dictionary.md](data_dictionary.md).

```mermaid
erDiagram
    CustomerSite {
        string site_id PK
        string hub_id FK
    }
    Order {
        string order_id PK
        string site_id FK
    }
    Delivery {
        string delivery_id PK
        string order_id FK
    }
    TimeWindow {
        string window_id PK
        string delivery_id FK
    }
    DeliveryStatusEvent {
        string event_id PK
        string delivery_id FK
        string route_id FK
    }
    Vehicle {
        string vehicle_id PK
        string home_hub_id FK
    }
    VehicleCapacity {
        string capacity_id PK
        string vehicle_id FK
    }
    Driver {
        string driver_id PK
        string home_hub_id FK
    }
    Shift {
        string shift_id PK
        string driver_id FK
        string vehicle_id FK
    }
    TravelTimeMatrix {
        string from_site_id PK, FK
        string to_site_id PK, FK
    }
    TrafficScenario {
        string scenario_id PK
        date scenario_date
        string hour_band
    }
    Route {
        string route_id PK
        string shift_id FK
        string hub_id FK
    }
    RouteStop {
        string stop_id PK
        string route_id FK
        string delivery_id FK
    }
    DeliveryOutcome {
        string outcome_id PK
        string stop_id FK
        string delivery_id FK
    }

    CustomerSite |o--o{ CustomerSite : "hub serves"
    CustomerSite ||--o{ Order : places
    Order ||--|{ Delivery : "split into"
    Delivery ||--|| TimeWindow : has
    Delivery ||--|{ DeliveryStatusEvent : "status history"
    Route |o--o{ DeliveryStatusEvent : "assigned on"
    Vehicle ||--|{ VehicleCapacity : "capacity history"
    Vehicle ||--o{ Shift : "used in"
    Driver ||--o{ Shift : works
    CustomerSite ||--o{ Vehicle : "home hub"
    CustomerSite ||--o{ Driver : "home hub"
    CustomerSite ||--o{ TravelTimeMatrix : "from"
    CustomerSite ||--o{ TravelTimeMatrix : "to"
    CustomerSite ||--o{ Route : "starts at"
    Shift ||--o{ Route : runs
    Route ||--|{ RouteStop : "ordered stops"
    Delivery ||--o{ RouteStop : "visited by"
    RouteStop ||--o| DeliveryOutcome : "result of"
    Delivery ||--o{ DeliveryOutcome : attempts
```

## Bridge tables

- **Shift** links Driver and Vehicle (N:M).
- **RouteStop** links Route and Delivery (N:M). A delivery has no stop while unserved and gets a new stop on a later route when retried.
- **TravelTimeMatrix** links CustomerSite to CustomerSite (N:M), one row per ordered pair.

## Traffic scenario

TrafficScenario has no foreign key and no line in the diagram. Actual travel minutes are `base_travel_minutes x traffic_factor`, computed by matching a leg's departure date and hour band to the scenario row. The value is never stored.

## Deviation from the original 12 entities

DeliveryStatusEvent and TrafficScenario were added. DeliveryStatusEvent keeps delivery states as append-only rows. TrafficScenario lets the travel matrix stay static (about 250,000 rows at full scale instead of about 37 million).
