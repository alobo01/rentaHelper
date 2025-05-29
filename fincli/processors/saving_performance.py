from decimal import Decimal

from ..models import (
    FinOp, SavingPerformanceIn, SavingPerformanceOut,
    Dividend, Interest,
)
from .abstract import AbstractProcessor

# ──────────────────────────────────────────────────────────────────────────────
# Saving performance (Dividends + Interest)
# ──────────────────────────────────────────────────────────────────────────────


class SavingPerformanceProcessor(AbstractProcessor):
    input_model = SavingPerformanceIn
    output_model = SavingPerformanceOut

    def __init__(self, year: int):
        self.year = year

    def process(self, data: SavingPerformanceIn) -> SavingPerformanceOut:
        total_eur = Decimal("0")
        recs: list[FinOp] = []

        for op in data.operations:
            if isinstance(op, Dividend) and op.date.year == self.year:
                total_eur += op.gross.amount
                recs.append(op)
            elif isinstance(op, Interest) and op.date.year == self.year:
                total_eur += op.gross.amount
                recs.append(op)

        return SavingPerformanceOut(
            year=self.year,
            total_eur=total_eur,
            records=sorted(recs, key=lambda x: x.date),
        )