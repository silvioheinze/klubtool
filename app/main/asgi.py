"""
ASGI config for main project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

from main.upload_asgi_middleware import UploadSizeLimitMiddleware

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

application = UploadSizeLimitMiddleware(get_asgi_application())
