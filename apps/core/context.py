"""Template context shared by every page."""


def nav_counts(request):
    """Badge counts for staff. Two cheap indexed COUNTs per staff page."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_staff:
        return {}
    from apps.billing.models import Invoice
    from apps.printing.models import PrintJob

    return {
        "staff_pending_invoices": Invoice.objects.filter(
            status=Invoice.Status.AWAITING_APPROVAL).count(),
        "staff_queue_depth": PrintJob.objects.filter(
            status=PrintJob.Status.QUEUED).count(),
    }