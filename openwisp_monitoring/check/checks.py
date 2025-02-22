from datetime import datetime

from django.core.checks import Error, register

from . import settings as app_settings


@register()
def check_wifi_clients_snooze_schedule(app_configs, **kwargs):
    errors = []
    setting_name = 'OPENWISP_MONITORING_WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE'
    schedule = app_settings.WIFI_CLIENTS_CHECK_SNOOZE_SCHEDULE

    if not isinstance(schedule, (list, tuple)):
        errors.append(
            Error(
                'Invalid schedule format',
                hint='Schedule must be a list of date-time ranges',
                obj=setting_name,
            )
        )
        return errors

    for item in schedule:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            errors.append(
                Error(
                    f'Invalid schedule entry format: {item}',
                    hint='Each schedule entry must be a pair of start and end times',
                    obj=setting_name,
                )
            )
            continue

        start, end = item
        if not isinstance(start, str) or not isinstance(end, str):
            errors.append(
                Error(
                    f'Invalid time format: {item}',
                    hint='Use format "MM-DD HH:MM", "MM-DD", or "HH:MM"',
                    obj=setting_name,
                )
            )
            continue

        try:
            # Check if both are time format (HH:MM)
            if '-' not in start and '-' not in end:
                datetime.strptime(start, '%H:%M')
                datetime.strptime(end, '%H:%M')
            # Check if both are date format (MM-DD)
            elif ':' not in start and ':' not in end:
                datetime.strptime(start, '%m-%d')
                datetime.strptime(end, '%m-%d')
            # Check if both are date-time format (MM-DD HH:MM)
            elif len(start.split()) == 2 and len(end.split()) == 2:
                datetime.strptime(start, '%m-%d %H:%M')
                datetime.strptime(end, '%m-%d %H:%M')
            else:
                errors.append(
                    Error(
                        f'Inconsistent format: {item}',
                        hint='Both start and end must be in the same format (either both time or both date)',
                        obj=setting_name,
                    )
                )
        except ValueError:
            errors.append(
                Error(
                    f'Invalid date-time format: {item}',
                    hint='Use format "MM-DD HH:MM", "MM-DD", or "HH:MM"',
                    obj=setting_name,
                )
            )

    return errors
