from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel

from ..models import SavingPerformanceOut, TradingPerformanceOut
from .abstract import AbstractOutputPipe

class HtmlReportOutput(AbstractOutputPipe):
    """Simple, responsive HTML report (Bootstrap 5)."""

    def __init__(self, out_file: str = "report.html"):
        self.out_file = Path(out_file).expanduser().resolve()
        self.env = Environment(
            # point at the 'fincli.output' package and its 'templates' folder
            loader=PackageLoader("fincli.output", "templates"),
            autoescape=select_autoescape()
        )

    def render(self, *results: BaseModel) -> str:
        tpl = self.env.get_template("report.html")
        html = tpl.render(results=results)
        self.out_file.write_text(html, encoding="utf-8")
        return str(self.out_file)