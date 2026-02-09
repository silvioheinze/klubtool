from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class UserLanguageMiddleware(MiddlewareMixin):
    """
    Middleware to set the language based on the user's language preference.
    This runs after authentication middleware to ensure user is available.
    """
    
    def process_request(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Get the user's preferred language
            user_language = getattr(request.user, 'language', None)
            if user_language:
                # Set the language in the session
                request.session['django_language'] = user_language
                # Activate the language for this request
                translation.activate(user_language)
                # Set LANGUAGE_CODE on request for other middleware/templates
                request.LANGUAGE_CODE = user_language
        
        return None
