"""Additive display metadata for known facilities; frozen baselines stay unchanged.

Match the full stored identity/location, never infer a body from facility type.
Keep the historical backfill in migration 0012 frozen when extending this table.
"""

FACILITY_LOCATIONS = {
    ("LUN-OPS-01", "Lunar Operations One", "Mare Imbrium"): "Earth’s Moon",
    ("LUN-OPS-02", "South Pole Research Station", "Shackleton Crater"): "Earth’s Moon",
    ("MCC-OPS-01", "Mission Control Center", "Houston"): "Earth",
    ("ORB-OPS-01", "Orbital Operations Station", "Low Earth Orbit"): "Earth",
    ("LOG-OPS-01", "Cislunar Logistics Depot", "Earth-Moon L1"): "Earth–Moon system",
}


def facility_body_or_system(code: str, name: str, location: str) -> str | None:
    return FACILITY_LOCATIONS.get((code, name, location))
