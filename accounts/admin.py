from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'network', 'created_at', 'last_seen_at')
    search_fields = ('phone_number',)
    list_filter = ('network',)
