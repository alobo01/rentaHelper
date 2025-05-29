"""Public façade for fincli.output"""
from .abstract import AbstractOutputPipe
from .html_report import HtmlReportOutput

__all__ = ["AbstractOutputPipe", "HtmlReportOutput"]
