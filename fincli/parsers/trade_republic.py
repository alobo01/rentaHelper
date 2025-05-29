from __future__ import annotations
from pathlib import Path
from decimal import Decimal

import pandas as pd
from pydantic import BaseModel

from ..models import (
    Asset, Money,
    BuyOperation, SellOperation, Dividend, Interest,
    FinOp, TRParserConfig,
)
from .abstract import AbstractParser

class TradeRepublicParser(AbstractParser):
    config_model = TRParserConfig

    def __init__(self, config: TRParserConfig):
        super().__init__(config)

    def load(self) -> pd.DataFrame:
        """Parse *all* CSVs inside `data_dir` into a canonical dataframe."""
        frames: list[pd.DataFrame] = []
        path = Path(self.config.data_dir)
        for csv in path.glob(self.config.csv_glob):
            frames.append(
                pd.read_csv(
                    csv,
                    sep=self.config.sep,
                    encoding=self.config.encoding,
                    parse_dates=["Fecha"],
                    dayfirst=False,
                )
            )
        raw = pd.concat(frames, ignore_index=True)

        # Map raw -> strongly-typed rows (dicts) – keeps processors clean
        records: list[FinOp] = []
        for _, row in raw.iterrows():
            kind = row["Tipo"]
            date = row["Fecha"]
            amount = Decimal(str(row["Valor"]))  # TR uses decimal '.' but negative for outflow
            note = str(row["Nota"]).strip() if pd.notna(row["Nota"]) else "Undefined"
            isin = str(row["ISIN"]) if pd.notna(row["ISIN"]) else None
            quantity = Decimal("1") if pd.isna(row["Cantidad"]) else Decimal(str(row["Cantidad"]))
            comission = Decimal("0") if pd.isna(row.get("Comisiones", 0)) else abs(Decimal(str(row.get("Comisiones", 0))))

            if kind == "Compra":
                records.append(
                    BuyOperation(
                        asset=Asset(name=note, isin=isin),
                        unit_price=Money(amount=abs(amount)/quantity, currency="EUR"),
                        quantity=quantity,
                        commission=Money(amount=comission, currency="EUR"),
                        date=date,
                    )
                )
            elif kind == "Venta":
                records.append(
                    SellOperation(
                        asset=Asset(name=note, isin=isin),
                        unit_price=Money(amount=abs(amount)/quantity, currency="EUR"),
                        quantity=Decimal("1") if pd.isna(row["Cantidad"]) else Decimal(str(row["Cantidad"])),
                        commission=Money(amount=comission, currency="EUR"),
                        date=date,
                    )
                )
            elif kind == "Dividendo":
                records.append(
                    Dividend(
                        asset=Asset(name=note, isin=isin),
                        gross=Money(amount=abs(amount), currency="EUR"),
                        date=date,
                    )
                )
            elif kind == "Intereses":
                records.append(
                    Interest(
                        gross=Money(amount=abs(amount), currency="EUR"),
                        date=date,
                    )
                )
            else:  # silently ignore unknowns, or raise
                continue

        # One row per FinOp
        df = pd.DataFrame([r.model_dump() for r in records])
        df["__object__"] = records  # keep native object version beside flat cols
        return df