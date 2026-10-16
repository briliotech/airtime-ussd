from django.contrib import admin, messages

from .models import AirtimePurchase
from .services import retry_airtime


@admin.register(AirtimePurchase)
class AirtimePurchaseAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'amount', 'status', 'customer', 'statum_charge', 'created_at')
    list_filter = ('status',)
    search_fields = ('recipient_phone', 'customer__phone_number', 'statum_request_id', 'ussd_session_id')
    readonly_fields = ('raw_callback', 'created_at', 'updated_at')
    list_select_related = ('customer',)
    actions = ['retry_selected']

    @admin.action(description='Retry airtime for selected failed purchases')
    def retry_selected(self, request, queryset):
        retried = sum(retry_airtime(pk) for pk in queryset.values_list('pk', flat=True))
        skipped = queryset.count() - retried
        self.message_user(request, f'Retrying {retried} purchase(s).', messages.SUCCESS)
        if skipped:
            self.message_user(request, f'Skipped {skipped}: only failed, paid purchases can be retried.', messages.WARNING)
