"""Public for fincli.processors"""
from .abstract import AbstractProcessor
from .saving_performance import SavingPerformanceProcessor
from .trading_performance import TradingPerformanceProcessor

__all__ = [
    "AbstractProcessor",
    "SavingPerformanceProcessor",
    "TradingPerformanceProcessor",
]
