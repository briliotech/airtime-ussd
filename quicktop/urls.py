from django.contrib import admin
from django.db import DatabaseError
from django.http import JsonResponse
from django.urls import include, path

from accounts.models import Customer


def health(request):
    # Touch a migrated table so a missing database or unapplied migrations fail the deploy.
    try:
        Customer.objects.exists()
    except DatabaseError as exc:
        return JsonResponse({'status': 'error', 'detail': str(exc).splitlines()[0]}, status=503)
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health, name='health'),
    path('ussd/', include('ussd.urls')),
    path('payments/', include('payments.urls')),
    path('airtime/', include('airtime.urls')),
]
