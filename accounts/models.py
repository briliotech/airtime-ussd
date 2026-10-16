from django.db import models


class Customer(models.Model):
    """A subscriber who has dialled the QuickTop USSD code."""

    phone_number = models.CharField(max_length=15, unique=True)
    network = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.phone_number
