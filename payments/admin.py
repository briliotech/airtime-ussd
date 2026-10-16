from django.contrib import admin

from .models import MpesaPayment


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'amount', 'status', 'mpesa_receipt_number', 'result_desc', 'created_at')
    list_filter = ('status',)
    search_fields = ('phone_number', 'mpesa_receipt_number', 'checkout_request_id')
    readonly_fields = ('raw_callback', 'created_at', 'updated_at')
