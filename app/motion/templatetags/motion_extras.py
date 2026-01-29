from django import template

register = template.Library()


@register.filter
def can_delete_motion(motion, user):
    """Check if a user can delete a motion"""
    return motion.can_be_deleted_by(user)


@register.filter
def sum_attr(queryset, attr):
    """Return the sum of attribute values over a queryset (e.g. votes, 'approve_votes')."""
    if not queryset:
        return 0
    return sum(getattr(obj, attr, 0) or 0 for obj in queryset)
