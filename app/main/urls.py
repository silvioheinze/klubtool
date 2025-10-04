"""
URL configuration for main project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

def redirect_to_user_login(request):
    """Redirect /accounts/login/ to /user/settings/"""
    return redirect('/user/settings/')

def redirect_to_user_signup(request):
    """Redirect /accounts/signup/ to /user/signup/"""
    return redirect('/user/signup/')

def redirect_to_user_logout(request):
    """Redirect /accounts/logout/ to /user/settings/"""
    return redirect('/user/settings/')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('pages.urls')),
    path('user/', include('user.urls')),
    path('accounts/login/', redirect_to_user_login, name='account_login_redirect'),
    path('accounts/signup/', redirect_to_user_signup, name='account_signup_redirect'),
    path('accounts/logout/', redirect_to_user_logout, name='account_logout_redirect'),
    path('local/', include('local.urls')),
    path('group/', include('group.urls')),
    path('motion/', include('motion.urls')), # Added
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
