import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from accounts.models import Customer
from payments.models import MpesaPayment
from payments.services import send_stk_push
from quicktop.background import run_in_background

from . import statum
from .models import AirtimePurchase

logger = logging.getLogger(__name__)


def start_airtime_purchase(session_id, payer_phone, recipient_phone, amount):
    """Record the order and send the STK push after the USSD session has closed.

    Safe to call twice for the same USSD session: the second call is a no-op.
    """
    customer, _ = Customer.objects.get_or_create(phone_number=payer_phone)
    with transaction.atomic():
        existing = AirtimePurchase.objects.filter(ussd_session_id=session_id).first()
        if existing:
            return existing
        payment = MpesaPayment.objects.create(
            phone_number=payer_phone,
            amount=Decimal(amount),
            account_reference='QuickTop',
            description='Airtime',
        )
        purchase = AirtimePurchase.objects.create(
            customer=customer,
            payment=payment,
            ussd_session_id=session_id,
            recipient_phone=recipient_phone,
            amount=Decimal(amount),
        )
    # A phone can't show the M-Pesa prompt while the USSD screen is still open,
    # so give the network a moment to close the session first.
    transaction.on_commit(
        lambda: run_in_background(send_stk_push, payment.pk, delay=settings.STK_PUSH_DELAY_SECONDS)
    )
    return purchase


def on_payment_completed(sender, payment, **kwargs):
    """payments.signals.payment_completed receiver."""
    purchase = AirtimePurchase.objects.filter(payment=payment).first()
    if purchase is None or purchase.status != AirtimePurchase.Status.AWAITING_PAYMENT:
        return
    if payment.status == MpesaPayment.Status.SUCCESS:
        purchase.status = AirtimePurchase.Status.PAID
        purchase.save(update_fields=['status', 'updated_at'])
        run_in_background(disburse_airtime, purchase.pk)
    else:
        purchase.status = AirtimePurchase.Status.PAYMENT_FAILED
        purchase.result_desc = payment.result_desc
        purchase.save(update_fields=['status', 'result_desc', 'updated_at'])


def retry_airtime(purchase_id):
    """Resend airtime for a paid purchase that failed (e.g. Statum balance was empty).

    Returns False if the purchase isn't a failed purchase with a successful payment.
    """
    retried = AirtimePurchase.objects.filter(
        pk=purchase_id,
        status=AirtimePurchase.Status.FAILED,
        payment__status=MpesaPayment.Status.SUCCESS,
    ).update(status=AirtimePurchase.Status.PAID, statum_request_id=None, result_desc='')
    if retried:
        run_in_background(disburse_airtime, purchase_id)
    return bool(retried)


def disburse_airtime(purchase_id):
    # Claim the purchase so that a duplicate trigger can't send airtime twice.
    claimed = AirtimePurchase.objects.filter(
        pk=purchase_id, status=AirtimePurchase.Status.PAID
    ).update(status=AirtimePurchase.Status.SENDING)
    if not claimed:
        return
    purchase = AirtimePurchase.objects.get(pk=purchase_id)
    try:
        request_id = statum.send_airtime(purchase.recipient_phone, purchase.amount)
    except statum.StatumError as exc:
        logger.error('Airtime for purchase %s failed after payment: %s', purchase.pk, exc)
        purchase.status = AirtimePurchase.Status.FAILED
        purchase.result_desc = str(exc)[:255]
        purchase.save(update_fields=['status', 'result_desc', 'updated_at'])
        return
    purchase.statum_request_id = request_id
    purchase.save(update_fields=['statum_request_id', 'updated_at'])


def handle_statum_callback(payload):
    request_id = payload.get('request_id')
    if not request_id:
        return None
    with transaction.atomic():
        purchase = (
            AirtimePurchase.objects.select_for_update()
            .filter(statum_request_id=request_id)
            .first()
        )
        if purchase is None:
            logger.warning('Statum callback for unknown request_id %s', request_id)
            return None
        if purchase.status != AirtimePurchase.Status.SENDING:
            return purchase  # duplicate callback

        purchase.raw_callback = payload
        purchase.result_desc = str(payload.get('result_desc', ''))[:255]
        if int(payload.get('result_code', 0)) == 200:
            purchase.status = AirtimePurchase.Status.DELIVERED
            if payload.get('charge') is not None:
                purchase.statum_charge = Decimal(str(payload['charge']))
        else:
            purchase.status = AirtimePurchase.Status.FAILED
            logger.error('Statum failed purchase %s: %s', purchase.pk, purchase.result_desc)
        purchase.save()
    return purchase
