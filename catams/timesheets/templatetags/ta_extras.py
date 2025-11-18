
from django import template
from ..models import TeachingAssistantAssignment

register = template.Library()

@register.simple_tag(takes_context=True)
def is_ta(context):
    user = context['request'].user
    return TeachingAssistantAssignment.objects.filter(user=user).exists()

@register.simple_tag(takes_context=True)
def ta_units(context):
    user = context['request'].user
    return [a.unit for a in TeachingAssistantAssignment.objects.filter(user=user).select_related('unit')]

@register.simple_tag
def ta_hourly_rate(assignment):
    return getattr(assignment, 'hourly_rate', None)
