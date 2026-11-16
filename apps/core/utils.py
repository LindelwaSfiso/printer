"""Formatting and parsing helpers for the two units we use.

Credits are the print currency (integer, 10 credits = E1.00).
Cents are money, and only appear on plan prices and invoices.
Never do arithmetic on a formatted string, and never store a credit as a float.
"""
import re
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings


def fmt_credits(credits: int) -> str:
    """430 -> '430 credits'"""
    return f"{credits:,} credits"


def credits_to_rand(credits: int) -> str:
    """430 -> 'E43.00' (display only)"""
    per = settings.CREDITS_PER_RAND
    whole, remainder = divmod(int(credits), per)
    cents = remainder * 100 // per
    return f"E{whole:,}.{cents:02d}"


def to_cents(amount) -> int:
    """'50.00' -> 5000, without float rounding."""
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"),
                                                     rounding=ROUND_HALF_UP))


def cents_to_rand(cents: int) -> str:
    """5000 -> 'E50.00'"""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}E{cents // 100:,}.{cents % 100:02d}"


def rand_to_credits(amount) -> int:
    """'50.00' -> 500 credits, using the configured rate."""
    return to_cents(amount) * settings.CREDITS_PER_RAND // 100


def normalize_txn_id(raw: str) -> str:
    """Uppercase and strip separators: 'mp 260714-1234' -> 'MP2607141234'."""
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())