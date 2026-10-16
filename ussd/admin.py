from django.contrib import admin

from .models import UssdSession


@admin.register(UssdSession)
class UssdSessionAdmin(admin.ModelAdmin):
    list_display = ('msisdn', 'network', 'text', 'ended', 'created_at')
    list_filter = ('network', 'ended')
    search_fields = ('msisdn', 'session_id')
