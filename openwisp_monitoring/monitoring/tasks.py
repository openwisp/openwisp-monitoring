from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now, timedelta
from swapper import load_model

from ..db import timeseries_db
from ..db.exceptions import TimeseriesWriteException
from .settings import RETRY_OPTIONS
from .signals import post_metric_write


@shared_task(bind=True, autoretry_for=(TimeseriesWriteException,), **RETRY_OPTIONS)
def timeseries_write(
    self, name, values, metric_pk=None, check_threshold_kwargs=None, **kwargs
):
    """
    write with exponential backoff on a failure
    """
    timeseries_db.write(name, values, **kwargs)
    if not metric_pk or not check_threshold_kwargs:
        return
    try:
        metric = load_model('monitoring', 'Metric').objects.get(pk=metric_pk)
    except ObjectDoesNotExist:
        # The metric can be deleted by the time threshold is being checked.
        # This can happen as the task is being run async.
        pass
    else:
        metric.check_threshold(**check_threshold_kwargs)
        signal_kwargs = dict(
            sender=metric.__class__,
            metric=metric,
            values=values,
            time=kwargs.get('timestamp'),
            current=kwargs.get('current', 'False'),
        )
        post_metric_write.send(**signal_kwargs)


@shared_task
def migrate_timeseries_database():
    """
    Perform migrations on timeseries database
    asynchronously for changes introduced in
    https://github.com/openwisp/openwisp-monitoring/pull/368

    To be removed in 1.1.0 release.
    """
    from .migrations.influxdb.influxdb_alter_structure_0006 import (
        migrate_influxdb_structure,
    )

    migrate_influxdb_structure()


@shared_task
def save_wifi_clients_and_sessions(device_data, device_pk):
    _WIFICLIENT_FIELDS = ['vendor', 'ht', 'vht', 'wmm', 'wds', 'wps']
    WifiClient = load_model('monitoring', 'WifiClient')
    WifiSession = load_model('monitoring', 'WifiSession')

    active_wireless_sessions = []
    interfaces = device_data.get('interfaces', [])
    for interface in interfaces:
        if interface.get('type') != 'wireless':
            continue
        interface_name = interface.get('name')
        wireless = interface.get('wireless', {})

        wireless_ssid = wireless.get('ssid')
        wireless_clients = wireless.get('clients', [])
        for client in wireless_clients:
            # Save WifiClient
            client_obj, created = WifiClient.objects.get_or_create(
                mac_address=client.get('mac')
            )
            update_fields = []
            for field in _WIFICLIENT_FIELDS:
                if getattr(client_obj, field) != client.get(field):
                    setattr(client_obj, field, client.get(field))
                    update_fields.append(field)
            if update_fields:
                client_obj.full_clean()
                client_obj.save(update_fields=update_fields)

            # Save WifiSession
            session_object, _ = WifiSession.objects.get_or_create(
                device_id=device_pk,
                interface_name=interface_name,
                ssid=wireless_ssid,
                wifi_client=client_obj,
            )
            active_wireless_sessions.append(session_object.pk)

    # Close open WifiSession
    WifiSession.objects.filter(device_id=device_pk, stop_time=None,).exclude(
        pk__in=active_wireless_sessions
    ).update(stop_time=now())


@shared_task
def delete_wifi_clients_and_session(days=6 * 30):
    WifiClient = load_model('monitoring', 'WifiClient')
    WifiSession = load_model('monitoring', 'WifiSession')

    WifiSession.objects.filter(start_time__lte=(now() - timedelta(days=days))).delete()
    WifiClient.objects.exclude(
        mac_address__in=WifiSession.objects.values_list('wifi_client')
    ).delete()
