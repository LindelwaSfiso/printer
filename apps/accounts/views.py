import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View

from apps.credits.models import CreditEntry
from apps.credits.services import ensure_account
from apps.printing.models import PrintJob

from .forms import LoginForm, ProfileForm, SetPasswordForm
from .models import User
from .services import accept_invite

log = logging.getLogger(__name__)


class RoleAwareLoginView(LoginView):
    """Students land on their dashboard, staff on the admin dashboard."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or (
            reverse("console:dashboard") if self.request.user.is_staff
            else reverse("accounts:home"))


class SignOutView(LogoutView):
    next_page = "accounts:login"


class AcceptInviteView(View):
    """The page the emailed link opens: choose a password, then sign in."""

    template_name = "accounts/accept_invite.html"

    def _resolve(self, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None
        if not default_token_generator.check_token(user, token):
            return None
        return user

    def get(self, request, uidb64, token):
        user = self._resolve(uidb64, token)
        if user is None:
            return render(request, "accounts/invite_invalid.html", status=400)
        if user.has_usable_password() and user.invitation_accepted_at:
            messages.info(request, "You have already set a password. Please sign in.")
            return redirect("accounts:login")
        return render(request, self.template_name,
                      {"form": SetPasswordForm(user=user), "invited_user": user})

    def post(self, request, uidb64, token):
        user = self._resolve(uidb64, token)
        if user is None:
            return render(request, "accounts/invite_invalid.html", status=400)
        form = SetPasswordForm(request.POST, user=user)
        if not form.is_valid():
            return render(request, self.template_name,
                          {"form": form, "invited_user": user})
        accept_invite(user, form.cleaned_data["password1"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Welcome, {user.display_name}. Your password is set.")
        return redirect("console:dashboard" if user.is_staff else "accounts:home")


class HomeView(LoginRequiredMixin, View):
    """The student dashboard."""

    template_name = "accounts/home.html"

    def get(self, request):
        if request.user.is_staff:
            return redirect("console:dashboard")

        account = ensure_account(request.user)
        jobs = PrintJob.objects.filter(member=request.user)
        entries = account.entries.select_related("job", "invoice")[:8]

        printed = jobs.filter(status=PrintJob.Status.PRINTED)
        context = {
            "account": account,
            "subscription": request.user.active_subscription,
            "recent_jobs": jobs[:6],
            "recent_entries": entries,
            "jobs_total": jobs.count(),
            "jobs_printed": printed.count(),
            "pages_printed": sum(j.page_count for j in printed) if printed else 0,
            "jobs_queued": jobs.filter(status=PrintJob.Status.QUEUED).count(),
            "jobs_failed": jobs.filter(status=PrintJob.Status.FAILED).count(),
        }
        from apps.printing.stats import daily_pages
        context["chart"] = daily_pages(days=30, member=request.user)
        return render(request, self.template_name, context)


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get(self, request):
        return render(request, self.template_name,
                      {"form": ProfileForm(instance=request.user)})

    def post(self, request):
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your details were updated.")
            return redirect("accounts:profile")
        return render(request, self.template_name, {"form": form})