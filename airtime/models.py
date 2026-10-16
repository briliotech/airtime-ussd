from django.db import models

from accounts.models import Customer
from payments.models import MpesaPayment


class AirtimePurchase(models.Model):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = 'awaiting_payment', 'Awaiting payment'
        PAYMENT_FAILED = 'payment_failed', 'Payment failed'
        PAID = 'paid', 'Paid'                    # M-Pesa confirmed, airtime not sent yet
        SENDING = 'sending', 'Sending'           # Statum accepted, waiting for callback
        DELIVERED = 'delivered', 'Delivered'
        FAILED = 'failed', 'Failed (refund due)'  # paid but airtime could not be sent

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='airtime_purchases')
    payment = models.OneToOneField(MpesaPayment, on_delete=models.PROTECT, related_name='airtime_purchase')
    ussd_session_id = models.CharField(max_length=100, unique=True)
    recipient_phone = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT)

    statum_request_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    statum_charge = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)
    raw_callback = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'KES {self.amount} to {self.recipient_phone} ({self.status})'
