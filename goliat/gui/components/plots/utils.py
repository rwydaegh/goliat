"""Common utilities for plotting components."""

from datetime import datetime, timezone, timedelta


def convert_to_utc_plus_one(timestamp: datetime) -> datetime:
    """Convert a datetime to UTC+1 timezone.

    Handles both naive (assumed UTC) and timezone-aware datetimes.
    Works reliably across VMs worldwide by always normalizing to UTC first.

    Args:
        timestamp: Datetime to convert (can be naive or timezone-aware).
                  If naive, assumes it's already in UTC (recommended usage).

    Returns:
        Datetime in UTC+1 timezone (timezone-aware).
    """
    utc_plus_one_tz = timezone(timedelta(hours=1))

    # If timestamp is naive, assume it's UTC (most reliable for VMs worldwide)
    if timestamp.tzinfo is None:
        # Treat naive datetime as UTC
        utc_timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        # Convert timezone-aware datetime to UTC first
        utc_timestamp = timestamp.astimezone(timezone.utc)

    # Convert UTC to UTC+1
    return utc_timestamp.astimezone(utc_plus_one_tz)
