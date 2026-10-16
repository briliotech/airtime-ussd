import json
from unittest import mock

from django.test import TestCase, override_settings

from payments.models import MpesaPayment

from .models import AirtimePurchase
from .services import start_airtime_purchase

STK_ACCEPTED = {
    'MerchantRequestID': 'mr-1',
    'CheckoutRequestID': 'ws_CO_1',
    'ResponseCode': '0',
    'ResponseDescription': 'Success. Request accepted for processing',
}


def stk_callback(result_code=0, amount=50, checkout='ws_CO_1'):
    stk = {
        'MerchantRequestID': 'mr-1',
        'CheckoutRequestID': checkout,
        'ResultCode': result_code,
        'ResultDesc': 'The service request is processed successfully.' if result_code == 0 else 'Request cancelled by user',
    }
    if result_code == 0:
        stk['CallbackMetadata'] = {'Item': [
            {'Name': 'Amount', 'Value': amount},
            {'Name': 'MpesaReceiptNumber', 'Value': 'QKL123ABC'},
            {'Name': 'TransactionDate', 'Value': 20261016150000},
            {'Name': 'PhoneNumber', 'Value': 254712345678},
        ]}
    return {'Body': {'stkCallback': stk}}


@override_settings(
    BACKGROUND_TASKS_INLINE=True,
    STK_PUSH_DELAY_SECONDS=0,
)
class AirtimeFlowTests(TestCase):
    def setUp(self):
        stk = mock.patch('payments.mpesa.stk_push', return_value=STK_ACCEPTED)
        statum = mock.patch('airtime.statum.send_airtime', return_value='statum-req-1')
        self.stk_push = stk.start()
        self.send_airtime = statum.start()
        self.addCleanup(mock.patch.stopall)

    def start(self):
        with self.captureOnCommitCallbacks(execute=True):
            return start_airtime_purchase('sess-1', '254712345678', '254722000111', 50)

    def mpesa_callback(self, body):
        return self.client.post('/payments/mpesa/callback/', json.dumps(body), content_type='application/json')

    def statum_callback(self, body):
        return self.client.post('/airtime/statum/callback/', json.dumps(body), content_type='application/json')

    def test_happy_path(self):
        purchase = self.start()
        self.stk_push.assert_called_once()
        self.assertEqual(self.stk_push.call_args.kwargs['phone_number'], '254712345678')
        self.assertTrue(self.stk_push.call_args.kwargs['callback_url'].endswith('/payments/mpesa/callback/'))
        self.assertEqual(MpesaPayment.objects.get().status, MpesaPayment.Status.INITIATED)

        response = self.mpesa_callback(stk_callback())
        self.assertEqual(response.json(), {'ResultCode': 0, 'ResultDesc': 'Accepted'})
        self.send_airtime.assert_called_once_with('254722000111', purchase.amount)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, AirtimePurchase.Status.SENDING)
        self.assertEqual(purchase.payment.mpesa_receipt_number, 'QKL123ABC')

        self.statum_callback({
            'request_id': 'statum-req-1', 'charge': 48.5, 'account_balance': 5000,
            'result_code': 200, 'result_desc': 'You have topped up 254722000111 with Ksh. 50.',
        })
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, AirtimePurchase.Status.DELIVERED)
        self.assertEqual(str(purchase.statum_charge), '48.50')

    def test_duplicate_mpesa_callback_sends_airtime_once(self):
        self.start()
        self.mpesa_callback(stk_callback())
        self.mpesa_callback(stk_callback())
        self.send_airtime.assert_called_once()

    def test_same_session_creates_one_order(self):
        self.start()
        self.start()
        self.assertEqual(AirtimePurchase.objects.count(), 1)
        self.stk_push.assert_called_once()

    def test_cancelled_payment(self):
        purchase = self.start()
        self.mpesa_callback(stk_callback(result_code=1032))
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, AirtimePurchase.Status.PAYMENT_FAILED)
        self.send_airtime.assert_not_called()

    def test_underpayment_is_rejected(self):
        purchase = self.start()
        self.mpesa_callback(stk_callback(amount=1))
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, AirtimePurchase.Status.PAYMENT_FAILED)
        self.send_airtime.assert_not_called()

    def test_stk_push_rejected(self):
        from payments.mpesa import MpesaError

        self.stk_push.side_effect = MpesaError('Invalid PhoneNumber')
        purchase = self.start()
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, AirtimePurchase.Status.PAYMENT_FAILED)

    def test_statum_failure_marks_refund_due(self):
        from airtime.statum import StatumError

        self.send_airtime.side_effect = StatumError('Insufficient balance')
        purchase = self.start()
        self.mpesa_callback(stk_callback())
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, AirtimePurchase.Status.FAILED)

    def test_statum_callback_failure(self):
        purchase = self.start()
        self.mpesa_callback(stk_callback())
        self.statum_callback({'request_id': 'statum-req-1', 'result_code': 500, 'result_desc': 'Failed'})
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, AirtimePurchase.Status.FAILED)
