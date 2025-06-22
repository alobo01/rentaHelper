"""Public façade for fincli.output"""
from .abstract import AbstractOutputPipe
from .html_report import HtmlReportOutput
from .pdf_report import PdfReportOutput

__all__ = ["AbstractOutputPipe", "HtmlReportOutput", "PdfReportOutput"]
