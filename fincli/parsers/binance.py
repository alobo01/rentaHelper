from __future__ import annotations
from pathlib import Path
from decimal import Decimal
import pandas as pd

from .abstract import AbstractParser
from ..models import (
    BinanceParserConfig,
    Asset, Money,
    BuyOperation, SellOperation, Dividend, Interest, AssetTrade, FinOp,
)


class BinanceParser(AbstractParser):
    """
    Parses Binance CSV exports:
      - trades CSV: realized gains and cost basis
      - savings CSV: reward/interest receives
    """
    config_model = BinanceParserConfig

    def __init__(self, config: BinanceParserConfig):
        super().__init__(config)

    def _load_files(self, path: str, trades=True) -> list[pd.DataFrame]:
        p = Path(path)
        files = [p] if p.is_file() else list(p.glob(self.config.glob))
        dfs = []
        for f in files:
            dfs.append(pd.read_csv(f, sep=self.config.sep, encoding=self.config.encoding, 
                                   parse_dates=["Acquired", "Sold"] if trades else ["Date"],))
        return dfs

    def load(self) -> pd.DataFrame:
        records: list[FinOp] = []
        # --- Trades ---
        trades_dfs = self._load_files(self.config.trades_path)
        for df in trades_dfs:
            df.columns = [str(c).replace(" ", "_").replace("(","").replace(")","") for c in df.columns]
            for row in df.itertuples(index=False):
                # fields from header:
                # Currency name,Currency amount,Acquired,Sold,Proceeds (EUR),Cost basis (EUR),Gains (EUR),Holding period (Days),Transaction type,Label
                base = row._asdict()["Currency_name"]
                amt = Decimal(str(row._asdict()["Currency_amount"]))
                acquired = row._asdict()["Acquired"]
                sold = row._asdict()["Sold"]
                proceeds = Decimal(str(row._asdict()["Proceeds_EUR"] or 0))
                cost = Decimal(str(row._asdict()["Cost_basis_EUR"] or 0))
                gains = Decimal(str(row._asdict()["Gains_EUR"] or 0))
                asset = Asset(name=base, ticker=base)

                # build buy/sell pair
                buy = BuyOperation(
                    asset=asset,
                    unit_price=Money(amount=(cost / amt) if amt else Decimal(0), currency="EUR"),
                    quantity=amt,
                    commission=None,
                    date=acquired,
                )
                sell = SellOperation(
                    asset=asset,
                    unit_price=Money(amount=(proceeds / amt) if amt else Decimal(0), currency="EUR"),
                    quantity=amt,
                    commission=None,
                    date=sold,
                )
                records+= [
                    buy,sell
                ]
        # --- Savings (rewards) ---
        savings_dfs = self._load_files(self.config.savings_path, trades=False)
        for df in savings_dfs:
            df.columns = [str(c).replace(" ", "_").replace("(","").replace(")","") for c in df.columns]
            for row in df.itertuples(index=False):
                # Date,Asset,Amount,Price per unit (EUR),Value (EUR),Transaction Type,Label
                date = row._asdict()["Date"]
                symbol = row._asdict()["Asset"]
                amt = Decimal(str(row._asdict()["Amount"]))
                value = Decimal(str(row._asdict()["Value_EUR"] or 0))
                asset = Asset(name=symbol, ticker=symbol)
                # treat as dividend
                records.append(
                    Dividend(asset=asset, gross=Money(amount=value, currency="EUR"), date=date, source="Binance")
                )

        # assemble DataFrame
        df_out = pd.DataFrame([r.model_dump() for r in records])
        df_out["__object__"] = records
        return df_out
