from django.urls import path
from . import views

urlpatterns = [
    # Geo Block
    path("", views.geo_block_dashboard, name="geo_block_dashboard"),
    path("create/", views.geo_block_create, name="geo_block_create"),
    path("update/<int:pk>/", views.geo_block_update, name="geo_block_update"),
    path("delete/<int:pk>/", views.geo_block_delete, name="geo_block_delete"),
]
