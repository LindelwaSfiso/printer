"""Aggregates for the dashboards. Read-only; nothing here mutates."""
from datetime import timedelta

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import PrintJob


def _sample_labels(start, days, count=6):
    """Evenly spaced date labels for the x axis, always including both ends."""
    if days <= count:
        indices = range(days)
    else:
        step = (days - 1) / (count - 1)
        indices = sorted({round(i * step) for i in range(count)})
    return [{"date": (start + timedelta(days=index)).strftime("%d %b"),
             "index": index} for index in indices]


def daily_pages(*, days=30, member=None):
    """Pages actually printed per calendar day, zero-filled.

    Zero-filled on purpose: a gap in the chart must mean "nothing printed that
    day", never a missing data point that silently shifts the x axis.
    """
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)

    jobs = PrintJob.objects.filter(
        status=PrintJob.Status.PRINTED,
        printed_at__date__gte=start,
        printed_at__date__lte=today,
    )
    if member is not None:
        jobs = jobs.filter(member=member)

    rows = (jobs.annotate(day=TruncDate("printed_at"))
                .values("day")
                .annotate(pages=Sum("page_count"))
                .order_by("day"))
    by_day = {row["day"]: row["pages"] for row in rows}

    values = [by_day.get(start + timedelta(days=i), 0) for i in range(days)]
    return {
        "values": values,
        "labels": _sample_labels(start, days),
        "total": sum(values),
        "peak": max(values) if values else 0,
        "days": days,
        "start": start,
        "end": today,
    }


def pages_in_window(*, days, member=None, offset=0):
    """Pages printed in a window that ends `offset` days ago (for deltas)."""
    today = timezone.localdate()
    end = today - timedelta(days=offset)
    start = end - timedelta(days=days - 1)
    jobs = PrintJob.objects.filter(
        status=PrintJob.Status.PRINTED,
        printed_at__date__gte=start,
        printed_at__date__lte=end,
    )
    if member is not None:
        jobs = jobs.filter(member=member)
    return jobs.aggregate(s=Sum("page_count"))["s"] or 0


def percent_change(current, previous):
    """None when there is no baseline -- better than a fake '+100%'."""
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)