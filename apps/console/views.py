"""The administrator dashboard.

This replaces Django admin deliberately: the society needs four screens it can
explain to a treasurer in a minute -- members, plans, money waiting for
approval, and the queue -- not a generic model admin.
"""
import csv
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.accounts.models import User
from apps.accounts.mixins import StaffRequiredMixin
from apps.accounts.services import create_account, invite_url, send_invite
from apps.billing import services as billing
from apps.billing.forms import ManualCreditForm, RejectForm
from apps.billing.models import Invoice
from apps.credits.models import CreditAccount, CreditEntry
from apps.credits.services import adjust, ensure_account
from apps.printing import services as printing
from apps.printing.backends import get_backend
from apps.printing.models import PrintJob, Tariff
from apps.subscriptions.models import Plan, Subscription
from apps.subscriptions.services import subscribe

from .forms import MemberForm, PlanForm, SubscribeForm

log = logging.getLogger(__name__)


class ConsoleView(StaffRequiredMixin, View):
    """Shared context: the sidebar counters and the active tab."""

    tab = "dashboard"

    def context(self, **extra):
        base = {
            "active_tab": self.tab,
            "society_name": settings.SOCIETY_NAME,
        }
        base.update(extra)
        return base

    def chart_context(self, request, *, member=None):
        """Chart series and period-over-period deltas for the dashboard cards."""
        from apps.printing.stats import (daily_pages, pages_in_window,
                                         percent_change)

        ranges = (7, 30, 90)
        try:
            days = int(request.GET.get("range", 30))
        except (TypeError, ValueError):
            days = 30
        if days not in ranges:
            days = 30

        pages_now = pages_in_window(days=days, member=member)
        pages_prev = pages_in_window(days=days, offset=days, member=member)
        extra = {
            "chart": daily_pages(days=days, member=member),
            "range_days": days,
            "range_options": ranges,
            "pages_now": pages_now,
            "pages_delta": percent_change(pages_now, pages_prev),
        }

        if member is None:
            now = timezone.now()

            def revenue_between(offset):
                end = now - timedelta(days=offset)
                start = end - timedelta(days=days)
                return Invoice.objects.filter(
                    status=Invoice.Status.APPROVED,
                    decided_at__gte=start, decided_at__lt=end,
                ).aggregate(s=Sum("amount_cents"))["s"] or 0

            def members_between(offset):
                end = now - timedelta(days=offset)
                start = end - timedelta(days=days)
                return User.objects.filter(
                    role=User.Role.MEMBER,
                    created_at__gte=start, created_at__lt=end).count()

            extra["revenue_delta"] = percent_change(revenue_between(0),
                                                    revenue_between(days))
            extra["members_delta"] = percent_change(members_between(0),
                                                    members_between(days))
        return extra


class DashboardView(ConsoleView):
    template_name = "console/dashboard.html"
    tab = "dashboard"

    def get(self, request):
        now = timezone.now()
        since = now - timedelta(days=30)
        jobs = PrintJob.objects.all()

        credits_out = CreditAccount.objects.aggregate(
            s=Sum("balance_credits"))["s"] or 0
        credits_held = CreditAccount.objects.aggregate(
            s=Sum("held_credits"))["s"] or 0
        consumed = CreditEntry.objects.filter(
            kind=CreditEntry.Kind.CAPTURE, created_at__gte=since
        ).aggregate(s=Sum("delta_credits"))["s"] or 0
        revenue = Invoice.objects.filter(
            status=Invoice.Status.APPROVED, decided_at__gte=since
        ).aggregate(s=Sum("amount_cents"))["s"] or 0

        printed = jobs.filter(status=PrintJob.Status.PRINTED)
        context = self.context(
            members=User.objects.filter(role=User.Role.MEMBER).count(),
            active_members=User.objects.filter(
                role=User.Role.MEMBER, is_active=True).count(),
            pending_invites=User.objects.filter(
                invitation_accepted_at__isnull=True, is_active=True).count(),
            active_subs=Subscription.objects.filter(status="ACTIVE").count(),
            credits_out=credits_out,
            credits_held=credits_held,
            credits_consumed=-consumed,
            revenue_cents=revenue,
            revenue=Invoice.objects.none(),
            pages_printed=printed.aggregate(s=Sum("page_count"))["s"] or 0,
            jobs_printed=printed.count(),
            queue_depth=jobs.filter(status=PrintJob.Status.QUEUED).count(),
            failures=jobs.filter(status=PrintJob.Status.FAILED).count(),
            awaiting_approval=Invoice.objects.filter(
                status=Invoice.Status.AWAITING_APPROVAL).count(),
            recent_jobs=jobs.select_related("member")[:8],
            recent_invoices=Invoice.objects.filter(
                status=Invoice.Status.AWAITING_APPROVAL
            ).select_related("member")[:5],
            printer=get_backend().status(),
            tariff=Tariff.current(),
            today=timezone.localdate(),
        )
        context.update(self.chart_context(request))
        return render(request, self.template_name, context)


