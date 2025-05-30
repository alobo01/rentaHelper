from __future__ import annotations
from pathlib import Path
from decimal import Decimal
import pandas as pd

from .abstract import AbstractParser
from ..models import (
    BitGetParserConfig,
    Asset, Money,
    BuyOperation, SellOperation, FinOp,
)

EQUIVALENCES = {
    "USDT": "USD",
    "USDC": "USD",
}

def _to_decimal(val) -> Decimal:
    try:
        return Decimal(str(val))
    except:
        return Decimal(0)

class BitGetParser(AbstractParser):
    """
    Parses BitGet CSV exports in two formats:
      Format A (semicolon):
        Date;Direction;Coin;Futures;Transaction amount;Average Price;Realized P/L;NetProfits;Fee
      Format B (semicolon):
        Date;Trading pair;Direction;Price;Amount;Total;Fee
    """
    config_model = BitGetParserConfig

    def __init__(self, config: BitGetParserConfig):
        super().__init__(config)

    def load(self) -> pd.DataFrame:
        records: list[FinOp] = []
        p = Path(self.config.path)
        files = [p] if p.is_file() else list(p.glob(self.config.glob))

        for f in files:
            df = pd.read_csv(f, sep=self.config.sep, encoding=self.config.encoding, parse_dates=[0])
            
            df.columns = [str(c).replace(" ", "_").replace("(","").replace(")","") for c in df.columns]
            cols = df.columns.tolist()
            # Format A
            if {"Direction","Coin","Futures","Transaction_amount","Average_Price","Fee"}.issubset(cols):
                
                for row in df.itertuples(index=False):
                    d = row._asdict()
                    dt = d["Date"]
                    direction = d["Direction"].lower()
                    coin = d["Coin"]
                    pair = d["Futures"]
                    amt = _to_decimal(d["Transaction_amount"])
                    price = _to_decimal(d["Average_Price"])
                    fee  = _to_decimal(d["Fee"])

                    base = coin
                    base_currency = EQUIVALENCES.get(base, base)
                    
                    asset = Asset(name=pair.replace(base,""), ticker=pair.replace(base,""))
                    unit_price = Money(amount=price, currency=base_currency)
                    commission = Money(amount=fee, currency=base_currency)

                    if "open" in direction:
                        records.append(
                            BuyOperation(
                                asset=asset,
                                unit_price=unit_price,
                                quantity=amt,
                                commission=commission,
                                date=dt,
                            )
                        )
                    elif "close" in direction or "liquidation" in direction:
                        records.append(
                            SellOperation(
                                asset=asset,
                                unit_price=unit_price,
                                quantity=amt,
                                commission=commission,
                                date=dt,
                            )
                        )

            # Format B
            elif {"Trading_pair","Direction","Price","Amount","Fee"}.issubset(cols):
                for row in df.itertuples(index=False):
                    d = row._asdict()
                    dt = d["Date"]
                    pair = d["Trading_pair"]
                    direction = d["Direction"].lower()
                    price = _to_decimal(d["Price"])
                    amt   = _to_decimal(d["Amount"])
                    fee   = _to_decimal(d["Fee"])

                    # Handle currency equivalences
                    if "/" in pair:
                        base, quote = pair.split("/", 1)
                    else:
                        base, quote = pair[:3], pair[3:]
                    
                    quote_currency = EQUIVALENCES.get(quote, quote)

                    asset = Asset(name=base, ticker=base)
                    unit_price = Money(amount=price, currency=quote_currency)
                    commission = Money(amount=fee, currency=quote_currency)

                    if direction == "buy":
                        records.append(
                            BuyOperation(
                                asset=asset,
                                unit_price=unit_price,
                                quantity=amt,
                                commission=commission,
                                date=dt,
                            )
                        )
                    elif direction == "sell":
                        records.append(
                            SellOperation(
                                asset=asset,
                                unit_price=unit_price,
                                quantity=amt,
                                commission=commission,
                                date=dt,
                            )
                        )

            # else: skip unknown

        df_out = pd.DataFrame([r.model_dump() for r in records])
        df_out["__object__"] = records
        return df_out

