from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class StaffRequiredMixin(LoginRequiredMixin):
    """Administrators only. This is the gate on the whole /manage/ area."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not request.user.is_staff:
            messages.error(request, "That area is for administrators.")
            return redirect("accounts:home")
        return super().dispatch(request, *args, **kwargs)


class MemberRequiredMixin(LoginRequiredMixin):
    """An approved, active member.

    Note what this does *not* check: a subscription. Credits are what pay for
    printing, and a member can buy them with a top-up without ever taking a
    plan. The credit balance is checked when the job's reservation is placed.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if request.user.is_staff:
            return redirect("console:dashboard")
        if not request.user.can_print:
            if request.user.active_subscription is None and \
                    settings.REQUIRE_SUBSCRIPTION_TO_PRINT:
                messages.error(
                    request,
                    "An active subscription is required to print. Ask the society "
                    "office to activate a plan.")
            else:
                messages.error(
                    request,
                    "This account cannot submit print jobs. Ask the society office "
                    "to check your membership.")
            return redirect("accounts:home")
        return super().dispatch(request, *args, **kwargs)
