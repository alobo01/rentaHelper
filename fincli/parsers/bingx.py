from __future__ import annotations
from pathlib import Path
from decimal import Decimal
import pandas as pd

from .abstract import AbstractParser
from ..models import (
    BingxParserConfig,
    Asset, Money,
    BuyOperation, SellOperation,
    FinOp,
)


EQUIVALENCES = {
    "USDT": "USD",
    "USDC": "USD",
}


class BingxParser(AbstractParser):
    config_model = BingxParserConfig

    def __init__(self, config: BingxParserConfig):
        super().__init__(config)

    def load(self) -> pd.DataFrame:
        """
        Load one or more Bingx CSVs, parse into FinOp objects:
          - 'Open Long'   → BuyOperation
          - 'Close Long'  → SellOperation
        """
        path = Path(self.config.path)
        files = (
            list(path.glob(self.config.glob))
            if path.is_dir()
            else [path]
        )

        

        records: list[FinOp] = []
        for f in files:
            df = pd.read_csv(
                f,
                sep=self.config.sep,
                encoding=self.config.encoding,
                parse_dates=["Time(UTC+8)"],
            )
            df = df.rename(columns={"Time(UTC+8)": "Time_UTC_8"})
            for row in df.itertuples(index=False):
                ts = row.Time_UTC_8
                base, quote = row.Pair.split("-", 1)
                asset = Asset(name=base, ticker=base, isin=None)
                price = Decimal(str(row.DealPrice))
                qty = Decimal(str(row.Quantity))
                fee = Decimal(str(row.Fee or 0))
                fee_coin = row._asdict().get("Fee Coin", "USDT")
                quote_currency = EQUIVALENCES.get(quote, quote)
                fee_currency = EQUIVALENCES.get(fee_coin, fee_coin)
                if row.Type == "Open Long":
                    records.append(
                        BuyOperation(
                            asset=asset,
                            unit_price=Money(amount=price, currency=quote_currency),
                            quantity=qty,
                            commission=Money(amount=fee, currency=fee_currency),
                            date=ts,
                        )
                    )
                elif row.Type == "Close Long" or row.Type == "Liquidation Long":
                    records.append(
                        SellOperation(
                            asset=asset,
                            unit_price=Money(amount=price, currency=quote_currency),
                            quantity=qty,
                            commission=Money(amount=fee, currency=fee_currency),
                            date=ts,
                        )
                    )
                # ignore other types for now


        # Convert to eur
        for record in records:
            if isinstance(record, (BuyOperation, SellOperation)):
                record.unit_price = record.unit_price.convert_to_eur(on=record.date)
                record.commission = record.commission.convert_to_eur(on=record.date)
        # build DataFrame of flat fields + keep objects
        df_out = pd.DataFrame([r.model_dump() for r in records])
        df_out["__object__"] = records
        return df_out
