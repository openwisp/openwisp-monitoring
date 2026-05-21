import logging
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings

logger = logging.getLogger(__name__)

_INVALID_TIMEZONE = object()

_LEGACY_TIMEZONE_MAP = {
    "Asia/Calcutta": "Asia/Kolkata",
    "Asia/Saigon": "Asia/Ho_Chi_Minh",
    "Asia/Katmandu": "Asia/Kathmandu",
    "US/Eastern": "America/New_York",
    "US/Pacific": "America/Los_Angeles",
    "Europe/Kiev": "Europe/Kyiv",
    "Asia/Rangoon": "Asia/Yangon",
    "America/Godthab": "America/Nuuk",
    "Asia/Ulan_Bator": "Asia/Ulaanbaatar",
    "US/Central": "America/Chicago",
    "US/Mountain": "America/Denver",
}


def normalize_timezone(tz_name):
    """
    Normalize known legacy timezone aliases.

    Invalid or made-up timezones are returned unchanged so the existing
    pytz-based validation in the API views can still raise a 400 response.
    """
    fallback = getattr(settings, "TIME_ZONE", None) or "UTC"
    if not tz_name:
        return fallback

    if tz_name not in _LEGACY_TIMEZONE_MAP:
        return tz_name

    normalized_tz = _normalize_timezone_cached(tz_name)
    if normalized_tz is _INVALID_TIMEZONE:
        logger.warning(
            f"Normalized timezone '{_LEGACY_TIMEZONE_MAP[tz_name]}' "
            "not found in OS zoneinfo. "
            f"Falling back to system TIME_ZONE '{fallback}'."
        )
        return fallback
    return normalized_tz


@lru_cache(maxsize=128)
def _normalize_timezone_cached(tz_name):
    """
    Cache only explicit legacy timezone normalization results.
    """
    normalized_tz = _LEGACY_TIMEZONE_MAP[tz_name]

    try:
        ZoneInfo(normalized_tz)
        if normalized_tz != tz_name:
            logger.info(
                f"Normalized deprecated timezone '{tz_name}' to '{normalized_tz}'"
            )
        return normalized_tz
    except ZoneInfoNotFoundError:
        return _INVALID_TIMEZONE
