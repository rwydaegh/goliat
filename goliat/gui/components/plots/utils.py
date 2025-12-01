"""Common utilities for plotting components."""

import socket
import struct
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

# Cache for NTP time to avoid querying NTP too frequently
_ntp_cache: Optional[Tuple[datetime, float]] = None
_NTP_CACHE_DURATION = 30.0  # Cache for 30 seconds


def get_ntp_utc_time() -> datetime:
    """Get current UTC time from NTP server (bypasses system clock).

    Uses NTP to get accurate time independent of system clock issues.
    Caches the result for 30 seconds to minimize performance impact.
    Falls back to system time if NTP query fails.

    Returns:
        Current UTC time as timezone-aware datetime.
    """
    global _ntp_cache

    # Check cache first
    current_system_time = time.time()
    if _ntp_cache is not None:
        cached_time, cache_timestamp = _ntp_cache
        if current_system_time - cache_timestamp < _NTP_CACHE_DURATION:
            # Return cached time adjusted by elapsed time since cache
            elapsed = current_system_time - cache_timestamp
            return cached_time + timedelta(seconds=elapsed)

    # Query NTP
    try:
        ntp_query = bytearray(48)
        ntp_query[0] = 0x1B  # NTP version 3, client mode

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.0)  # 2 second timeout
        s.sendto(ntp_query, ("pool.ntp.org", 123))
        data, _ = s.recvfrom(48)
        s.close()

        # Extract timestamp from NTP response (bytes 40-44)
        ntp_timestamp = struct.unpack("!I", data[40:44])[0] - 2208988800  # Convert from NTP epoch to Unix epoch
        utc_time = datetime.fromtimestamp(ntp_timestamp, tz=timezone.utc)

        # Cache the result
        _ntp_cache = (utc_time, current_system_time)
        return utc_time
    except Exception:
        # Fallback to system time if NTP fails (but log a warning)
        # In production, you might want to log this
        fallback_time = datetime.now(timezone.utc)
        # Still cache it to avoid repeated failures
        _ntp_cache = (fallback_time, current_system_time)
        return fallback_time


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
