from django.contrib import admin

from .models import AirtimePurchase


@admin.register(AirtimePurchase)
class AirtimePurchaseAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'amount', 'status', 'customer', 'statum_charge', 'created_at')
    list_filter = ('status',)
    search_fields = ('recipient_phone', 'customer__phone_number', 'statum_request_id', 'ussd_session_id')
    readonly_fields = ('raw_callback', 'created_at', 'updated_at')
    list_select_related = ('customer',)
