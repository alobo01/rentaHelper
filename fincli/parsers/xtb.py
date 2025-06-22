from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict, List
import pandas as pd

from .abstract import AbstractParser
from ..models import (
    XTBParserConfig,
    Asset, Money,
    BuyOperation, SellOperation, Dividend, Interest, AssetTrade, FinOp, ZERO_EUR
)

# Helpers --------------------------------------------------------------------
def _dec(euro_str: str) -> Decimal:
    """'1.234,56' or '0,6'  →  Decimal('1234.56') / Decimal('0.6')"""
    return Decimal(euro_str.replace(".", "").replace(",", "."))

def _parse_dt(date_str: str, fmt: str) -> datetime:
    return datetime.strptime(date_str, fmt)


def group_within_threshold(lines, threshold_seconds=10, sep=";"):
    """
    Iterate over (timestamp‐sorted) lines and assign a “group key” such 
    that any two consecutive entries within threshold_seconds land in the same group.
    """

    # First, parse everything (and sort by dt upfront)
    parsed = []
    for line in lines:
        parts = line.split(sep)
        _, typ, raw_time, comment, symbol, raw_amount, *_ = parts
        dt = datetime.strptime(raw_time, "%d/%m/%Y %H:%M:%S")
        parsed.append((dt, typ.strip(), comment.strip(), symbol.strip(), _dec(raw_amount.strip())))
    parsed.sort(key=lambda tup: tup[0])

    grouped = {}
    if not parsed:
        return grouped

    # Use the first dt as the “anchor” for group 1
    current_group_key = parsed[0][0]  # you could also store an integer index
    grouped[current_group_key] = [{
        "type": parsed[0][1],
        "amount": parsed[0][4],
        "desc": parsed[0][2],
        "symbol": parsed[0][3],
    }]

    last_dt = parsed[0][0]

    for dt, typ, comment, symbol, amount in parsed[1:]:
        # If this entry is ≤ threshold_seconds away from the LAST entry, 
        # put it in the same group; otherwise start a new group.
        if (dt - last_dt).total_seconds() <= threshold_seconds:
            grouped[current_group_key].append({
                "type": typ,
                "amount": amount,
                "desc": comment,
                "symbol": symbol,
            })
        else:
            # start a fresh group anchored at this dt
            current_group_key = dt
            grouped[current_group_key] = [{
                "type": typ,
                "amount": amount,
                "desc": comment,
                "symbol": symbol,
            }]
        last_dt = dt

    return grouped

