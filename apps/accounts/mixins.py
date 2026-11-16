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
    """A student with an active subscription."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if request.user.is_staff:
            return redirect("console:dashboard")
        if not request.user.can_print:
            messages.error(
                request,
                "You need an active subscription before you can print. "
                "Ask the society office to activate one.")
            return redirect("accounts:home")
        return super().dispatch(request, *args, **kwargs)