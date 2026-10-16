import json
from itertools import product

from django.test import TestCase, override_settings

from accounts.phone import normalize_msisdn
from airtime.models import AirtimePurchase

from . import menu
from .models import UssdSession

CTX = menu.Context(msisdn='254712345678', session_id='s1', min_amount=10, max_amount=10000)


class PhoneTests(TestCase):
    def test_normalize(self):
        for raw in ('0712345678', '712345678', '254712345678', '+254 712 345 678', 254712345678):
            self.assertEqual(normalize_msisdn(raw), '254712345678')
        self.assertEqual(normalize_msisdn('0110123456'), '254110123456')
        for raw in ('', '12345', '0812345678', 'abc', None, '07123456789'):
            self.assertIsNone(normalize_msisdn(raw))


class MenuTests(TestCase):
    def test_main_menu(self):
        response = menu.handle('', CTX)
        self.assertFalse(response.end)
        self.assertTrue(response.text.startswith('Welcome to QuickTop'))
        self.assertIn('1. Buy Airtime', response.text)

    def test_airtime_for_self(self):
        response = menu.handle('1*1*50', CTX)
        self.assertIn('Buy KES 50 airtime for 0712345678', response.text)
        response = menu.handle('1*1*50*1', CTX)
        self.assertTrue(response.end)
        self.assertIsNotNone(response.action)

    def test_airtime_for_other_number(self):
        response = menu.handle('1*2*0722000111*100', CTX)
        self.assertIn('for 0722000111', response.text)
        self.assertIn('Pay via M-Pesa 0712345678', response.text)

    def test_invalid_input_reprompts(self):
        response = menu.handle('1*2*12345', CTX)
        self.assertTrue(response.text.startswith('Invalid phone number.'))
        # The bad entry is skipped; a valid one moves on.
        response = menu.handle('1*2*12345*0722000111', CTX)
        self.assertTrue(response.text.startswith('Enter amount'))

    def test_amount_limits(self):
        self.assertIn('Amount must be', menu.handle('1*1*5', CTX).text)
        self.assertIn('Amount must be', menu.handle('1*1*20000', CTX).text)
        self.assertIn('whole shillings', menu.handle('1*1*abc', CTX).text)

    def test_back_and_home(self):
        self.assertTrue(menu.handle('1*2*0', CTX).text.startswith('Buy Airtime'))
        self.assertTrue(menu.handle('1*2*00', CTX).text.startswith('Welcome to QuickTop'))
        self.assertTrue(menu.handle('1*0*2', CTX).text.startswith('Buy Data'))

    def test_cancel(self):
        response = menu.handle('1*1*50*2', CTX)
        self.assertTrue(response.end)
        self.assertIsNone(response.action)
        self.assertIn('cancelled', response.text)

    def test_data_placeholder(self):
        self.assertIn('MTN bundles', menu.handle('2*3', CTX).text)
        response = menu.handle('2*1*3*1', CTX)
        self.assertTrue(response.end)
        self.assertIn('coming soon', response.text)
        self.assertIsNone(response.action)

    def test_utilities_placeholder(self):
        self.assertIn('meter number', menu.handle('3*2', CTX).text)
        self.assertIn('Pay KES 1,500 to ZUKU', menu.handle('3*1*123456*1500', CTX).text)
        self.assertIn('ZUKU payment is coming soon', menu.handle('3*1*123456*1500*1', CTX).text)

    def test_insurance_placeholder(self):
        response = menu.handle('4*2', CTX)
        self.assertTrue(response.end)
        self.assertIn('Health insurance is coming soon', response.text)

    def test_every_screen_fits_160_chars(self):
        inputs = ['', '1', '2', '3', '4', '0', '0722000111', '10000', '123456', 'x']
        for path in product(inputs, repeat=4):
            text = '*'.join(p for p in path if p != '')
            response = menu.handle(text, CTX)
            self.assertLessEqual(len(response.text), menu.MAX_TEXT_LENGTH, msg=f'{text!r}: {response.text!r}')


@override_settings(BRILIO_CALLBACK_SECRETS=['secret-1', 'secret-2'], DEBUG=False)
class CallbackViewTests(TestCase):
    def post(self, text='', secret='secret-1', session='sess-1', msisdn=254712345678):
        payload = {
            'msisdn': msisdn, 'sessionId': session, 'text': text, 'countryCode': 254,
            'network': 'Safaricom KE', 'level': 1, 'code': '4320', 'input': '',
        }
        headers = {'Authentication': secret} if secret else {}
        return self.client.post('/ussd/callback/', json.dumps(payload), content_type='application/json', headers=headers)

    def test_rejects_bad_secret(self):
        self.assertEqual(self.post(secret='wrong').status_code, 401)
        self.assertEqual(self.post(secret=None).status_code, 401)

    def test_accepts_either_rotating_secret(self):
        self.assertEqual(self.post(secret='secret-2').status_code, 200)

    def test_main_menu_and_session_logged(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['responseType'], 'CON')
        self.assertIn('Welcome to QuickTop', body['text'])
        self.assertTrue(UssdSession.objects.filter(session_id='sess-1', msisdn='254712345678').exists())

    @override_settings(BRILIO_CALLBACK_SECRETS=[])
    def test_missing_secret_config_rejects_in_production(self):
        self.assertEqual(self.post().status_code, 401)

    def test_confirm_creates_purchase(self):
        with self.captureOnCommitCallbacks(execute=False):
            body = self.post(text='1*2*0722000111*50*1').json()
        self.assertEqual(body['responseType'], 'END')
        purchase = AirtimePurchase.objects.get(ussd_session_id='sess-1')
        self.assertEqual(purchase.recipient_phone, '254722000111')
        self.assertEqual(purchase.payment.phone_number, '254712345678')
        self.assertEqual(purchase.amount, 50)
