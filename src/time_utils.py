"""Time utilities for handling Slovak timezone complexities."""

from datetime import datetime, timedelta, timezone
from typing import List
import calendar


def get_current_time_windows(now_utc: datetime | None = None) -> List[datetime]:
    """
    Generate list of possible file timestamps accounting for Slovak timezone.

    CRITICAL: Slovak weather files use CEST/CET in URLs but data is UTC+1.
    We need to check multiple possible time windows due to:
    1. Summer (CEST = UTC+2) vs Winter (CET = UTC+1) time
    2. File publication delays
    3. Rounding to 5-minute intervals

    Args:
        now_utc: Current UTC time (defaults to datetime.utcnow())

    Returns:
        List of datetime objects in priority order (most likely first)
    """
    if now_utc is None:
        now_utc = datetime.utcnow()

    windows = []

    # Try both CEST (summer) and CET (winter) - we don't know which is active
    for tz_offset in [2, 1]:  # CEST first, then CET
        local_time = now_utc + timedelta(hours=tz_offset)

        # Round DOWN to 5-minute interval (files are published on 5-min boundaries)
        minute = (local_time.minute // 5) * 5
        window_base = local_time.replace(minute=minute, second=0, microsecond=0)

        # Generate cascade: current, -5min, -10min, -15min
        # (account for publication delays)
        for offset_minutes in [0, 5, 10, 15]:
            window = window_base - timedelta(minutes=offset_minutes)
            if window not in windows:  # Avoid duplicates
                windows.append(window)

    # Sort by most recent first
    windows.sort(reverse=True)
    return windows[:8]  # Limit to 8 most likely candidates


def build_url_timestamp(timestamp: datetime) -> str:
    """
    Build the timestamp part of SHMU URL.

    Example: 2025-09-16 18:35:00 -> "2025-09-16 18-35-00-264"

    Args:
        timestamp: Datetime in local Slovak time (CEST/CET)

    Returns:
        Formatted timestamp string for URL
    """
    # Format: YYYY-MM-DD HH-MM-SS-fff
    return timestamp.strftime("%Y-%m-%d %H-%M-%S-264")


def build_date_path(timestamp: datetime) -> str:
    """
    Build the date path part of SHMU URL.

    Example: 2025-09-16 18:35:00 -> "20250916"

    Args:
        timestamp: Datetime in local Slovak time

    Returns:
        Date string for URL path
    """
    return timestamp.strftime("%Y%m%d")


def fix_data_timestamp(data_timestamp_str: str) -> datetime:
    """
    Convert data timestamp from Slovak source to proper UTC.

    CRITICAL: SHMU data timestamps are marked as UTC but are actually UTC+1.
    We need to subtract 1 hour to get true UTC.

    Args:
        data_timestamp_str: ISO timestamp string from JSON data

    Returns:
        Corrected UTC datetime
    """
    # Parse the timestamp (it's in ISO format like "2025-09-16T18:35:00")
    data_time = datetime.fromisoformat(data_timestamp_str.replace('Z', ''))

    # Subtract 1 hour to convert from "fake UTC" to real UTC
    return data_time - timedelta(hours=1)


def is_daylight_saving_time(dt: datetime) -> bool:
    """
    Check if given date is in daylight saving time for Slovakia.

    Slovakia follows EU DST rules:
    - Begins: Last Sunday in March at 02:00 CET (becomes 03:00 CEST)
    - Ends: Last Sunday in October at 03:00 CEST (becomes 02:00 CET)

    Args:
        dt: Datetime to check

    Returns:
        True if date is in DST period
    """
    year = dt.year

    # Find last Sunday in March
    march_last_day = 31
    while calendar.weekday(year, 3, march_last_day) != 6:  # 6 = Sunday
        march_last_day -= 1
    dst_start = datetime(year, 3, march_last_day, 2, 0, 0)

    # Find last Sunday in October
    october_last_day = 31
    while calendar.weekday(year, 10, october_last_day) != 6:
        october_last_day -= 1
    dst_end = datetime(year, 10, october_last_day, 3, 0, 0)

    return dst_start <= dt < dst_end


def get_slovak_timezone_offset(dt: datetime) -> int:
    """
    Get timezone offset for Slovakia at given datetime.

    Args:
        dt: Datetime to check

    Returns:
        Hours offset from UTC (1 for CET, 2 for CEST)
    """
    return 2 if is_daylight_saving_time(dt) else 1


def utc_to_slovak_time(utc_dt: datetime) -> datetime:
    """
    Convert UTC datetime to Slovak local time.

    Args:
        utc_dt: UTC datetime

    Returns:
        Local Slovak datetime
    """
    offset = get_slovak_timezone_offset(utc_dt)
    return utc_dt + timedelta(hours=offset)


def slovak_time_to_utc(slovak_dt: datetime) -> datetime:
    """
    Convert Slovak local time to UTC.

    Args:
        slovak_dt: Slovak local datetime

    Returns:
        UTC datetime
    """
    offset = get_slovak_timezone_offset(slovak_dt)
    return slovak_dt - timedelta(hours=offset)