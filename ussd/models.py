from django.db import models


class UssdSession(models.Model):
    """Last known state of a Brilio USSD session, kept for support and debugging."""

    session_id = models.CharField(max_length=100, unique=True)
    msisdn = models.CharField(max_length=15)
    network = models.CharField(max_length=50, blank=True)
    service_code = models.CharField(max_length=30, blank=True)
    text = models.TextField(blank=True)
    last_response = models.TextField(blank=True)
    ended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.msisdn} {self.session_id}'
