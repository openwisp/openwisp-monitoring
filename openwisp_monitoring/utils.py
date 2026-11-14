import logging
from functools import wraps
from time import sleep

import pytz
from django.db import transaction

from .settings import MONITORING_TIMESERIES_RETRY_OPTIONS

logger = logging.getLogger(__name__)

# Mapping of deprecated IANA timezone aliases to their canonical replacements.
# Derived from the IANA tzdata "backward" compatibility file.
# These aliases are recognised by pytz but may not be present in all
# Go/InfluxDB timezone databases, causing query failures.
_DEPRECATED_TIMEZONE_MAP = {
    "Africa/Asmera": "Africa/Asmara",
    "Africa/Timbuktu": "Africa/Abidjan",
    "America/Argentina/ComodRivadavia": "America/Argentina/Catamarca",
    "America/Atka": "America/Adak",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
    "America/Catamarca": "America/Argentina/Catamarca",
    "America/Coral_Harbour": "America/Atikokan",
    "America/Cordoba": "America/Argentina/Cordoba",
    "America/Ensenada": "America/Tijuana",
    "America/Fort_Wayne": "America/Indiana/Indianapolis",
    "America/Godthab": "America/Nuuk",
    "America/Indianapolis": "America/Indiana/Indianapolis",
    "America/Jujuy": "America/Argentina/Jujuy",
    "America/Knox_IN": "America/Indiana/Knox",
    "America/Louisville": "America/Kentucky/Louisville",
    "America/Mendoza": "America/Argentina/Mendoza",
    "America/Montreal": "America/Toronto",
    "America/Nipigon": "America/Toronto",
    "America/Pangnirtung": "America/Iqaluit",
    "America/Porto_Acre": "America/Rio_Branco",
    "America/Rainy_River": "America/Winnipeg",
    "America/Rosario": "America/Argentina/Cordoba",
    "America/Santa_Isabel": "America/Tijuana",
    "America/Shiprock": "America/Denver",
    "America/Thunder_Bay": "America/Toronto",
    "America/Virgin": "America/Port_of_Spain",
    "America/Yellowknife": "America/Edmonton",
    "Antarctica/South_Pole": "Pacific/Auckland",
    "Asia/Ashkhabad": "Asia/Ashgabat",
    "Asia/Calcutta": "Asia/Kolkata",
    "Asia/Chongqing": "Asia/Shanghai",
    "Asia/Chungking": "Asia/Shanghai",
    "Asia/Dacca": "Asia/Dhaka",
    "Asia/Harbin": "Asia/Shanghai",
    "Asia/Istanbul": "Europe/Istanbul",
    "Asia/Kashgar": "Asia/Urumqi",
    "Asia/Katmandu": "Asia/Kathmandu",
    "Asia/Macao": "Asia/Macau",
    "Asia/Rangoon": "Asia/Yangon",
    "Asia/Saigon": "Asia/Ho_Chi_Minh",
    "Asia/Tel_Aviv": "Asia/Jerusalem",
    "Asia/Thimbu": "Asia/Thimphu",
    "Asia/Ujung_Pandang": "Asia/Makassar",
    "Asia/Ulan_Bator": "Asia/Ulaanbaatar",
    "Atlantic/Faeroe": "Atlantic/Faroe",
    "Atlantic/Jan_Mayen": "Europe/Oslo",
    "Australia/ACT": "Australia/Sydney",
    "Australia/Canberra": "Australia/Sydney",
    "Australia/LHI": "Australia/Lord_Howe",
    "Australia/NSW": "Australia/Sydney",
    "Australia/North": "Australia/Darwin",
    "Australia/Queensland": "Australia/Brisbane",
    "Australia/South": "Australia/Adelaide",
    "Australia/Tasmania": "Australia/Hobart",
    "Australia/Victoria": "Australia/Melbourne",
    "Australia/West": "Australia/Perth",
    "Australia/Yancowinna": "Australia/Broken_Hill",
    "Brazil/Acre": "America/Rio_Branco",
    "Brazil/DeNoronha": "America/Noronha",
    "Brazil/East": "America/Sao_Paulo",
    "Brazil/West": "America/Manaus",
    "Canada/Saskatchewan": "America/Regina",
    "Canada/Yukon": "America/Whitehorse",
    "Chile/Continental": "America/Santiago",
    "Chile/EasterIsland": "Pacific/Easter",
    "Cuba": "America/Havana",
    "Egypt": "Africa/Cairo",
    "Eire": "Europe/Dublin",
    "Europe/Nicosia": "Asia/Nicosia",
    "Europe/Tiraspol": "Europe/Chisinau",
    "GB": "Europe/London",
    "GB-Eire": "Europe/London",
    "Greenwich": "Etc/GMT",
    "Hongkong": "Asia/Hong_Kong",
    "Iceland": "Atlantic/Reykjavik",
    "Iran": "Asia/Tehran",
    "Israel": "Asia/Jerusalem",
    "Jamaica": "America/Jamaica",
    "Japan": "Asia/Tokyo",
    "Kwajalein": "Pacific/Kwajalein",
    "Libya": "Africa/Tripoli",
    "Mexico/BajaNorte": "America/Tijuana",
    "Mexico/BajaSur": "America/Mazatlan",
    "Mexico/General": "America/Mexico_City",
    "NZ": "Pacific/Auckland",
    "NZ-CHAT": "Pacific/Chatham",
    "Navajo": "America/Denver",
    "PRC": "Asia/Shanghai",
    "Pacific/Johnston": "Pacific/Honolulu",
    "Pacific/Ponape": "Pacific/Pohnpei",
    "Pacific/Samoa": "Pacific/Pago_Pago",
    "Pacific/Truk": "Pacific/Chuuk",
    "Pacific/Yap": "Pacific/Chuuk",
    "Poland": "Europe/Warsaw",
    "Portugal": "Europe/Lisbon",
    "ROC": "Asia/Taipei",
    "ROK": "Asia/Seoul",
    "Singapore": "Asia/Singapore",
    "Turkey": "Europe/Istanbul",
    "UCT": "Etc/UCT",
    "US/Aleutian": "America/Adak",
    "US/East-Indiana": "America/Indiana/Indianapolis",
    "US/Indiana-Starke": "America/Indiana/Knox",
    "US/Michigan": "America/Detroit",
    "US/Samoa": "Pacific/Pago_Pago",
    "Universal": "Etc/UTC",
    "W-SU": "Europe/Moscow",
    "Zulu": "Etc/UTC",
}


