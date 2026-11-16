from django import forms
from django.conf import settings

from apps.core.forms import StyledFormMixin
from apps.core.utils import to_cents


class TopUpForm(StyledFormMixin, forms.Form):
    PRESETS = [("5", "E5"), ("10", "E10"), ("20", "E20"), ("50", "E50"),
               ("100", "E100"), ("200", "E200")]

    amount = forms.DecimalField(
        label="Amount (E)",
        min_value=settings.TOPUP_MIN_CENTS / 100,
        max_value=settings.TOPUP_MAX_CENTS / 100,
        max_digits=7, decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "5", "inputmode": "decimal",
                                        "placeholder": "20.00"}))

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        self.amount_cents = to_cents(amount)
        return amount


class PaymentProofForm(StyledFormMixin, forms.Form):
    momo_txn_id = forms.CharField(
        label="Transaction ID",
        max_length=40,
        help_text="The code in the mobile-money SMS you received.")
    payer_phone = forms.CharField(
        label="Phone you paid from", max_length=16,
        help_text="So the treasurer can match the payment.")
    proof_file = forms.FileField(
        label="Screenshot (optional)", required=False,
        help_text="A photo or screenshot of the confirmation SMS, up to 2 MB.")


class RejectForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(
        label="Reason for rejection", max_length=200,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. No matching payment on the statement"}))


class ManualCreditForm(StyledFormMixin, forms.Form):
    credits = forms.IntegerField(
        label="Credits to add", min_value=1, max_value=100_000,
        widget=forms.NumberInput(attrs={"placeholder": "200"}))
    memo = forms.CharField(
        label="Reason / receipt", max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Cash paid at the desk, receipt 12"}))