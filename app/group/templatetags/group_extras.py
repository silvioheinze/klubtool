from django import template
from django.utils.safestring import mark_safe
import bleach

register = template.Library()

# Allowed tags and attributes for minute item (and similar) rich text display
ALLOWED_TAGS = ['p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li', 'a', 'span', 'div']
ALLOWED_ATTRS = {'a': ['href', 'title'], 'span': ['class'], 'div': ['class']}


@register.filter
def sanitize_richtext(value):
    """Sanitize HTML from rich text fields for safe display."""
    if not value:
        return ''
    cleaned = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    return mark_safe(cleaned)


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key."""
    if dictionary is None:
        return None
    return dictionary.get(key)