class XTBParser(AbstractParser):
    """Parses XTB cashOperations & tradeOperations CSVs."""
    config_model = XTBParserConfig

    def __init__(self, config: XTBParserConfig):
        super().__init__(config)

    # --------------------------------------------------------------------- #
    # CASH OPERATIONS  ->  Interest / Dividend (and their taxes)
    # --------------------------------------------------------------------- #
    def _parse_cash(self, file: Path) -> list[FinOp]:
        """
        Parse XTB cashOperations.csv, grouping “Free-funds Interest” and their matching
        “Free-funds Interest Tax” rows into single Interest records, and any Dividend entries.
        """
        # Read all lines
        text = file.read_text(encoding=self.config.encoding)
        lines = [line for line in text.splitlines() if line.strip()]
        # Skip header
        data_lines = lines[1:]

        # Temporary grouping: key by (date)
        grouped = group_within_threshold(data_lines, threshold_seconds=10, sep=self.config.sep)

            

        # Build FinOp records
        records: list[FinOp] = []
        types_set = {
            y["type"]
            for x in grouped.values()
            for y in x
        }
        Interest_types = {"Free-funds Interest", "Free-funds Interest Tax"}
        Dividend_types = {"DIVIDENT", "Withholding Tax"}
        Important_types = Interest_types | Dividend_types
        # print(types_set)
        for date, entry_list in grouped.items():
            # 1) Skip if there are no interest/dividend entries at all
            if all(x["type"] not in Important_types for x in entry_list):
                continue

            # 2) First, handle Interest:
            gross_interest = sum(
                x["amount"] 
                for x in entry_list 
                if x["type"] in Interest_types and "Tax" not in x["type"]            )
            tax_interest = abs(sum(
                x["amount"] 
                for x in entry_list 
                if x["type"] in Interest_types and "Tax" in x["type"]
            ))
            if gross_interest > 0:
                records.append(
                    Interest(
                        gross=Money(amount=gross_interest, currency="EUR"),
                        tax=Money(amount=tax_interest, currency="EUR"),
                        date=date,
                        source="XTB",
                    )
                )

            # 3) Now build one Dividend instance per symbol on this date:
            #    - collect all “dividend‐type” entries in a per‐symbol bucket
            dividends_by_symbol: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for x in entry_list:
                if x["type"] in Dividend_types:
                    dividends_by_symbol[x["symbol"]].append(x)

            # 4) For each symbol, sum gross and tax separately:
            for symbol, div_entries in dividends_by_symbol.items():
                # Sum gross dividend amounts for THIS symbol (exclude any "Tax" entries)
                gross_div = sum(x["amount"] for x in div_entries if "Tax" not in x["type"])
                # Sum tax entries for THIS symbol (any “Dividend‐type” where type contains "Tax")
                tax_div = sum(x["amount"] for x in div_entries if "Tax" in x["type"])

                if gross_div > 0:
                    asset = Asset(
                        name=symbol,      # you could substitute a lookup if you have a nicer name
                        isin=None,        # XTB does not provide ISINs
                        ticker=symbol     # symbol is the ticker in your existing code
                    )
                    records.append(
                        Dividend(
                            asset=asset,
                            gross=Money(amount=gross_div, currency="EUR"),
                            tax=Money(amount=tax_div, currency="EUR"),
                            date=date,
                            source="XTB",
                        )
                    )

        return records

    # --------------------------------------------------------------------- #
    # TRADE OPERATIONS  ->  AssetTrade (Buy + Sell bundled)
    # --------------------------------------------------------------------- #
    def _parse_trades(self, file: Path) -> list[FinOp]:
        # Read raw lines
        lines = file.read_text(encoding=self.config.encoding).splitlines()
        if len(lines) < 3:
            return []

        # First two header lines
        hdr1 = lines[0].split(self.config.sep)
        hdr2 = lines[1].split(self.config.sep)

        # Build combined column names
        cols = []
        prev_c1 = ""
        for c1, c2 in zip(hdr1, hdr2):
            c1 = c1.strip()
            if len(c1) == 0:
                c1 = prev_c1 
            c2 = c2.strip()
            if c2:
                cols.append(f"{c1}_{c2}")
            else:
                cols.append(c1)
            prev_c1 = c1

        # The remainder lines → data
        data_lines = lines[2:]
        df = pd.read_csv(
            pd.io.common.StringIO("\n".join([";".join(cols)] + data_lines)),
            sep=self.config.sep,
            encoding=self.config.encoding,
        )
        # Clean up DataFrame
        # Remove empty rows
        df = df.dropna(how='all')


        df.columns = [c.strip().replace(" ","_").replace("(","").replace(")","") for c in df.columns]  # Clean column names

        records: list[FinOp] = []
        for row in df.itertuples(index=False):
            t = row._asdict()
            if all(map(pd.isna, t.values())):
                continue

            # Basic fields
            name   = t["Nombre"]
            isin   = t["ISIN"]
            ticker = t["Ticker"]
            vol    = _dec(t["Volumen"].replace(" ", ""))

            # Buy side fields
            buy_dt    = _parse_dt(t["Compra_Fecha"], "%d/%m/%Y")
            buy_amt   = _dec(t["Compra_Importe_transacción_EUR"])
            unit_buy  = buy_amt / vol if vol else Decimal(0)

            # Sell side fields
            sell_dt   = _parse_dt(t["Venta_Fecha"], "%d/%m/%Y")
            sell_amt  = _dec(t["Venta_Importe_transacción_EUR"])
            unit_sell = sell_amt / vol if vol else Decimal(0)

            # Tax & commissions
            comm = _dec(t.get("Comisión_transacción__EUR", "0"))
            rollover = _dec(t.get("Rollovers_EUR", "0"))
            swaps = _dec(t.get("Swaps_EUR", "0"))

            total_comm = comm + abs(rollover) + abs(swaps)

            tax  = _dec(t.get("Impuesto_sobre_transacciones_financieras_o_similares_EUR", "0"))
            operation_direction = t.get("Posición", "Alcista").strip()
            if operation_direction == "Bajista":
                # We swap dates for compatibility with existing code
                # (where buy_dt is always before sell_dt)
                buy_dt, sell_dt = sell_dt, buy_dt
            # Build ops
            buy_op = BuyOperation(
                asset=Asset(name=name, isin=isin if not pd.isna(isin) else None, ticker=ticker),
                unit_price=Money(amount=unit_buy, currency="EUR"),
                quantity=vol,
                commission=ZERO_EUR,
                tax=ZERO_EUR,
                date=buy_dt
            )
            sell_op = SellOperation(
                asset=buy_op.asset,
                unit_price=Money(amount=unit_sell, currency="EUR"),
                quantity=vol,
                commission=Money(amount=total_comm, currency="EUR"),
                tax=Money(amount=tax, currency="EUR"),
                date=sell_dt
            )

            pnl = _dec(t["Resultado_neto_EUR"])
            if abs(pnl-(sell_op.unit_price.amount*sell_op.quantity-buy_op.unit_price.amount*buy_op.quantity - total_comm))> 0.01:
                raise ValueError(f"Unexpected PnL: {pnl} != {sell_op.unit_price.amount*vol - buy_op.unit_price.amount*vol}") 
            records +=[
                buy_op, sell_op
            ]
            # records.append(
            #     AssetTrade(buy=buy_op, sell=sell_op, pnl=Money(amount=pnl, currency="EUR"), tax=sell_op.tax)
            # )

        return records

    # --------------------------------------------------------------------- #
    # public API
    # --------------------------------------------------------------------- #
    def load(self) -> pd.DataFrame:
        cash_recs   = self._parse_cash(Path(self.config.cash_file))
        trade_recs  = self._parse_trades(Path(self.config.trades_file))

        records = cash_recs + trade_recs
        df = pd.DataFrame([r.model_dump() for r in records])
        df["__object__"] = records
        return df