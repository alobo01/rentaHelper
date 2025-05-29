# file: fincli/fx.py
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from decimal import Decimal
from datetime import datetime

import pandas as pd


@lru_cache
def fx_table(csv_path: str | Path) -> pd.DataFrame:
    """Load the ECB historical reference rates and return *daily* dataframe."""
    df = pd.read_csv(csv_path, parse_dates=["Date"]).set_index("Date").sort_index()
    df.columns = [c.strip() for c in df.columns]  # e.g. 'USD', 'JPY'
    # convert index from Timestamps to date objects
    df.index = df.index.date
    df.columns = [c.strip() for c in df.columns]
    return df


def eur_to(currency: str, amount: Decimal, on: datetime, csv_path: str | Path) -> Decimal:
    """Convert EUR → <currency> at date `on`.  Fallback to previous known day."""
    tbl = fx_table(csv_path)
    day = on
    while day not in tbl.index:                # weekends / holidays
        day = day - pd.Timedelta(days=1)
    rate = Decimal(str(tbl.loc[day, currency]))
    return amount * rate

def to_eur(currency: str, amount: Decimal, on: datetime, csv_path: str | Path) -> Decimal:
    """Convert <currency> → EUR at date `on`.  Fallback to previous known day."""
    tbl = fx_table(csv_path)
    day = on.date()  # ensure we are working with date only
    while day not in tbl.index:                # weekends / holidays
        day = day - pd.Timedelta(days=1)
    rate = Decimal(str(tbl.loc[day, currency]))
    return amount / rate