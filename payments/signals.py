from django.dispatch import Signal

# Sent once an MpesaPayment reaches a final state (success or failed).
# Receivers get `payment`. Product apps (airtime, data, utilities) listen to it.
payment_completed = Signal()
