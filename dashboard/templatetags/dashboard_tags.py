from django import template

from accounts.phone import display_msisdn

register = template.Library()

STATUS_TONES = {
    'delivered': 'good', 'success': 'good',
    'sending': 'info', 'paid': 'info', 'initiated': 'info',
    'awaiting_payment': 'muted', 'pending': 'muted',
    'payment_failed': 'warn',
    'failed': 'bad',
}


@register.filter
def phone(value):
    return display_msisdn(value)


@register.filter
def tone(status):
    return STATUS_TONES.get(status, 'muted')


@register.filter
def kes(value):
    if value is None:
        return '—'
    return f'KES {value:,.0f}'
