def plain_id(prefix, number):
    return f"{prefix}-{number:06d}"


def yearly_id(prefix, year, number):
    return f"{prefix}-{year}-{number:06d}"


def site_id(number):
    return plain_id("SITE", number)


def order_id(year, number):
    return yearly_id("ORD", year, number)


def delivery_id(year, number):
    return yearly_id("DEL", year, number)


def vehicle_id(number):
    return plain_id("VEH", number)


def capacity_id(number):
    return plain_id("VCAP", number)


def driver_id(number):
    return plain_id("DRV", number)


def shift_id(year, number):
    return yearly_id("SHF", year, number)


def window_id(year, number):
    return yearly_id("TW", year, number)


def route_id(year, number):
    return yearly_id("RTE", year, number)


def stop_id(route, sequence_no):
    return f"STOP-{route}-{sequence_no:03d}"


def outcome_id(year, number):
    return yearly_id("OUT", year, number)


def status_event_id(year, number):
    return yearly_id("DEV", year, number)


def scenario_id(year, number):
    return yearly_id("SCN", year, number)
