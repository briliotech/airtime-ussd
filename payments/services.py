import logging

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from . import mpesa
from .models import MpesaPayment
from .signals import payment_completed

logger = logging.getLogger(__name__)


def callback_url():
    path = reverse('payments:mpesa-callback')
    return f'{settings.PUBLIC_BASE_URL}{path}'


def send_stk_push(payment_id):
    """Ask Daraja to prompt the customer. Marks the payment failed if Daraja refuses."""
    payment = MpesaPayment.objects.get(pk=payment_id)
    if payment.status != MpesaPayment.Status.PENDING:
        return
    try:
        data = mpesa.stk_push(
            phone_number=payment.phone_number,
            amount=payment.amount,
            account_reference=payment.account_reference,
            description=payment.description,
            callback_url=callback_url(),
        )
    except mpesa.MpesaError as exc:
        logger.warning('STK push for payment %s failed: %s', payment.pk, exc)
        payment.status = MpesaPayment.Status.FAILED
        payment.result_desc = str(exc)[:255]
        payment.save(update_fields=['status', 'result_desc', 'updated_at'])
        payment_completed.send(sender=MpesaPayment, payment=payment)
        return

    payment.status = MpesaPayment.Status.INITIATED
    payment.merchant_request_id = data.get('MerchantRequestID', '')
    payment.checkout_request_id = data.get('CheckoutRequestID')
    payment.save(update_fields=['status', 'merchant_request_id', 'checkout_request_id', 'updated_at'])


def handle_stk_callback(body):
    """Apply a Daraja STK callback. Returns the payment, or None if it's unknown."""
    stk = (body.get('Body') or {}).get('stkCallback') or {}
    checkout_id = stk.get('CheckoutRequestID')
    if not checkout_id:
        return None

    with transaction.atomic():
        payment = (
            MpesaPayment.objects.select_for_update()
            .filter(checkout_request_id=checkout_id)
            .first()
        )
        if payment is None:
            logger.warning('STK callback for unknown CheckoutRequestID %s', checkout_id)
            return None
        if payment.status in (MpesaPayment.Status.SUCCESS, MpesaPayment.Status.FAILED):
            return payment  # duplicate callback, already handled

        result_code = int(stk.get('ResultCode', -1))
        meta = mpesa.parse_callback_metadata(stk)
        payment.result_code = result_code
        payment.result_desc = str(stk.get('ResultDesc', ''))[:255]
        payment.raw_callback = body

        paid_amount = meta.get('Amount')
        if result_code == 0 and paid_amount is not None and int(float(paid_amount)) < int(payment.amount):
            logger.error('Payment %s underpaid: got %s, expected %s', payment.pk, paid_amount, payment.amount)
            payment.status = MpesaPayment.Status.FAILED
            payment.result_desc = f'Amount mismatch: paid {paid_amount}'
        elif result_code == 0:
            payment.status = MpesaPayment.Status.SUCCESS
            payment.mpesa_receipt_number = str(meta.get('MpesaReceiptNumber', ''))
        else:
            payment.status = MpesaPayment.Status.FAILED
        payment.save()

    payment_completed.send(sender=MpesaPayment, payment=payment)
    return payment
