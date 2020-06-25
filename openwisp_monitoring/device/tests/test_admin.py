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
Check = load_model('check', 'Check')


class TestAdmin(DeviceMonitoringTestCase):
    """
    Test the additions of openwisp-monitoring to DeviceAdmin
    """

    def _login_admin(self):
        User = get_user_model()
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
        self.assertContains(r, check.name)
        self.assertContains(r, check.params)

    def test_no_device_data(self):
        d = self._create_device(organization=self._create_org())
        url = reverse('admin:config_device_change', args=[d.pk])
        self._login_admin()
        r = self.client.get(url)
        self.assertNotContains(r, '<h2>Status</h2>')

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
            f'{ct}-0-active': True,
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