def normalize_timezone(tz_name):
    """Return the canonical IANA timezone name for a given timezone string.

    pytz accepts deprecated timezone aliases (e.g. ``Asia/Calcutta``) but
    InfluxDB's Go runtime may not include those legacy entries, causing
    query failures.  This function maps known deprecated names to their
    current canonical equivalents so the normalised value can be safely
    forwarded to the timeseries backend.

    Names already in ``pytz.common_timezones`` are returned unchanged.
    """
    if tz_name in pytz.common_timezones_set:
        return tz_name
    canonical = _DEPRECATED_TIMEZONE_MAP.get(tz_name)
    if canonical:
        return canonical
    # Fall back to the original name if no mapping is found; the caller
    # should have already validated the name with pytz.
    return tz_name


def transaction_on_commit(func):
    with transaction.atomic():
        transaction.on_commit(func)


def retry(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        max_retries = MONITORING_TIMESERIES_RETRY_OPTIONS.get("max_retries")
        delay = MONITORING_TIMESERIES_RETRY_OPTIONS.get("delay")
        for attempt_no in range(1, max_retries + 1):
            try:
                return method(*args, **kwargs)
            except Exception as err:
                logger.info(
                    f'Error while executing method "{method.__name__}":\n{err}\n'
                    f"Attempt {attempt_no} out of {max_retries}.\n"
                )
                if attempt_no > 3:
                    sleep(delay)
                if attempt_no == max_retries:
                    raise err

    return wrapper
