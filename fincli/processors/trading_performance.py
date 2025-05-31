from collections import defaultdict, deque
from decimal import Decimal

import pandas as pd

from ..models import (
    Asset, TradingPerformanceIn, TradingPerformanceOut,
    BuyOperation, SellOperation, AssetTrade,
    Money, AssetPNL,
)
from .abstract import AbstractProcessor

# ──────────────────────────────────────────────────────────────────────────────
# Trading performance (FIFO net P/L per asset)
# ──────────────────────────────────────────────────────────────────────────────
class TradingPerformanceProcessor(AbstractProcessor):
    input_model = TradingPerformanceIn
    output_model = TradingPerformanceOut

    def __init__(self, year: int):
        self.year = year

    def process(self, data: TradingPerformanceIn) -> TradingPerformanceOut:
        # Buckets per asset: queue of unmatched BUY lots
        buys: dict[str, deque[BuyOperation]] = defaultdict(deque)
        # Map asset_key -> AssetPNL
        output: dict[str, AssetPNL] = defaultdict(
            lambda: AssetPNL(
                asset=Asset(name="Undefined", isin="UN0000000000", ticker="UN0000000000"),
                pnl=Money(amount=Decimal(0), currency="EUR"),
                trades=[],
                total_buy_eur=Decimal(0),
                total_sell_eur=Decimal(0),
            )
        )

        

        # Stream operations chronologically
        sorted_ops = sorted(data.operations, key=lambda o: (o.date, o.class__))
        for op in sorted_ops:
            if isinstance(op, BuyOperation):
                key = op.asset.isin or op.asset.name
                buys[key].append(op)

            elif isinstance(op, SellOperation) and op.date.year == self.year:
                asset_key = op.asset.isin or op.asset.name
                if asset_key=="Cardano":
                    print(f"Processing SellOperation for {asset_key} on {op.date}")
                qty_to_match = op.quantity

                # Ensure we have an entry for this key
                pnl_record = output[asset_key]
                if pnl_record.asset.isin == "UN0000000000":
                    # First time encountering this asset_key
                    pnl_record.asset = op.asset

                while qty_to_match > 0 and buys[asset_key]:
                    buy_lot = buys[asset_key][0]
                    match_qty = min(qty_to_match, buy_lot.quantity)

                    buy_px = buy_lot.unit_price.amount
                    sell_px = op.unit_price.amount
                    pnl_amount = (sell_px - buy_px) * match_qty - op.commission.amount

                    trade = AssetTrade(
                        buy=buy_lot,
                        sell=op,
                        pnl=Money(amount=pnl_amount, currency="EUR"),
                    )

                    # Register the trade
                    pnl_record.trades.append(trade)
                    pnl_record.pnl.amount += pnl_amount


                    # **accumulate gross buy/sell**
                    pnl_record.total_buy_eur += buy_px * match_qty
                    pnl_record.total_sell_eur += sell_px * match_qty

                    # Update remaining quantities
                    buy_lot.quantity -= match_qty
                    qty_to_match -= match_qty
                    if buy_lot.quantity == 0:
                        buys[asset_key].popleft()


        # Build per-ticker totals
        summary_by_ticker: dict[str, dict[str, Decimal]] = defaultdict(lambda: {
            "realized_pnl": Decimal(0),
            "matched_qty": Decimal(0),
            "unmatched_qty": Decimal(0),
            "trade_count": 0
        })

        # 1) Aggregate realized P&L and matched quantities
        for asset_pnl in output.values():           # output is your dict[str,AssetPNL]
            t = asset_pnl.asset.ticker
            rec = summary_by_ticker[t]
            rec["realized_pnl"] += asset_pnl.pnl.amount
            rec["trade_count"] = len(asset_pnl.trades)
            # Sum up how many units were matched (from the sell side)
            rec["matched_qty"] += sum(trade.sell.quantity for trade in asset_pnl.trades)
            for t in asset_pnl.trades:
                if pd.isnull(t.buy.date):
                    print(t.buy)


        # 2) Tally up any remaining open buys
        for t, queue in buys.items():
            rec = summary_by_ticker[t]
            rec["unmatched_qty"] = sum(lot.quantity for lot in queue)

        # 3) (Optional) Convert your defaultdict back to a plain dict
        final_summary = dict(summary_by_ticker)

        # Print the final summary
        for ticker, stats in final_summary.items():
            if stats['unmatched_qty']>0:
                print(f"{ticker} | "
                    f"Realized P&L: {stats['realized_pnl']:8.2f} EUR | "
                    f"Matched Qty: {stats['matched_qty']:6}   | "
                    f"Unmatched Qty: {stats['unmatched_qty']:6}   | "
                    f"Trades: {stats['trade_count']}")

        return TradingPerformanceOut(
            year=self.year,
            summary=list(output.values()),
        )