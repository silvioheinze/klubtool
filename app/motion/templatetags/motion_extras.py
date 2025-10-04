from django import template

register = template.Library()

@register.filter
def can_delete_motion(motion, user):
    """Check if a user can delete a motion"""
    return motion.can_be_deleted_by(user)
