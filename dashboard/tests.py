from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Customer
from airtime.models import AirtimePurchase
from payments.models import MpesaPayment
from ussd.models import UssdSession

PAGES = ['dashboard:overview', 'dashboard:purchases', 'dashboard:payments', 'dashboard:sessions', 'dashboard:customers']


def make_purchase(status, payment_status=MpesaPayment.Status.SUCCESS, session='s1', amount=50):
    customer, _ = Customer.objects.get_or_create(phone_number='254712345678')
    payment = MpesaPayment.objects.create(
        phone_number=customer.phone_number, amount=amount, account_reference='QuickTop',
        description='Airtime', status=payment_status, mpesa_receipt_number='QKL123ABC',
    )
    return AirtimePurchase.objects.create(
        customer=customer, payment=payment, ussd_session_id=session,
        recipient_phone='254722000111', amount=amount, status=status,
    )


# Tests don't run collectstatic, so skip the hashed-manifest storage used in production.
PLAIN_STATIC = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(BACKGROUND_TASKS_INLINE=True, STORAGES=PLAIN_STATIC)
class DashboardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', password='pw', is_staff=True)

    def test_requires_staff_login(self):
        for name in PAGES:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn('/admin/login/', response['Location'])
        User.objects.create_user('plain', password='pw')
        self.client.login(username='plain', password='pw')
        self.assertEqual(self.client.get(reverse('dashboard:overview')).status_code, 302)

    def test_pages_render_empty_and_with_data(self):
        self.client.login(username='staff', password='pw')
        for name in PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

        make_purchase(AirtimePurchase.Status.DELIVERED, session='s1')
        make_purchase(AirtimePurchase.Status.FAILED, session='s2', amount=20)
        make_purchase(AirtimePurchase.Status.PAYMENT_FAILED, MpesaPayment.Status.FAILED, session='s3')
        UssdSession.objects.create(session_id='s1', msisdn='254712345678', text='1*1*50*1', last_response='Enter PIN', ended=True)
        for name in PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

        stats = self.client.get(reverse('dashboard:overview')).context['stats']
        self.assertEqual(stats['collected_all'], Decimal('70'))
        self.assertEqual(stats['delivered_value'], Decimal('50'))
        self.assertEqual(stats['refunds_due_count'], 1)
        self.assertEqual(stats['refunds_due_value'], Decimal('20'))
        self.assertEqual(stats['success_rate'], 67)

    def test_filters_and_search(self):
        self.client.login(username='staff', password='pw')
        make_purchase(AirtimePurchase.Status.DELIVERED, session='s1')
        make_purchase(AirtimePurchase.Status.FAILED, session='s2')
        url = reverse('dashboard:purchases')
        self.assertEqual(len(self.client.get(url, {'status': 'failed'}).context['object_list']), 1)
        self.assertEqual(len(self.client.get(url, {'q': '0722000111'}).context['object_list']), 2)
        self.assertEqual(len(self.client.get(url, {'q': 'QKL123'}).context['object_list']), 2)
        self.assertEqual(len(self.client.get(url, {'q': '722000'}).context['object_list']), 2)

    @mock.patch('airtime.statum.send_airtime', return_value='statum-req-9')
    def test_retry_failed_purchase(self, send_airtime):
        self.client.login(username='staff', password='pw')
        failed = make_purchase(AirtimePurchase.Status.FAILED, session='s1')
        unpaid = make_purchase(AirtimePurchase.Status.PAYMENT_FAILED, MpesaPayment.Status.FAILED, session='s2')

        self.client.post(reverse('dashboard:retry-purchase', args=[failed.pk]))
        failed.refresh_from_db()
        self.assertEqual(failed.status, AirtimePurchase.Status.SENDING)
        self.assertEqual(failed.statum_request_id, 'statum-req-9')

        self.client.post(reverse('dashboard:retry-purchase', args=[unpaid.pk]))
        unpaid.refresh_from_db()
        self.assertEqual(unpaid.status, AirtimePurchase.Status.PAYMENT_FAILED)
        send_airtime.assert_called_once()

    def test_retry_requires_post(self):
        self.client.login(username='staff', password='pw')
        failed = make_purchase(AirtimePurchase.Status.FAILED)
        self.assertEqual(self.client.get(reverse('dashboard:retry-purchase', args=[failed.pk])).status_code, 405)
