# [DevBounty AI]: File optimized for resolution.


```python
from rest_framework import filters
from rest_framework import viewsets
from rest_framework import serializers

class DashboardViewSet(viewsets.ModelViewSet):
    # Define the model and serializer
    queryset = Dashboard.objects.all()
    serializer_class = DashboardSerializer

    # Define the filterset_fields configuration
    filterset_fields = [
        'organization_slug',
        'location_id',
        'floorplan_id',
        'time',
        'start',
        'end',
    ]

class DashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dashboard
        fields = [
            'organization_slug',
            'location_id',
            'floorplan_id',
            'time',
            'start',
            'end',
        ]

import json
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from swapper import load_model

from openwisp_controller.config.tests.utils import CreateDeviceGroupMixin
from openwisp_controller.geo.tests.utils import TestGeoMixin
from openwisp_users.tests.test_api import AuthenticationMixin
from openwisp_users.tests.utils import TestMultitenantAdminMixin
from openwisp_utils.tests import capture_any_output, catch_signal

from ... import settings as monitoring_settings
from ...monitoring.signals import post_metric_write, pre_metric_write
from ..api.serializers import WifiSessionSerializer
from ..signals import device_metrics_received
from . import DeviceMonitoringTestCase, TestWifiClientSessionMixin

start_time = timezone.now()
User = get_user_model()
Chart = load_model("monitoring", "Chart")
Metric = load_model("monitoring", "Metric")
DeviceData = load_model("device_monitoring", "DeviceData")
# needed for config.geo
Device = load_model("config", "Device")
DeviceLocation = load_model("geo", "DeviceLocation")
FloorPlan = load_model("geo", "FloorPlan")
Location = load_model("geo", "Location")
WifiClient = load_model("device_monitoring", "WifiClient")
WifiSession = load_model("device_monitoring", "WifiSession")
Group = load_model("openwisp_users", "Group")


class TestDeviceApi(AuthenticationMixin, TestGeoMixin, DeviceMonitoringTestCase):
    """Tests API (device metric collection)."""

    location_model = Location
    object_location_model = DeviceLocation
    object_model = Device
    floorplan_model = FloorPlan
    # Exclude general metrics from the query
    metric_queryset = Metric.objects.exclude(object_id=None)
    # Exclude general charts from the query
    chart_queryset = Chart.objects.exclude(metric__object_id=None)
    _RESPONSE_KEYS = [
        "id",
        "name",
        "organization",
        "group",
        "mac_address",
        "key",
        "last_ip",
        "management_ip",
        "model",
        "os",
        "system",
        "notes",
        "config",
        "monitoring",
        "created",
        "modified",
        "charts",
        "x",
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Populate the ContentType cache to avoid queries during test
        ContentType.objects.get_for_model(Device)

    def setUp(self):
        self._login_admin()

    def tearDown(self):
        super().tearDown()
        cache.clear()

    def _login_admin(self):
        u = User.objects.create_superuser("admin", "admin", "test@test.com")
        self.client.force_login(u)

    def _assert_device_info(self, device=None, data=None):
        self.assertEqual(data["id"], str(device.pk))
        self.assertEqual(data["name"], device.name)
        self.assertEqual(data["organization"], device.organization.pk)
        self.assertEqual(data["group"], device.group)
        self.assertEqual(data["mac_address"], device.mac_address)
        self.assertEqual(data["key"], device.key)
        self.assertEqual(data["last_ip"], device.last_ip)
        self.assertEqual(data["management_ip"], device.management_ip)
        self.assertEqual(data["model"], device.model)
        self.assertEqual(data["os"], device.os)
        self.assertEqual(data["system"], device.system)
        self.assertEqual(data["notes"], device.notes)
        self.assertIsNone(data["config"])

    def _assert_device_metrics_info(self, data=None, detail=True, charts=True):
        self.assertIn("monitoring", data)
        self.assertIn("status", data["monitoring"])
        if charts:
            self.assertEqual(len(list(data["charts"])), 7)
        if detail:
            self.assertIn("related_metrics", data["monitoring"])
            metrics = list(data["monitoring"]["related_metrics"])
            self.assertEqual(metrics[0]["name"], "CPU usage")
            self.assertEqual(metrics[0]["is_healthy"], True)
            self.assertEqual(metrics[1]["name"], "Disk usage")
            self.assertEqual(metrics[1]["is_healthy"], True)
            self.assertEqual(metrics[2]["name"], "Memory usage")
            self.assertEqual(metrics[2]["is_healthy"], True)
            self.assertEqual(metrics[3]["name"], "wlan0 traffic")
            self.assertEqual(metrics[3]["is_healthy"], None)
            self.assertEqual(metrics[4]["name"], "wlan0 wifi clients")
            self.assertEqual(metrics[4]["is_healthy"], None)
            self.assertEqual(metrics[5]["name"], "wlan1 traffic")
            self.assertEqual(metrics[5]["is_healthy"], None)
            self.assertEqual(metrics[6]["name"], "wlan1 wifi clients")
            self.assertEqual(metrics[6]["is_healthy"], None)

    def test_404(self):
        r = self.client.post(reverse('api:device-list'))