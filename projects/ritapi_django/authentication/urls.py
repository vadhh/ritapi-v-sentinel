from django.urls import path
from . import views

urlpatterns = [
    path("auth/login/", views.custom_login, name="login_compat"),
    path("auth/logout/", views.custom_logout, name="logout_compat"),
    path("login/", views.custom_login, name="login"),
    path("logout/", views.custom_logout, name="logout"),
    path("change-password/", views.change_password, name="change_password"),
]
