"""The tariff calculation. Pure functions, no database writes, easy to test.

Rules (all integer arithmetic -- never a float):
    sides = pages x copies
    rate  = (colour ? colour_rate : mono_rate) x (A3 ? 200 : 100) / 100
    if duplex: rate = rate x (100 - discount) / 100      # applied per side
    total = max(sides x rate, minimum_charge)
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Quote:
    page_count: int
    copies: int
    sides: int
    rate_credits: int
    gross_credits: int
    total_credits: int

    @property
    def discount_credits(self):
        return self.gross_credits - self.total_credits

    def as_snapshot(self, tariff) -> dict:
        """Everything needed to explain this price, years later."""
        return {
            "tariff_id": tariff.pk,
            "rates": {
                "mono_a4": tariff.mono_a4_credits,
                "colour_a4": tariff.colour_a4_credits,
                "a3_percent": tariff.a3_multiplier_percent,
                "duplex_discount": tariff.duplex_discount_percent,
                "minimum": tariff.minimum_charge_credits,
            },
            "quote": asdict(self),
        }


def quote(*, page_count: int, copies: int, colour: bool, duplex: bool, a3: bool,
          tariff) -> Quote:
    sides = int(page_count) * int(copies)

    rate = tariff.colour_a4_credits if colour else tariff.mono_a4_credits
    if a3:
        rate = rate * tariff.a3_multiplier_percent // 100
    if duplex:
        rate = rate * (100 - tariff.duplex_discount_percent) // 100

    gross = sides * rate
    total = max(gross, tariff.minimum_charge_credits)
    return Quote(page_count=page_count, copies=copies, sides=sides,
                 rate_credits=rate, gross_credits=gross, total_credits=total)
