from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health, name='health'),
    path('ussd/', include('ussd.urls')),
    path('payments/', include('payments.urls')),
    path('airtime/', include('airtime.urls')),
]
