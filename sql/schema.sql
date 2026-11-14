-- Synthetic delivery-routing dataset schema for MySQL 8 (InnoDB, utf8mb4).

CREATE TABLE `customer_site` (
  `site_id` VARCHAR(11) NOT NULL,
  `site_type` ENUM('customer', 'hub') NOT NULL,
  `site_class` ENUM('commercial', 'industrial', 'residential') NOT NULL,
  `lat` DECIMAL(9,6) NOT NULL,
  `lon` DECIMAL(9,6) NOT NULL,
  `hub_id` VARCHAR(11),
  `restricts_vehicle_types` TINYINT(1) NOT NULL,
  `allowed_vehicle_types` VARCHAR(32),
  `open_time` TIME NOT NULL,
  `close_time` TIME NOT NULL,
  PRIMARY KEY (`site_id`),
  FOREIGN KEY (`hub_id`) REFERENCES `customer_site` (`site_id`),
  CHECK (`restricts_vehicle_types` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `vehicle` (
  `vehicle_id` VARCHAR(10) NOT NULL,
  `vehicle_type` ENUM('refrigerated', 'truck', 'van') NOT NULL,
  `home_hub_id` VARCHAR(11) NOT NULL,
  `restriction_code` ENUM('DAYTIME_ONLY', 'NONE', 'NO_RESIDENTIAL') NOT NULL,
  `commissioned_date` DATE NOT NULL,
  PRIMARY KEY (`vehicle_id`),
  FOREIGN KEY (`home_hub_id`) REFERENCES `customer_site` (`site_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `vehicle_capacity` (
  `capacity_id` VARCHAR(11) NOT NULL,
  `vehicle_id` VARCHAR(10) NOT NULL,
  `max_weight_kg` DECIMAL(8,2) NOT NULL,
  `max_volume_m3` DECIMAL(6,2) NOT NULL,
  `max_units` INT NOT NULL,
  `effective_from` DATE NOT NULL,
  `effective_to` DATE,
  PRIMARY KEY (`capacity_id`),
  UNIQUE (`vehicle_id`, `effective_from`),
  FOREIGN KEY (`vehicle_id`) REFERENCES `vehicle` (`vehicle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `driver` (
  `driver_id` VARCHAR(10) NOT NULL,
  `home_hub_id` VARCHAR(11) NOT NULL,
  `licence_class` ENUM('heavy', 'standard') NOT NULL,
  `hire_date` DATE NOT NULL,
  PRIMARY KEY (`driver_id`),
  FOREIGN KEY (`home_hub_id`) REFERENCES `customer_site` (`site_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `shift` (
  `shift_id` VARCHAR(15) NOT NULL,
  `driver_id` VARCHAR(10) NOT NULL,
  `vehicle_id` VARCHAR(10) NOT NULL,
  `shift_start` DATETIME NOT NULL,
  `shift_end` DATETIME NOT NULL,
  `max_driving_minutes` INT NOT NULL,
  `break_minutes_required` INT NOT NULL,
  `break_after_driving_minutes` INT NOT NULL,
  PRIMARY KEY (`shift_id`),
  FOREIGN KEY (`driver_id`) REFERENCES `driver` (`driver_id`),
  FOREIGN KEY (`vehicle_id`) REFERENCES `vehicle` (`vehicle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `travel_time_matrix` (
  `from_site_id` VARCHAR(11) NOT NULL,
  `to_site_id` VARCHAR(11) NOT NULL,
  `distance_km` DECIMAL(7,3) NOT NULL,
  `base_travel_minutes` DECIMAL(7,2) NOT NULL,
  PRIMARY KEY (`from_site_id`, `to_site_id`),
  FOREIGN KEY (`from_site_id`) REFERENCES `customer_site` (`site_id`),
  FOREIGN KEY (`to_site_id`) REFERENCES `customer_site` (`site_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `traffic_scenario` (
  `scenario_id` VARCHAR(15) NOT NULL,
  `scenario_date` DATE NOT NULL,
  `hour_band` ENUM('00-06', '06-10', '10-16', '16-20', '20-24') NOT NULL,
  `traffic_factor` DECIMAL(4,2) NOT NULL,
  `is_incident` TINYINT(1) NOT NULL,
  PRIMARY KEY (`scenario_id`),
  UNIQUE (`scenario_date`, `hour_band`),
  CHECK (`is_incident` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `order` (
  `order_id` VARCHAR(15) NOT NULL,
  `site_id` VARCHAR(11) NOT NULL,
  `order_datetime` DATETIME NOT NULL,
  `requested_date` DATE NOT NULL,
  `weight_kg` DECIMAL(8,2) NOT NULL,
  `volume_m3` DECIMAL(6,3) NOT NULL,
  `units` INT NOT NULL,
  `requires_refrigeration` TINYINT(1) NOT NULL,
  PRIMARY KEY (`order_id`),
  FOREIGN KEY (`site_id`) REFERENCES `customer_site` (`site_id`),
  CHECK (`requires_refrigeration` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `delivery` (
  `delivery_id` VARCHAR(15) NOT NULL,
  `order_id` VARCHAR(15) NOT NULL,
  `weight_kg` DECIMAL(8,2) NOT NULL,
  `volume_m3` DECIMAL(6,3) NOT NULL,
  `units` INT NOT NULL,
  `service_minutes` INT NOT NULL,
  PRIMARY KEY (`delivery_id`),
  FOREIGN KEY (`order_id`) REFERENCES `order` (`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `time_window` (
  `window_id` VARCHAR(14) NOT NULL,
  `delivery_id` VARCHAR(15) NOT NULL,
  `earliest_arrival` DATETIME NOT NULL,
  `latest_arrival` DATETIME NOT NULL,
  `priority` ENUM('critical', 'high', 'low', 'normal') NOT NULL,
  PRIMARY KEY (`window_id`),
  UNIQUE (`delivery_id`),
  FOREIGN KEY (`delivery_id`) REFERENCES `delivery` (`delivery_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `route` (
  `route_id` VARCHAR(15) NOT NULL,
  `shift_id` VARCHAR(15) NOT NULL,
  `hub_id` VARCHAR(11) NOT NULL,
  `route_date` DATE NOT NULL,
  `planned_start` DATETIME NOT NULL,
  PRIMARY KEY (`route_id`),
  FOREIGN KEY (`shift_id`) REFERENCES `shift` (`shift_id`),
  FOREIGN KEY (`hub_id`) REFERENCES `customer_site` (`site_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `route_stop` (
  `stop_id` VARCHAR(24) NOT NULL,
  `route_id` VARCHAR(15) NOT NULL,
  `sequence_no` INT NOT NULL,
  `delivery_id` VARCHAR(15) NOT NULL,
  `planned_arrival` DATETIME NOT NULL,
  `planned_departure` DATETIME NOT NULL,
  PRIMARY KEY (`stop_id`),
  UNIQUE (`route_id`, `sequence_no`),
  FOREIGN KEY (`route_id`) REFERENCES `route` (`route_id`),
  FOREIGN KEY (`delivery_id`) REFERENCES `delivery` (`delivery_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `delivery_status_event` (
  `event_id` VARCHAR(15) NOT NULL,
  `delivery_id` VARCHAR(15) NOT NULL,
  `event_seq` INT NOT NULL,
  `status` ENUM('assigned', 'delivered', 'failed', 'in_transit', 'planned', 'unserved') NOT NULL,
  `event_time` DATETIME NOT NULL,
  `route_id` VARCHAR(15),
  `reason_code` ENUM('CAPACITY', 'LATE_MISSED_WINDOW', 'SHIFT_EXCEEDED', 'SITE_CLOSED', 'VEHICLE_RESTRICTED'),
  PRIMARY KEY (`event_id`),
  UNIQUE (`delivery_id`, `event_seq`),
  FOREIGN KEY (`delivery_id`) REFERENCES `delivery` (`delivery_id`),
  FOREIGN KEY (`route_id`) REFERENCES `route` (`route_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `delivery_outcome` (
  `outcome_id` VARCHAR(15) NOT NULL,
  `stop_id` VARCHAR(24) NOT NULL,
  `delivery_id` VARCHAR(15) NOT NULL,
  `attempt_no` INT NOT NULL,
  `actual_arrival` DATETIME,
  `actual_departure` DATETIME,
  `status` ENUM('delivered', 'failed') NOT NULL,
  `reason_code` ENUM('CAPACITY', 'LATE_MISSED_WINDOW', 'SHIFT_EXCEEDED', 'SITE_CLOSED', 'VEHICLE_RESTRICTED'),
  PRIMARY KEY (`outcome_id`),
  UNIQUE (`stop_id`),
  UNIQUE (`delivery_id`, `attempt_no`),
  FOREIGN KEY (`stop_id`) REFERENCES `route_stop` (`stop_id`),
  FOREIGN KEY (`delivery_id`) REFERENCES `delivery` (`delivery_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
