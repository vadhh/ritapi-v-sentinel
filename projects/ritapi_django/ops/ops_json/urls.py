# ops/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.jsonschema_dashboard, name="ops.jsonschema_dashboard"),
    path("create/", views.jsonschema_create, name="jsonschema_create"),
    path("update/<int:pk>/", views.jsonschema_update, name="jsonschema_update"),
    path("delete/<int:pk>/", views.jsonschema_delete, name="jsonschema_delete"),
    path("toggle/<int:pk>/", views.jsonschema_toggle, name="jsonschema_toggle"),
]
