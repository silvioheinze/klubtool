from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user'
    
    def ready(self):
        from django.contrib import admin
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import User
        from django.contrib.auth.admin import UserAdmin
        from allauth.account.models import EmailAddress
        from .forms import CustomUserCreationForm, CustomUserChangeForm
        
        CustomUser = get_user_model()
        
        class CustomUserAdmin(UserAdmin):
            add_form = CustomUserCreationForm
            form = CustomUserChangeForm
            model = CustomUser
            list_display = [
                "email",
                "username",
                "is_superuser",
            ]
        
        # Unregister the default User model if it's registered
        try:
            admin.site.unregister(User)
        except admin.sites.NotRegistered:
            pass
        
        # Register our custom user model
        try:
            admin.site.register(CustomUser, CustomUserAdmin)
        except admin.sites.AlreadyRegistered:
            pass
        
        # Unregister the EmailAddress model from admin
        try:
            admin.site.unregister(EmailAddress)
        except admin.sites.NotRegistered:
            pass
