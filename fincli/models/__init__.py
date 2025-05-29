# file: fincli/models/__init__.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Literal, Annotated

import pandas as pd
from pydantic import BaseModel, Field

from ..utils.fx import to_eur

# ──────────────────────────────────────────────────────────────────────────────
# Domain Value Objects
# ──────────────────────────────────────────────────────────────────────────────
class Asset(BaseModel):
    name: str
    isin: str | None = Field(None, pattern=r"[A-Z]{2}[A-Z0-9]{10}")
    ticker: str | None = None


class Money(BaseModel):
    amount: Decimal
    currency: Literal["EUR", "USD", "GBP"]  # Enough for now, extend as needed

    def convert_to_eur(
        self,
        on: datetime,
        csv_path: str | Path = "utilsData/eurofxref-hist.csv",
    ) -> Money:
        """
        Return a new Money in EUR using historical FX on `on` as looked up
        from the CSV at `csv_path`.
        """
        # no-op if already EUR
        if self.currency == "EUR":
            return self

        # perform lookup + conversion
        eur_amount = to_eur(self.currency, self.amount, on, Path(csv_path))
        # quantize to cents
        eur_amount = eur_amount.quantize(Decimal("0.01"))

        return Money(amount=eur_amount, currency="EUR")

    


# ──────────────────────────────────────────────────────────────────────────────
# Financial Operations
# ──────────────────────────────────────────────────────────────────────────────
class BuyOperation(BaseModel):
    class__: Literal["BuyOperation"] = Field("BuyOperation", Literal=True)
    asset: Asset
    unit_price: Money
    quantity: Decimal
    commission: Money | None = None
    date: datetime

    def __str__(self):
        base = (f"Bought {str(self.quantity)} × {self.asset.name} @ {str(self.unit_price.amount)} {self.unit_price.currency}"
                f" on {self.date.date().isoformat()}")
        if self.commission:
            base += f" (commission: {str(self.commission.amount)} {self.commission.currency})"
        return base

class SellOperation(BaseModel):
    class__: Literal["SellOperation"] = Field("SellOperation", Literal=True)
    asset: Asset
    unit_price: Money
    quantity: Decimal
    commission: Money | None = None
    date: datetime

    def __str__(self):
        base = (f"Sold  {self.quantity} × {self.asset} @ {self.unit_price}"
                f" on {self.date.date().isoformat()}")
        if self.commission:
            base += f" (commission: {self.commission})"
        return base

class Dividend(BaseModel):
    class__: Literal["Dividend"] = Field("Dividend", Literal=True)
    asset: Asset
    gross: Money
    date: datetime

    def __str__(self):
        return (f"Dividend of {self.gross} from {self.asset}"
                f" on {self.date.date().isoformat()}")

class Interest(BaseModel):
    class__: Literal["Interest"] = Field("Interest", Literal=True)
    gross: Money
    date: datetime

    def __str__(self):
        return (f"Interest payment of {self.gross}"
                f" on {self.date.date().isoformat()}")

class AssetTrade(BaseModel):
    class__: Literal["AssetTrade"] = Field("AssetTrade", Literal=True)
    buy: BuyOperation
    sell: SellOperation
    pnl: Money  # positive = profit, negative = loss

    def __str__(self):
        return (
            f"{self.buy}\n"
            f"{self.sell}\n"
            f"→ PnL: {self.pnl}"
        )

# Discriminated union
FinOp = Annotated[
    BuyOperation | SellOperation | Dividend | Interest | AssetTrade,
    Field(discriminator="class__"),
]

class RawDataOut(BaseModel):
    parser_name: str
    records: List[FinOp]

    def __str__(self):
        lines = [f"Parser: {self.parser_name}", "Records:"]
        for op in self.records:
            # indent each line of op.__str__()
            for line in str(op).splitlines():
                lines.append("  " + line)
        return "\n".join(lines)

# ──────────────────────────────────────────────────────────────────────────────
# Processor I/O Contracts
# ──────────────────────────────────────────────────────────────────────────────
class SavingPerformanceIn(BaseModel):
    operations: list[FinOp]


class SavingPerformanceOut(BaseModel):
    year: int
    total_eur: Decimal
    records: list[FinOp]


class TradingPerformanceIn(BaseModel):
    operations: list[FinOp]


class AssetPNL(BaseModel):
    asset: Asset
    pnl: Money
    trades: list[AssetTrade]


class TradingPerformanceOut(BaseModel):
    year: int
    summary: list[AssetPNL]


# ──────────────────────────────────────────────────────────────────────────────
# Parser Configurations
# ──────────────────────────────────────────────────────────────────────────────
class TRParserConfig(BaseModel):
    """
    Configuration for BingxParser:
      - path: single CSV file or directory
      - glob: filename pattern if you point at a directory
    """ 
    data_dir: str
    csv_glob: str = "*.csv"
    encoding: str = "utf-8"
    sep: str = ";"

class BingxParserConfig(BaseModel):
    """
    Configuration for BingxParser:
      - path: single CSV file or directory
      - glob: filename pattern if you point at a directory
    """
    path: str
    glob: str = "*.csv"
    encoding: str = "utf-8"
    sep: str = ";"