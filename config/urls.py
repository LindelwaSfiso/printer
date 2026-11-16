from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("jobs/", include("apps.printing.urls")),
    path("credits/", include("apps.credits.urls")),
    path("billing/", include("apps.billing.urls")),
    path("manage/", include("apps.console.urls")),
]