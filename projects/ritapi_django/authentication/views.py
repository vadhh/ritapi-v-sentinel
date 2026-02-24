from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CustomLoginForm
from django.contrib.auth.forms import PasswordChangeForm
from .forms import CustomPasswordChangeForm


def custom_login(request):
    """
    Custom login view that only allows superusers
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("ops_dashboard")
        else:
            logout(request)
            messages.error(request, "You must be a superuser to access this system.")

    if request.method == "POST":
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")

            # Get next parameter or default to dashboard
            next_url = request.GET.get("next", "ops_dashboard")
            return redirect(next_url)
    else:
        form = CustomLoginForm()

    return render(request, "authentication/login.html", {"form": form})


def custom_logout(request):
    """
    Custom logout view
    """
    username = request.user.username if request.user.is_authenticated else None
    logout(request)
    if username:
        messages.info(request, f"Goodbye, {username}!")
    return redirect("login")


@login_required
def change_password(request):
    """
    Change password view - only for authenticated users
    """
    if request.method == "POST":
        form = CustomPasswordChangeForm(request.user, request.POST)  # Changed here
        if form.is_valid():
            user = form.save()
            # Important: Update the session so user doesn't get logged out
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was successfully updated!")
            return redirect("ops_dashboard")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomPasswordChangeForm(request.user)  # Changed here

    return render(request, "authentication/change_password.html", {"form": form})
