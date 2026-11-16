"""Small presentation helpers: the SVG chart geometry and status colours.

Charts are drawn server-side. That means no JavaScript charting library, no CDN,
and the numbers on screen are always the numbers in the database.
"""
from django import template

register = template.Library()


def _points(values, width, height, pad):
    if not values:
        return []
    # 12% headroom: a single spike should not touch the top of the card.
    peak = (max(values) or 1) * 1.12
    span = max(len(values) - 1, 1)
    step = (width - pad * 2) / span
    usable = height - pad * 2
    return [
        (pad + index * step, height - pad - (value / peak) * usable)
        for index, value in enumerate(values)
    ]


@register.simple_tag
def chart_line(values, width=760, height=190, pad=10):
    """`d` attribute for the line of an area chart."""
    pts = _points(values, width, height, pad)
    if not pts:
        return ""
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)


@register.simple_tag
def chart_area(values, width=760, height=190, pad=10):
    """`d` attribute for the filled area under that line."""
    pts = _points(values, width, height, pad)
    if not pts:
        return ""
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return f"{line} L{width - pad:.1f},{height - pad} L{pad},{height - pad} Z"


@register.filter
def status_class(value):
    """Map a status string to one of our pill classes."""
    mapping = {
        "PRINTED": "pill-success",
        "APPROVED": "pill-success",
        "SUCCESSFUL": "pill-success",
        "ACTIVE": "pill-success",
        "QUEUED": "pill-warning",
        "AWAITING_APPROVAL": "pill-warning",
        "PRINTING": "pill-info",
        "AWAITING_PAYMENT": "pill-info",
        "DRAFT": "pill-neutral",
        "CANCELLED": "pill-neutral",
        "EXPIRED": "pill-neutral",
        "REJECTED": "pill-danger",
        "FAILED": "pill-danger",
        "ADMIN": "pill-info",
        "MEMBER": "pill-neutral",
    }
    return mapping.get(str(value), "pill-neutral")


@register.filter
def delta_class(value):
    """Green for a rise, red for a fall, grey when there is nothing to compare."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "pill-neutral"
    if number > 0:
        return "pill-success"
    if number < 0:
        return "pill-danger"
    return "pill-neutral"


@register.filter
def rands(cents):
    """5000 -> 'E50.00'"""
    from apps.core.utils import cents_to_rand
    try:
        return cents_to_rand(int(cents or 0))
    except (TypeError, ValueError):
        return "E0.00"


@register.filter
def credit_rand(credits):
    """500 -> 'E50.00' (credits shown as their rand value)"""
    from apps.core.utils import credits_to_rand
    try:
        return credits_to_rand(int(credits or 0))
    except (TypeError, ValueError):
        return "E0.00"


@register.filter
def thousands(value):
    try:
        return f"{int(value or 0):,}"
    except (TypeError, ValueError):
        return value