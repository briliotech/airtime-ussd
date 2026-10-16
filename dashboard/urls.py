from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('purchases/', views.PurchaseList.as_view(), name='purchases'),
    path('purchases/<int:pk>/retry/', views.retry_purchase, name='retry-purchase'),
    path('payments/', views.PaymentList.as_view(), name='payments'),
    path('sessions/', views.SessionList.as_view(), name='sessions'),
    path('customers/', views.CustomerList.as_view(), name='customers'),
]
