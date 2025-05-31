from __future__ import annotations
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Any
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

        # Temporary grouping: key by (date, cleaned_description)
        grouped: dict[tuple[datetime, str], dict[str, Any]] = {}
        for line in data_lines:
            parts = line.split(self.config.sep)
            # CSV columns: ID;Type;Time;Comment;Symbol;Amount;
            _, typ, raw_time, comment, symbol, raw_amount, *_ = parts
            # Parse datetime
            dt = datetime.strptime(raw_time, "%d/%m/%Y %H:%M:%S")
            # Normalize description: use comment without trailing tax indicator
            desc = comment.strip()
            base_desc = desc.replace(" Tax", "").strip()
            key = (dt, base_desc)

            # Parse amount, converting comma-decimals
            amt = Decimal(raw_amount.replace(",", "."))
            
            entry = grouped.setdefault(key, {
                "date": dt,
                "asset": Asset(name=symbol) if symbol else None,
                "gross": Decimal(0),
                "tax": Decimal(0),
                "source": base_desc
            })

            # Accumulate
            if "Interest" in typ and "Tax" not in typ:
                entry["gross"] += amt
            elif "Interest Tax" in typ or "Withholding Tax" in typ:
                entry["tax"] += abs(amt)
            elif "Dividend" in typ or "Divident" in typ:
                entry["gross"] += amt
                # dividends may also have tax lines; handled above
            # else: ignore other types

        # Build FinOp records
        records: list[FinOp] = []
        for entry in grouped.values():
            if "Interest" in entry["source"]:
                records.append(
                    Interest(
                        gross=Money(amount=entry["gross"], currency="EUR"),
                        tax=Money(amount=entry["tax"], currency="EUR"),
                        date=entry["date"],
                        source=entry["source"],
                    )
                )
            elif "Dividend" in entry["source"] or "Divident" in entry["source"]:
                # treat as Dividend
                records.append(
                    Dividend(
                        asset=entry["asset"],
                        gross=Money(amount=entry["gross"], currency="EUR"),
                        tax=Money(amount=entry["tax"], currency="EUR"),
                        date=entry["date"],
                        source=entry["source"],
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
                quantity=vol-(total_comm/unit_sell),
                commission=Money(amount=comm, currency="EUR"),
                tax=Money(amount=tax, currency="EUR"),
                date=sell_dt
            )

            pnl = _dec(t["Resultado_neto_EUR"])
            if abs(pnl-(sell_op.unit_price.amount*sell_op.quantity-buy_op.unit_price.amount*buy_op.quantity))> 0.01:
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