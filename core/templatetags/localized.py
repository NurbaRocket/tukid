from django import template

from core.localization import localized

register = template.Library()


@register.filter(name='loc')
def localize_field(value, field):
    return localized(value, field)
