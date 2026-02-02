# alerts/urls.py
from django.urls import path
from .views import CreateAlertView, ListAlertsView

urlpatterns = [
    path('create/', CreateAlertView.as_view(), name='create-alert'),
    path('list/', ListAlertsView.as_view(), name='list-alerts'),
]
