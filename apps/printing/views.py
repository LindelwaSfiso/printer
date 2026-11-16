import logging
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.mixins import MemberRequiredMixin
from apps.credits.services import ensure_account

from . import services
from .forms import UploadJobForm
from .models import PrintJob, Tariff
from .validators import inspect_pdf

log = logging.getLogger(__name__)


class JobListView(LoginRequiredMixin, View):
    template_name = "printing/job_list.html"

    def get(self, request):
        if request.user.is_staff:
            return redirect("console:queue")

        jobs = PrintJob.objects.filter(member=request.user)
        status = request.GET.get("status", "")
        if status in dict(PrintJob.Status.choices):
            jobs = jobs.filter(status=status)

        context = {
            "jobs": jobs[:100],
            "active_status": status,
            "account": ensure_account(request.user),
            "counts": {
                "all": PrintJob.objects.filter(member=request.user).count(),
                "queued": PrintJob.objects.filter(
                    member=request.user, status=PrintJob.Status.QUEUED).count(),
                "printed": PrintJob.objects.filter(
                    member=request.user, status=PrintJob.Status.PRINTED).count(),
                "failed": PrintJob.objects.filter(
                    member=request.user, status=PrintJob.Status.FAILED).count(),
            },
            "status_choices": PrintJob.Status.choices,
        }
        return render(request, self.template_name, context)


class JobCreateView(MemberRequiredMixin, View):
    template_name = "printing/job_new.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": UploadJobForm(),
            "tariff": Tariff.current(),
            "account": ensure_account(request.user),
        })

    def post(self, request):
        form = UploadJobForm(request.POST, request.FILES)
        account = ensure_account(request.user)

        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form, "tariff": Tariff.current(), "account": account})

        try:
            pages = inspect_pdf(form.cleaned_data["document"])
        except ValidationError as exc:
            form.add_error("document", exc.messages[0])
            return render(request, self.template_name, {
                "form": form, "tariff": Tariff.current(), "account": account})

        job = services.create_draft(
            member=request.user,
            uploaded=form.cleaned_data["document"],
            cleaned={**form.cleaned_data, "page_count": pages},
        )
        return redirect("printing:job_detail", public_id=job.public_id)


class JobDetailView(LoginRequiredMixin, View):
    template_name = "printing/job_detail.html"

    def _get_job(self, request, public_id):
        job = get_object_or_404(PrintJob, public_id=public_id)
        if job.member_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied
        return job

    def get(self, request, public_id):
        job = self._get_job(request, public_id)
        return render(request, self.template_name, {
            "job": job,
            "account": ensure_account(job.member),
            "queue_position": job.queue_position(),
        })

    def post(self, request, public_id):
        """The confirm action: reserve the credits."""
        job = self._get_job(request, public_id)
        if job.status != PrintJob.Status.DRAFT:
            messages.info(request, "This job was already submitted.")
            return redirect("printing:job_detail", public_id=job.public_id)
        try:
            services.confirm_job(job)
        except Exception as exc:
            messages.error(request, f"Could not queue the job: {exc}")
        else:
            messages.success(request, f"Job {job.code} is in the queue.")
        return redirect("printing:job_detail", public_id=job.public_id)


class JobCancelView(LoginRequiredMixin, View):
    def post(self, request, public_id):
        job = get_object_or_404(PrintJob, public_id=public_id)
        if job.member_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied
        try:
            services.cancel_job(job, actor=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Job cancelled. Any reserved credits are back.")
            if job.status == PrintJob.Status.DRAFT:
                return redirect("printing:job_list")
        return redirect("accounts:home")


class JobRetryView(LoginRequiredMixin, View):
    def post(self, request, public_id):
        job = get_object_or_404(PrintJob, public_id=public_id)
        if job.member_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied
        try:
            services.retry_job(job, actor=request.user)
        except Exception as exc:
            messages.error(request, f"Could not retry: {exc}")
        else:
            messages.success(request, f"Job {job.code} is queued again.")
        return redirect("printing:job_detail", public_id=job.public_id)


class JobFileView(LoginRequiredMixin, View):
    """The uploaded document. Only the owner and staff can read it."""

    def get(self, request, public_id):
        job = get_object_or_404(PrintJob, public_id=public_id)
        if job.member_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied
        if not job.document:
            raise Http404("The document was removed from storage.")
        return FileResponse(job.document.open("rb"), as_attachment=True,
                            filename=job.original_name)


class JobOutputView(LoginRequiredMixin, View):
    """What the queue produced: the PDF with the cover sheet, as it would print."""

    def get(self, request, public_id):
        job = get_object_or_404(PrintJob, public_id=public_id)
        if job.member_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied
        if not job.output_file:
            raise Http404("This job has no printed output yet.")

        path = Path(settings.MEDIA_ROOT) / job.output_file
        if not path.exists():
            raise Http404("The printed output is no longer on disk.")
        return FileResponse(open(path, "rb"), as_attachment=True,
                            filename=f"{job.code}.pdf")