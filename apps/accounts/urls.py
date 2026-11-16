from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.RoleAwareLoginView.as_view(), name="login"),
    path("logout/", views.SignOutView.as_view(), name="logout"),
    path("home/", views.HomeView.as_view(), name="home"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("invite/<uidb64>/<token>/", views.AcceptInviteView.as_view(),
         name="accept_invite"),
]