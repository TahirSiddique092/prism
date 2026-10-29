"""Timestamp serialisation shared by the API modules (slice-25).

MySQL returns TIMESTAMP values as naive datetimes in the session time zone,
which get_db_config pins to UTC. Sent without a zone, browsers read them as
local time (5 h 30 min off in India), so they go out as ISO 8601 with "Z".
"""
from datetime import datetime, timezone


def to_utc_iso(value):
    """Return a UTC timestamp as ISO 8601 ending in "Z", e.g. "2026-10-29T16:00:09Z".

    Naive datetimes are taken to be UTC; aware ones are converted to UTC.
    None stays None, and any other value is returned as a string.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat() + "Z"
    return str(value)
