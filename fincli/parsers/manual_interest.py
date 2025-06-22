from __future__ import annotations
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import pandas as pd

from .abstract import AbstractParser
from ..models import (
    ManualInterestParserConfig,
    Interest, Money, FinOp,
)

class ManualInterestParser(AbstractParser):
    """
    Parses manual interest CSVs with format:
      year;quantity;currency;tax;source
    Creates one Interest record per line, setting date to Jan 1 of that year.
    """
    config_model = ManualInterestParserConfig

    def __init__(self, config: ManualInterestParserConfig):
        super().__init__(config)

    def load(self) -> pd.DataFrame:
        records: list[FinOp] = []
        path = Path(self.config.path)
        files = [path] if path.is_file() else list(path.glob(self.config.glob))

        for f in files:
            df = pd.read_csv(
                f,
                sep=self.config.sep,
                encoding=self.config.encoding,
                dtype=str,
                skip_blank_lines=True,
            )
            for row in df.itertuples(index=False):
                try:
                    year = int(getattr(row, 'year'))
                    qty = Decimal(str(getattr(row, 'quantity')))
                    currency = getattr(row, 'currency')
                    tax_amt = Decimal(str(getattr(row, 'tax')))
                    source = getattr(row, 'source')
                except Exception:
                    continue
                date = datetime(year, 1, 1)
                # Gross interest
                records.append(
                    Interest(
                        gross=Money(amount=qty, currency=currency),
                        tax=Money(amount=tax_amt, currency=currency),
                        date=date,
                        source=source,
                    )
                )
        df_out = pd.DataFrame([r.model_dump() for r in records])
        df_out['__object__'] = records
        return df_out
