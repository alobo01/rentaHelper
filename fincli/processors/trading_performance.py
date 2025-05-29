from collections import defaultdict, deque
from decimal import Decimal

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
                trades=[]
            )
        )

        # Stream operations chronologically
        sorted_ops = sorted(data.operations, key=lambda o: o.date)
        for op in sorted_ops:
            if isinstance(op, BuyOperation):
                key = op.asset.isin or op.asset.name
                buys[key].append(op)

            elif isinstance(op, SellOperation) and op.date.year == self.year:
                asset_key = op.asset.isin or op.asset.name
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
                    pnl_amount = (sell_px - buy_px) * match_qty

                    trade = AssetTrade(
                        buy=buy_lot,
                        sell=op,
                        pnl=Money(amount=pnl_amount, currency="EUR"),
                    )

                    # Register the trade
                    pnl_record.trades.append(trade)
                    pnl_record.pnl.amount += pnl_amount

                    # Update remaining quantities
                    buy_lot.quantity -= match_qty
                    qty_to_match -= match_qty
                    if buy_lot.quantity == 0:
                        buys[asset_key].popleft()

        return TradingPerformanceOut(
            year=self.year,
            summary=list(output.values()),
        )