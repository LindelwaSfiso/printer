from django.urls import path

from . import views

app_name = "printing"
urlpatterns = [
    path("", views.JobListView.as_view(), name="job_list"),
    path("new/", views.JobCreateView.as_view(), name="job_new"),
    path("<uuid:public_id>/", views.JobDetailView.as_view(), name="job_detail"),
    path("<uuid:public_id>/cancel/", views.JobCancelView.as_view(), name="job_cancel"),
    path("<uuid:public_id>/retry/", views.JobRetryView.as_view(), name="job_retry"),
    path("<uuid:public_id>/file/", views.JobFileView.as_view(), name="job_file"),
    path("<uuid:public_id>/output/", views.JobOutputView.as_view(), name="job_output"),
]