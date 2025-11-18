from django import template

register = template.Library()

@register.filter
def has_group(user, group_name):
    try:
        return user.is_authenticated and user.groups.filter(name__iexact=group_name).exists()
    except Exception:
        return False

@register.simple_tag
def in_any_group(user, *names):
    try:
        if not user.is_authenticated:
            return False
        for n in names:
            if user.groups.filter(name__iexact=n).exists():
                return True
        return False
    except Exception:
        return False
