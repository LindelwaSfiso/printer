from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from .services import ensure_account


class CreditHistoryView(LoginRequiredMixin, View):
    """A member's own statement."""

    template_name = "credits/history.html"

    def get(self, request):
        if request.user.is_staff:
            return redirect("console:dashboard")
        account = ensure_account(request.user)
        entries = (account.entries
                   .select_related("job", "invoice", "created_by")
                   .order_by("-created_at"))
        return render(request, self.template_name,
                      {"account": account, "entries": entries})