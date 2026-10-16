from django.apps import AppConfig


class AirtimeConfig(AppConfig):
    name = 'airtime'

    def ready(self):
        from payments.signals import payment_completed

        from .services import on_payment_completed

        payment_completed.connect(on_payment_completed, dispatch_uid='airtime.on_payment_completed')
