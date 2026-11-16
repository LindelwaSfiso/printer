from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect


def health(request):
    """Liveness probe: proves the process is up and the database answers."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


def home(request):
    """One entry point, two destinations."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.is_staff:
        return redirect("console:dashboard")
    return redirect("accounts:home")