# --------------------------------------------------------------------------- #
# Members
# --------------------------------------------------------------------------- #
class MemberListView(ConsoleView):
    template_name = "console/members.html"
    tab = "members"

    def get(self, request):
        query = request.GET.get("q", "").strip()
        members = User.objects.filter(role=User.Role.MEMBER)
        if query:
            members = members.filter(
                Q(student_no__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query))
        members = members.annotate(
            jobs_count=Count("jobs", distinct=True),
        ).order_by("student_no")
        return render(request, self.template_name, self.context(
            members=members,
            query=query,
            today=timezone.localdate(),
        ))


class MemberCreateView(ConsoleView):
    template_name = "console/member_form.html"
    tab = "members"

    def get(self, request):
        return render(request, self.template_name, self.context(
            form=MemberForm(), title="Add a member"))

    def post(self, request):
        form = MemberForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self.context(
                form=form, title="Add a member"))

        data = form.cleaned_data
        member = create_account(
            actor=request.user,
            student_no=data["student_no"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone=data["phone"],
            role=data["role"],
        )
        try:
            send_invite(member)
            messages.success(
                request,
                f"{member.display_name} created. An invitation was sent to "
                f"{member.email}. Any plan you assign grants credits immediately.")
        except Exception as exc:            # email is not fatal
            log.exception("invitation email failed")
            messages.warning(
                request,
                f"{member.display_name} created, but the invitation email could "
                f"not be sent ({exc}). Use 'Resend invitation' on their page to "
                f"get the link.")
        return redirect("console:member_detail", pk=member.pk)


class MemberDetailView(ConsoleView):
    template_name = "console/member_detail.html"
    tab = "members"

    def get(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        account = ensure_account(member)
        context = self.context(
            member=member,
            account=account,
            subscription=member.active_subscription,
            subscriptions=member.subscriptions.select_related("plan")[:5],
            jobs=member.jobs.all()[:8],
            entries=account.entries.select_related("job", "invoice")[:8],
            invite_link=invite_url(member) if settings.DEBUG else "",
            subscribe_form=SubscribeForm(),
            credit_form=ManualCreditForm(),
            plans=Plan.objects.filter(is_active=True),
            today=timezone.localdate(),
        )
        return render(request, self.template_name, context)


class MemberUpdateView(ConsoleView):
    template_name = "console/member_form.html"
    tab = "members"

    def get(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        return render(request, self.template_name, self.context(
            form=MemberForm(instance=member), title=f"Edit {member.display_name}",
            member=member))

    def post(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        form = MemberForm(request.POST, instance=member)
        if not form.is_valid():
            return render(request, self.template_name, self.context(
                form=form, title=f"Edit {member.display_name}", member=member))
        member = form.save(commit=False)
        member.is_staff = member.role == User.Role.ADMIN
        member.save()
        messages.success(request, "Member details updated.")
        return redirect("console:member_detail", pk=member.pk)


class MemberInviteView(ConsoleView):
    tab = "members"

    def post(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        try:
            send_invite(member)
            messages.success(request, f"A new invitation was sent to {member.email}.")
        except Exception as exc:
            messages.error(request, f"Could not send the invitation: {exc}")
        return redirect("console:member_detail", pk=member.pk)


class MemberToggleView(ConsoleView):
    tab = "members"

    def post(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        if member.pk == request.user.pk:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("console:member_detail", pk=member.pk)
        member.is_active = not member.is_active
        member.save(update_fields=["is_active", "updated_at"])
        state = "reactivated" if member.is_active else "deactivated"
        messages.success(request, f"{member.display_name} {state}.")
        return redirect("console:member_detail", pk=member.pk)


class MemberSubscribeView(ConsoleView):
    tab = "members"

    def post(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        form = SubscribeForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Choose a plan first.")
            return redirect("console:member_detail", pk=member.pk)
        plan = form.cleaned_data["plan"]
        subscribe(member=member, plan=plan, actor=request.user)
        messages.success(
            request,
            f"{plan.name} activated for {member.student_no}: "
            f"{plan.grant_credits:,} credits added.")
        return redirect("console:member_detail", pk=member.pk)


class MemberCreditView(ConsoleView):
    tab = "members"

    def post(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        form = ManualCreditForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a whole number of credits and a reason.")
            return redirect("console:member_detail", pk=member.pk)

        account = ensure_account(member)
        try:
            adjust(account_id=account.id, credits=form.cleaned_data["credits"],
                   memo=form.cleaned_data["memo"], actor=request.user)
        except Exception as exc:
            messages.error(request, f"Could not add credits: {exc}")
        else:
            messages.success(
                request,
                f"{form.cleaned_data['credits']:,} credits added to "
                f"{member.student_no} (recorded as a manual adjustment).")
        return redirect("console:member_detail", pk=member.pk)


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #
class PlanListView(ConsoleView):
    template_name = "console/plans.html"
    tab = "plans"

    def get(self, request):
        return render(request, self.template_name, self.context(
            plans=Plan.objects.all().annotate(
                subscriber_count=Count("subscription", distinct=True)),
        ))


class PlanCreateView(ConsoleView):
    template_name = "console/plan_form.html"
    tab = "plans"

    def get(self, request):
        return render(request, self.template_name, self.context(
            form=PlanForm(), title="New plan"))

    def post(self, request):
        form = PlanForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self.context(
                form=form, title="New plan"))
        form.save()
        messages.success(request, "Plan created.")
        return redirect("console:plans")


class PlanUpdateView(ConsoleView):
    template_name = "console/plan_form.html"
    tab = "plans"

    def get(self, request, pk):
        plan = get_object_or_404(Plan, pk=pk)
        return render(request, self.template_name, self.context(
            form=PlanForm(instance=plan), title=f"Edit {plan.name}"))

    def post(self, request, pk):
        plan = get_object_or_404(Plan, pk=pk)
        form = PlanForm(request.POST, instance=plan)
        if not form.is_valid():
            return render(request, self.template_name, self.context(
                form=form, title=f"Edit {plan.name}"))
        form.save()
        messages.success(request, "Plan updated. Existing subscriptions keep "
                                  "the credits they were granted.")
        return redirect("console:plans")


# --------------------------------------------------------------------------- #
# Invoices (the money that needs a human)
# --------------------------------------------------------------------------- #
class InvoiceQueueView(ConsoleView):
    template_name = "console/invoices.html"
    tab = "invoices"

    def get(self, request):
        invoices = Invoice.objects.select_related("member", "decided_by")
        return render(request, self.template_name, self.context(
            awaiting=invoices.filter(status=Invoice.Status.AWAITING_APPROVAL),
            decided=invoices.exclude(
                status=Invoice.Status.AWAITING_APPROVAL)[:25],
            open_unpaid=invoices.filter(status=Invoice.Status.AWAITING_PAYMENT),
        ))


class InvoiceReviewView(ConsoleView):
    template_name = "console/invoice_review.html"
    tab = "invoices"

    def get(self, request, reference):
        invoice = get_object_or_404(Invoice, reference=reference)
        return render(request, self.template_name, self.context(
            invoice=invoice,
            member=invoice.member,
            account=ensure_account(invoice.member),
            reject_form=RejectForm(),
            previous=Invoice.objects.filter(
                member=invoice.member).exclude(pk=invoice.pk)[:5],
        ))


class InvoiceApproveView(ConsoleView):
    tab = "invoices"

    def post(self, request, reference):
        invoice = get_object_or_404(Invoice, reference=reference)
        try:
            billing.approve_invoice(invoice=invoice, by=request.user)
        except billing.InvoiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"{invoice.credits:,} credits added to {invoice.member.student_no}.")
        return redirect("console:invoices")


class InvoiceRejectView(ConsoleView):
    tab = "invoices"

    def post(self, request, reference):
        invoice = get_object_or_404(Invoice, reference=reference)
        form = RejectForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Give a reason for the rejection.")
            return redirect("console:invoice_review", reference=invoice.reference)
        try:
            billing.reject_invoice(invoice=invoice, by=request.user,
                                   reason=form.cleaned_data["reason"])
        except billing.InvoiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{invoice.reference} rejected.")
        return redirect("console:invoices")


# --------------------------------------------------------------------------- #
# The queue
# --------------------------------------------------------------------------- #
class QueueView(ConsoleView):
    template_name = "console/queue.html"
    tab = "queue"

    def get(self, request):
        jobs = PrintJob.objects.select_related("member")
        return render(request, self.template_name, self.context(
            queued=jobs.filter(status=PrintJob.Status.QUEUED),
            failures=jobs.filter(status=PrintJob.Status.FAILED)[:15],
            recent=jobs.filter(status=PrintJob.Status.PRINTED)[:15],
            printing=jobs.filter(status=PrintJob.Status.PRINTING),
            printer=get_backend().status(),
            backend=settings.PRINT_BACKEND,
            queue_depth=jobs.filter(status=PrintJob.Status.QUEUED).count(),
        ))


class QueueProcessView(ConsoleView):
    """The 'Print now' button: drain the queue in this request."""

    tab = "queue"

    def post(self, request):
        processed = printing.process_all(actor=request.user, limit=10)
        if not processed:
            messages.info(request, "Nothing was waiting in the queue.")
            return redirect("console:queue")

        printed = [j for j in processed if j.status == PrintJob.Status.PRINTED]
        failed = [j for j in processed if j.status == PrintJob.Status.FAILED]
        if printed:
            messages.success(
                request, f"Printed {len(printed)} job(s): "
                         f"{', '.join(j.code for j in printed)}.")
        if failed:
            messages.error(
                request, f"{len(failed)} job(s) failed: "
                         f"{', '.join(j.code for j in failed)}. "
                         f"Credits were returned.")
        return redirect("console:queue")


class QueueRetryView(ConsoleView):
    tab = "queue"

    def post(self, request, public_id):
        job = get_object_or_404(PrintJob, public_id=public_id)
        try:
            printing.retry_job(job, actor=request.user)
        except Exception as exc:
            messages.error(request, f"Could not retry {job.code}: {exc}")
        else:
            messages.success(request, f"{job.code} is back in the queue.")
        return redirect("console:queue")


class QueueCancelView(ConsoleView):
    tab = "queue"

    def post(self, request, public_id):
        job = get_object_or_404(PrintJob, public_id=public_id)
        try:
            printing.cancel_job(job, actor=request.user)
        except Exception as exc:
            messages.error(request, f"Could not cancel {job.code}: {exc}")
        else:
            messages.success(request, f"{job.code} cancelled; credits released.")
        return redirect("console:queue")


# --------------------------------------------------------------------------- #
# All jobs + CSV
# --------------------------------------------------------------------------- #
class JobBrowserView(ConsoleView):
    template_name = "console/jobs.html"
    tab = "jobs"

    def get(self, request):
        if request.GET.get("export") == "csv":
            return self._csv()

        jobs = PrintJob.objects.select_related("member")
        status = request.GET.get("status", "")
        query = request.GET.get("q", "").strip()
        if status in dict(PrintJob.Status.choices):
            jobs = jobs.filter(status=status)
        if query:
            jobs = jobs.filter(Q(code__icontains=query)
                               | Q(member__student_no__icontains=query)
                               | Q(original_name__icontains=query))
        return render(request, self.template_name, self.context(
            jobs=jobs[:200],
            status=status,
            query=query,
            status_choices=PrintJob.Status.choices,
        ))

    def _csv(self):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="print-jobs.csv"'
        writer = csv.writer(response)
        writer.writerow(["code", "student_no", "created", "document", "pages",
                         "colour", "sides", "paper", "copies", "credits",
                         "status", "printed_at", "failure_reason"])
        for job in PrintJob.objects.select_related("member").iterator():
            writer.writerow([
                job.code, job.member.student_no, job.created_at.isoformat(),
                job.original_name, job.page_count, job.colour_mode, job.sides,
                job.paper, job.copies, job.cost_credits, job.status,
                job.printed_at or "", job.failure_reason,
            ])
        return response


# --------------------------------------------------------------------------- #
# Settings / status
# --------------------------------------------------------------------------- #
class SettingsView(ConsoleView):
    template_name = "console/settings.html"
    tab = "settings"

    def get(self, request):
        return render(request, self.template_name, self.context(
            tariff=Tariff.current(),
            printer=get_backend().status(),
            backend=settings.PRINT_BACKEND,
            society_momo=settings.SOCIETY_MOMO_NUMBER,
            society_momo_name=settings.SOCIETY_MOMO_NAME,
            credits_per_rand=settings.CREDITS_PER_RAND,
            topup_min=settings.TOPUP_MIN_CENTS,
            topup_max=settings.TOPUP_MAX_CENTS,
            invoice_ttl=settings.INVOICE_TTL_HOURS,
            job_expiry=settings.JOB_EXPIRY_HOURS,
            email_backend=settings.EMAIL_BACKEND,
            debug=settings.DEBUG,
        ))
