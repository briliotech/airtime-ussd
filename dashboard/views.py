from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from accounts.models import Customer
from accounts.phone import normalize_msisdn
from airtime.models import AirtimePurchase
from airtime.services import retry_airtime
from payments.models import MpesaPayment
from ussd.models import UssdSession

CHART_DAYS = 14


def _total(queryset, field='amount'):
    return queryset.aggregate(total=Sum(field))['total'] or Decimal('0')


@staff_member_required
def overview(request):
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=6)

    paid = MpesaPayment.objects.filter(status=MpesaPayment.Status.SUCCESS)
    finished_payments = MpesaPayment.objects.filter(
        status__in=[MpesaPayment.Status.SUCCESS, MpesaPayment.Status.FAILED]
    )
    delivered = AirtimePurchase.objects.filter(status=AirtimePurchase.Status.DELIVERED)
    refunds_due = AirtimePurchase.objects.filter(status=AirtimePurchase.Status.FAILED)

    finished_count = finished_payments.count()
    success_rate = round(100 * paid.count() / finished_count) if finished_count else None

    # Daily M-Pesa collections for the chart.
    start = today - timedelta(days=CHART_DAYS - 1)
    by_day = {
        row['day']: row['total']
        for row in paid.filter(created_at__gte=start)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('amount'))
    }
    days = [(start + timedelta(days=i)).date() for i in range(CHART_DAYS)]
    chart_max = max(by_day.values(), default=0) or 1
    chart = [
        {'day': day, 'total': by_day.get(day, 0), 'pct': int(100 * (by_day.get(day, 0) / chart_max))}
        for day in days
    ]

    context = {
        'stats': {
            'collected_today': _total(paid.filter(created_at__gte=today)),
            'collected_week': _total(paid.filter(created_at__gte=week_ago)),
            'collected_all': _total(paid),
            'delivered_count': delivered.count(),
            'delivered_value': _total(delivered),
            'success_rate': success_rate,
            'refunds_due_count': refunds_due.count(),
            'refunds_due_value': _total(refunds_due),
            'sessions_today': UssdSession.objects.filter(created_at__gte=today).count(),
            'customers': Customer.objects.count(),
            'statum_charges': _total(delivered, 'statum_charge'),
        },
        'status_counts': [
            {**row, 'label': AirtimePurchase.Status(row['status']).label}
            for row in AirtimePurchase.objects.values('status').annotate(n=Count('id')).order_by('-n')
        ],
        'chart': chart,
        'recent_purchases': AirtimePurchase.objects.select_related('customer', 'payment')[:8],
        'recent_sessions': UssdSession.objects.all()[:8],
        'active': 'overview',
    }
    return render(request, 'dashboard/overview.html', context)


@method_decorator(staff_member_required, name='dispatch')
class FilteredListView(ListView):
    """List with ?q= search, ?status= filter and pagination."""

    paginate_by = 25
    search_fields = ()
    status_choices = None
    active = ''

    def get_queryset(self):
        queryset = super().get_queryset()
        self.q = self.request.GET.get('q', '').strip()
        self.status = self.request.GET.get('status', '')
        if self.q and self.search_fields:
            # Phones are stored as 2547...; let staff search the way they type them (07...).
            term = normalize_msisdn(self.q) or self.q
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f'{field}__icontains': term})
            queryset = queryset.filter(condition)
        if self.status and self.status_choices:
            queryset = queryset.filter(status=self.status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update(
            q=self.q,
            status=self.status,
            status_choices=self.status_choices,
            querystring=params.urlencode(),
            active=self.active,
        )
        return context


class PurchaseList(FilteredListView):
    queryset = AirtimePurchase.objects.select_related('customer', 'payment')
    template_name = 'dashboard/purchases.html'
    search_fields = ('recipient_phone', 'customer__phone_number', 'payment__mpesa_receipt_number', 'statum_request_id')
    status_choices = AirtimePurchase.Status.choices
    active = 'purchases'


class PaymentList(FilteredListView):
    queryset = MpesaPayment.objects.select_related('airtime_purchase')
    template_name = 'dashboard/payments.html'
    search_fields = ('phone_number', 'mpesa_receipt_number', 'checkout_request_id')
    status_choices = MpesaPayment.Status.choices
    active = 'payments'


class SessionList(FilteredListView):
    queryset = UssdSession.objects.all()
    template_name = 'dashboard/sessions.html'
    search_fields = ('msisdn', 'session_id', 'text')
    active = 'sessions'


class CustomerList(FilteredListView):
    queryset = Customer.objects.annotate(
        purchase_count=Count('airtime_purchases'),
        delivered_value=Sum('airtime_purchases__amount', filter=Q(airtime_purchases__status=AirtimePurchase.Status.DELIVERED)),
        last_purchase=Max('airtime_purchases__created_at'),
    ).order_by('-last_seen_at')
    template_name = 'dashboard/customers.html'
    search_fields = ('phone_number',)
    active = 'customers'


@staff_member_required
@require_POST
def retry_purchase(request, pk):
    purchase = get_object_or_404(AirtimePurchase, pk=pk)
    if retry_airtime(purchase.pk):
        messages.success(request, f'Resending KES {purchase.amount:,.0f} airtime to {purchase.recipient_phone}.')
    else:
        messages.error(request, 'Only failed purchases with a successful M-Pesa payment can be retried.')
    return redirect(request.POST.get('next') or 'dashboard:purchases')
