import re
from html import unescape

import nh3
from django import template
from django.utils.html import linebreaks, strip_tags
from django.utils.safestring import mark_safe

register = template.Library()
FORMATTED = re.compile(r'</?(?:p|div|br|h[2-4]|strong|em|b|i|u|ul|ol|li|a|blockquote|pre|code)\b', re.I)
TAGS = {'p', 'div', 'br', 'h2', 'h3', 'h4', 'strong', 'em', 'b', 'i', 'u', 'ul', 'ol', 'li', 'a', 'blockquote', 'pre', 'code'}


@register.filter
def richtext(value):
    value = str(value or '')
    if not FORMATTED.search(value):
        return mark_safe(linebreaks(value, autoescape=True))
    return mark_safe(nh3.clean(
        value, tags=TAGS, attributes={'a': {'href', 'title'}},
        url_schemes={'http', 'https', 'mailto', 'tel'},
        clean_content_tags={'script', 'style', 'iframe', 'object'},
        link_rel='noopener noreferrer',
    ))


@register.filter
def plain_text(value):
    return unescape(strip_tags(str(value or '')))
