import datetime
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView
from django.views.generic.list import ListView
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .forms import CustomUserCreationForm, CustomUserEditForm
from .models import CustomUser


class AccountDeleteView(LoginRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'user/confirm_delete.html'
    success_url = reverse_lazy('home')

    def get_object(self, queryset=None):
        # Ensure that only the logged-in user can delete their user
        return self.request.user

    def delete(self, request, *args, **kwargs):
        # Optionally, add a message for the user or perform extra cleanup
        messages.success(request, "Your user has been deleted successfully.")
        return super().delete(request, *args, **kwargs)


def DashboardView(request):
    """
    Display a dashboard overview for the logged-in user.
    If the user is not authenticated, display the login form.
    """
    if request.user.is_authenticated:
        context = {
            'user': request.user,
        }
        return render(request, "user/dashboard.html", context)
    else:
        # Process the login form for unauthenticated users
        form = AuthenticationForm(request=request, data=request.POST or None)
        if request.method == "POST":
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                return redirect("home")  # Redirect to home page
        return render(request, "user/login.html", {"form": form})


class SignupPageView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("home")
    template_name = "user/signup.html"

    def form_valid(self, form):
        user = form.instance

        return super().form_valid(form)


def SettingsView(request):
    """
    Display a dashboard overview for the logged-in user.
    If the user is not authenticated, display the login form.
    """
    if request.user.is_authenticated:
        # Here, you can add additional context for the dashboard as needed
        context = {
            'user': request.user,
            # add other variables for your dashboard here
        }
        return render(request, "user/settings.html", context)
    else:
        # Process the login form for unauthenticated users
        form = AuthenticationForm(request=request, data=request.POST or None)
        if request.method == "POST":
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                return redirect("home")
        return render(request, "user/login.html", {"form": form})
    

class UsersUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = get_user_model()
    form_class = CustomUserEditForm
    template_name = 'user/edit.html'
    pk_url_kwarg = 'user_id'  # Erwartet in der URL: /users/edit/<user_id>/

    def get_success_url(self):
        return reverse_lazy('user-list')

    def test_func(self):
        # Zugriff erlauben, wenn der angemeldete Benutzer ein Superuser ist
        return self.request.user.is_superuser


class UsersListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = CustomUser
    context_object_name = 'users'
    template_name = 'user/list.html'

    def test_func(self):
        # Only superusers can access this view
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def get_queryset(self):
        # Optimize queryset by selecting related 'current_organization'
        return CustomUser.objects.all().order_by('id')
