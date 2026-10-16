from django.urls import path

from . import views

app_name = 'ussd'

urlpatterns = [
    path('callback/', views.brilio_callback, name='callback'),
]
