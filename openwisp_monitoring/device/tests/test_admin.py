from django.contrib.auth import get_user_model
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.urls import reverse
from django.utils.timezone import now
from swapper import get_model_name, load_model

from ...check.settings import CHECK_CLASSES
from ..admin import CheckInline, CheckInlineFormSet
from . import DeviceMonitoringTestCase

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
DeviceData = load_model('device_monitoring', 'DeviceData')
User = get_user_model()
Check = load_model('check', 'Check')


class TestAdmin(DeviceMonitoringTestCase):
    """
    Test the additions of openwisp-monitoring to DeviceAdmin
    """

    def _login_admin(self):
        u = User.objects.create_superuser('admin', 'admin', 'test@test.com')
        self.client.force_login(u)

    def test_device_admin(self):
        dd = self.create_test_adata()
        check = Check.objects.create(
            name='Ping check', check=CHECK_CLASSES[0][0], content_object=dd, params={},
        )
        url = reverse('admin:config_device_change', args=[dd.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertContains(r, '<h2>Status</h2>')
        self.assertContains(r, '<h2>Charts</h2>')
        self.assertContains(r, '<h2>Checks</h2>')
        self.assertContains(r, 'Storage')
        self.assertContains(r, 'CPU')
        self.assertContains(r, 'RAM status')
        self.assertContains(r, 'AlertSettings')
        self.assertContains(r, 'Is healthy')
        self.assertContains(r, check.name)
        self.assertContains(r, check.params)

    def test_no_device_data(self):
        d = self._create_device(organization=self._create_org())
        url = reverse('admin:config_device_change', args=[d.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertNotContains(r, '<h2>Status</h2>')
        self.assertNotContains(r, 'AlertSettings')

    def test_device_add_view(self):
        self._login_admin()
        url = reverse('admin:config_device_add')
        r = self.client.get(url)
        self.assertNotContains(r, 'AlertSettings')
        self.assertContains(r, '<h2>Configuration</h2>')
        self.assertContains(r, '<h2>Map</h2>')
        self.assertContains(r, '<h2>Credentials</h2>')
        self.assertContains(r, '<h2>Checks</h2>')

    def test_remove_invalid_interface(self):
        d = self._create_device(organization=self._create_org())
        dd = DeviceData(name='test-device', pk=d.pk)
        self._post_data(
            d.id,
            d.key,
            {'type': 'DeviceMonitoring', 'interfaces': [{'name': 'br-lan'}]},
        )
        url = reverse('admin:config_device_change', args=[dd.pk])
        self._login_admin()
        self.client.get(url)

    def test_wifi_clients_admin(self):
        self._login_admin()
        dd = self.create_test_adata(no_resources=True)
        url = reverse('admin:config_device_change', args=[dd.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, '00:ee:ad:34:f5:3b')

    def test_interface_properties_admin(self):
        self._login_admin()
        dd = self.create_test_adata(no_resources=True)
        url = reverse('admin:config_device_change', args=[dd.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, '44:d1:fa:4b:38:44')
        self.assertContains(r1, 'Transmit Queue Length')
        self.assertContains(r1, 'Up')
        self.assertContains(r1, 'Multicast')
        self.assertContains(r1, 'MTU')

    def test_interface_bridge_admin(self):
        self._login_admin()
        d = self._create_device(organization=self._create_org())
        dd = DeviceData(name='test-device', pk=d.pk)
        data = self._data()
        del data['resources']
        self._post_data(
            d.id,
            d.key,
            {
                'type': 'DeviceMonitoring',
                'interfaces': [
                    {
                        'name': 'br-lan',
                        'type': 'bridge',
                        'bridge_members': ['tap0', 'wlan0', 'wlan1'],
                        'stp': True,
                    }
                ],
            },
        )
        url = reverse('admin:config_device_change', args=[dd.id])
        r1 = self.client.get(url, follow=True)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, 'Bridge Members')
        self.assertContains(r1, 'tap0, wlan0, wlan1')
        self.assertContains(r1, 'Spanning Tree Protocol')

    def test_uuid_bug(self):
        dd = self.create_test_adata(no_resources=True)
        uuid = str(dd.pk).replace('-', '')
        url = reverse('admin:config_device_change', args=[uuid])
        self._login_admin()
        r = self.client.get(url)
        self.assertContains(r, '<h2>Status</h2>')

    def test_check_inline_formset(self):
        d = self._create_device(organization=self._create_org())
        check_inline_formset = generic_inlineformset_factory(
            model=Check, form=CheckInline.form, formset=CheckInlineFormSet
        )
        # model_name changes if swapped
        model_name = get_model_name('check', 'Check').lower().replace('.', '-')
        ct = f'{model_name}-content_type-object_id'
        data = {
            f'{ct}-TOTAL_FORMS': '1',
            f'{ct}-INITIAL_FORMS': '0',
            f'{ct}-MAX_NUM_FORMS': '0',
            f'{ct}-0-name': 'Ping Check',
            f'{ct}-0-check': CHECK_CLASSES[0][0],
            f'{ct}-0-params': '{}',
            f'{ct}-0-is_active': True,
            f'{ct}-0-created': now(),
            f'{ct}-0-modified': now(),
        }
        formset = check_inline_formset(data)
        formset.instance = d
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.errors, [{}])
        self.assertEqual(formset.non_form_errors(), [])
        form = formset.forms[0]
        form.cleaned_data = data
        form.save(commit=True)
        self.assertEqual(Check.objects.count(), 1)
        c = Check.objects.first()
        self.assertEqual(c.name, 'Ping Check')
        self.assertEqual(c.content_object, d)

    def test_metric_health_list(self):
        dd = self.create_test_adata()
        url = reverse('admin:config_device_change', args=[dd.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertNotContains(r, '<label>Metric health:</label>')
        m = Metric.objects.filter(configuration='disk').first()
        m.write(m.alertsettings.threshold + 0.1)
        self.assertFalse(m.is_healthy)
        self.assertEqual(dd.monitoring.status, 'problem')
        r = self.client.get(url)
        self.assertContains(r, '<label>Metric health:</label>')
        # Clients and Traffic metrics
        interface_metrics = dd.metrics.filter(is_healthy=None)
        other_metrics = dd.metrics.all().exclude(is_healthy=None)
        for metric in interface_metrics:
            self.assertNotContains(r, f'{metric.name}</li>')
        for metric in other_metrics:
            health = 'yes' if metric.is_healthy else 'no'
            self.assertContains(
                r,
                f'<li><img src="/static/admin/img/icon-{health}.svg" '
                f'alt="health"> {metric.name}</li>',
            )
