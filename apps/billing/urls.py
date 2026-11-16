from django.urls import path

from . import views

app_name = "billing"
urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="invoice_list"),
    path("topup/", views.TopUpView.as_view(), name="topup"),
    path("<str:reference>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("<str:reference>/submit/", views.SubmitTransactionView.as_view(),
         name="invoice_submit"),
    path("<str:reference>/cancel/", views.CancelInvoiceView.as_view(),
         name="invoice_cancel"),
    path("<str:reference>/proof/", views.InvoiceProofView.as_view(),
         name="invoice_proof"),
]