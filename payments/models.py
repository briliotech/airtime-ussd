from django.db import models


class MpesaPayment(models.Model):
    """One M-Pesa STK push (Lipa na M-Pesa Online) request and its outcome."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'          # created, STK push not sent yet
        INITIATED = 'initiated', 'Initiated'    # Daraja accepted the STK push
        SUCCESS = 'success', 'Success'          # customer paid
        FAILED = 'failed', 'Failed'             # cancelled, timed out, insufficient funds...

    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    account_reference = models.CharField(max_length=12)
    description = models.CharField(max_length=13)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    merchant_request_id = models.CharField(max_length=64, blank=True)
    checkout_request_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    mpesa_receipt_number = models.CharField(max_length=32, blank=True)
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)
    raw_callback = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone_number} KES {self.amount} ({self.status})'
