from django.contrib import admin
from django.db import DatabaseError
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView

from accounts.models import Customer

admin.site.site_header = 'QuickTop Admin'
admin.site.site_title = 'QuickTop Admin'
admin.site.index_title = 'Manage QuickTop'


def health(request):
    # Touch a migrated table so a missing database or unapplied migrations fail the deploy.
    try:
        Customer.objects.exists()
    except DatabaseError as exc:
        return JsonResponse({'status': 'error', 'detail': str(exc).splitlines()[0]}, status=503)
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard:overview')),
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls')),
    path('health/', health, name='health'),
    path('ussd/', include('ussd.urls')),
    path('payments/', include('payments.urls')),
    path('airtime/', include('airtime.urls')),
]
