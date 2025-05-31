from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import pandas as pd

from .abstract import AbstractParser
from ..models import (
    RevolutParserConfig,
    Interest, Money, FinOp,
)

# map Spanish month abbreviations to month numbers
_SPANISH_MONTHS = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4,
    'mayo': 5, 'jun': 6, 'jul': 7, 'ago': 8,
    'sept': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}

def _parse_spanish_datetime(s: str) -> datetime:
    # s like '31 dic 2024, 1:29:07'
    date_part, time_part = s.split(',', 1)
    day, mon_str, year = date_part.strip().split()
    mon = _SPANISH_MONTHS[mon_str.lower()]
    hour, minute, second = time_part.strip().split(':')
    return datetime(
        year=int(year), month=mon, day=int(day),
        hour=int(hour), minute=int(minute), second=int(second)
    )

class RevolutParser(AbstractParser):
    """
    Parses Revolut savings CSVs of form:
      Date;Description;Value, EUR;Price per share;Quantity of shares
    Treats all lines as Interest (positive or negative).
    """
    config_model = RevolutParserConfig

    def __init__(self, config: RevolutParserConfig):
        super().__init__(config)

    def load(self) -> pd.DataFrame:
        path = Path(self.config.path)
        files = [path] if path.is_file() else list(path.glob(self.config.glob))

        # temp store: key -> dict with date, gross, tax
        grouped = defaultdict(lambda: {"date": None, "gross": Decimal(0), "tax": Decimal(0)})

        for f in files:
            text = f.read_text(encoding=self.config.encoding)
            for line in text.splitlines()[1:]:
                if not line.strip():
                    continue
                parts = line.split(self.config.sep)
                raw_date = parts[0]
                desc     = parts[1]
                raw_value= parts[2].replace(',', '.').strip()
                try:
                    dt  = _parse_spanish_datetime(raw_date)
                    val = Decimal(raw_value)
                except Exception:
                    continue

                # Determine key: use description without trailing ' Tax'
                key_desc = desc.replace(" Tax", "").strip()

                entry = grouped[key_desc]
                # record date from the non-tax line (first occurrence)
                if entry["date"] is None and "Interest" in desc:
                    entry["date"] = dt

                # gross vs tax
                if "Tax" in desc:
                    entry["tax"] += abs(val)
                else:
                    entry["gross"] += val

                grouped[key_desc] = entry

        # build model instances
        records: list[FinOp] = []
        for source, vals in grouped.items():
            if vals["date"] is None:
                continue
            records.append(
                Interest(
                    gross=Money(amount=vals["gross"], currency="EUR"),
                    tax=Money(amount=vals["tax"], currency="EUR"),
                    date=vals["date"],
                    source=source
                )
            )

        # assemble DataFrame
        df_out = pd.DataFrame([r.model_dump() for r in records])
        df_out["__object__"] = records
        return df_out