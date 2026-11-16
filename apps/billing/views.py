from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.credits.services import ensure_account

from . import services
from .forms import PaymentProofForm, TopUpForm
from .models import Invoice


class InvoiceListView(LoginRequiredMixin, View):
    template_name = "billing/invoice_list.html"

    def get(self, request):
        if request.user.is_staff:
            return redirect("console:invoices")
        invoices = Invoice.objects.filter(member=request.user)
        return render(request, self.template_name, {
            "invoices": invoices[:50],
            "account": ensure_account(request.user),
            "open_count": invoices.filter(
                status__in=[Invoice.Status.AWAITING_PAYMENT,
                            Invoice.Status.AWAITING_APPROVAL]).count(),
        })


class TopUpView(LoginRequiredMixin, View):
    template_name = "billing/topup.html"

    def get(self, request):
        if request.user.is_staff:
            return redirect("console:invoices")
        return render(request, self.template_name, {
            "form": TopUpForm(),
            "account": ensure_account(request.user),
            "presets": TopUpForm.PRESETS,
        })

    def post(self, request):
        form = TopUpForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "account": ensure_account(request.user),
                "presets": TopUpForm.PRESETS,
            })
        invoice = services.create_invoice(
            member=request.user, amount_cents=form.amount_cents)
        messages.success(
            request, f"Invoice {invoice.reference} created. Pay it, then record the "
                     f"transaction ID.")
        return redirect("billing:invoice_detail", reference=invoice.reference)


class InvoiceDetailView(LoginRequiredMixin, View):
    template_name = "billing/invoice_detail.html"

    def get(self, request, reference):
        invoice = get_object_or_404(Invoice, reference=reference)
        if invoice.member_id != request.user.id and not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return render(request, self.template_name, {
            "invoice": invoice,
            "form": PaymentProofForm(initial={
                "payer_phone": invoice.payer_phone or invoice.member.phone,
            }),
            "account": ensure_account(invoice.member),
        })


class SubmitTransactionView(LoginRequiredMixin, View):
    template_name = "billing/invoice_detail.html"

    def post(self, request, reference):
        invoice = get_object_or_404(Invoice, reference=reference,
                                    member=request.user)
        form = PaymentProofForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {
                "invoice": invoice,
                "form": form,
                "account": ensure_account(invoice.member),
            })
        try:
            services.submit_transaction_id(
                invoice=invoice,
                txn_id=form.cleaned_data["momo_txn_id"],
                payer_phone=form.cleaned_data["payer_phone"],
                proof=form.cleaned_data.get("proof_file"),
            )
        except services.InvoiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Sent to the treasurer. You will see the "
                                      "credits here as soon as it is approved.")
        return redirect("billing:invoice_detail", reference=invoice.reference)


class CancelInvoiceView(LoginRequiredMixin, View):
    def post(self, request, reference):
        invoice = get_object_or_404(Invoice, reference=reference,
                                    member=request.user)
        try:
            services.cancel_invoice(invoice=invoice)
        except services.InvoiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Invoice {invoice.reference} cancelled.")
        return redirect("billing:invoice_list")


class InvoiceProofView(LoginRequiredMixin, View):
    """Download the uploaded proof of payment."""

    def get(self, request, reference):
        from django.core.exceptions import PermissionDenied
        from django.http import FileResponse, Http404

        invoice = get_object_or_404(Invoice, reference=reference)
        if invoice.member_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied
        if not invoice.proof_file:
            raise Http404("No proof was uploaded.")
        return FileResponse(invoice.proof_file.open("rb"), as_attachment=True,
                            filename=f"{invoice.reference}-proof")
