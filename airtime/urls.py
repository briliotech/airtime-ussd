from django.urls import path

from . import views

app_name = 'airtime'

urlpatterns = [
    path('statum/callback/', views.statum_callback, name='statum-callback'),
]
