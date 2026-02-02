"""
URLs untuk MiniFW-AI Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    # Main Pages
    path('dashboard/', views.minifw_dashboard, name='minifw_dashboard'),
    path('policy/', views.minifw_policy, name='minifw_policy'),
    path('feeds/', views.minifw_feeds, name='minifw_feeds'),
    path('blocked-ips/', views.minifw_blocked_ips, name='minifw_blocked_ips'),
    
    # Service Control
    path('service/control/', views.minifw_service_control, name='minifw_service_control'),
    
    # API Endpoints
    path('api/stats/', views.minifw_api_stats, name='minifw_api_stats'),
    path('api/service-status/', views.minifw_api_service_status, name='minifw_api_service_status'),
    path('api/events/', views.minifw_api_recent_events, name='minifw_api_recent_events'),
]
