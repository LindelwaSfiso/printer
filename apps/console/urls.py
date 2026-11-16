from django.urls import path

from . import views

app_name = "console"
urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),

    path("members/", views.MemberListView.as_view(), name="members"),
    path("members/new/", views.MemberCreateView.as_view(), name="member_new"),
    path("members/<int:pk>/", views.MemberDetailView.as_view(), name="member_detail"),
    path("members/<int:pk>/edit/", views.MemberUpdateView.as_view(), name="member_edit"),
    path("members/<int:pk>/invite/", views.MemberInviteView.as_view(),
         name="member_invite"),
    path("members/<int:pk>/toggle/", views.MemberToggleView.as_view(),
         name="member_toggle"),
    path("members/<int:pk>/subscribe/", views.MemberSubscribeView.as_view(),
         name="member_subscribe"),
    path("members/<int:pk>/credit/", views.MemberCreditView.as_view(),
         name="member_credit"),

    path("plans/", views.PlanListView.as_view(), name="plans"),
    path("plans/new/", views.PlanCreateView.as_view(), name="plan_new"),
    path("plans/<int:pk>/edit/", views.PlanUpdateView.as_view(), name="plan_edit"),

    path("invoices/", views.InvoiceQueueView.as_view(), name="invoices"),
    path("invoices/<str:reference>/", views.InvoiceReviewView.as_view(),
         name="invoice_review"),
    path("invoices/<str:reference>/approve/", views.InvoiceApproveView.as_view(),
         name="invoice_approve"),
    path("invoices/<str:reference>/reject/", views.InvoiceRejectView.as_view(),
         name="invoice_reject"),

    path("queue/", views.QueueView.as_view(), name="queue"),
    path("queue/process/", views.QueueProcessView.as_view(), name="queue_process"),
    path("queue/<uuid:public_id>/retry/", views.QueueRetryView.as_view(),
         name="queue_retry"),
    path("queue/<uuid:public_id>/cancel/", views.QueueCancelView.as_view(),
         name="queue_cancel"),

    path("jobs/", views.JobBrowserView.as_view(), name="jobs"),
    path("settings/", views.SettingsView.as_view(), name="settings"),
]