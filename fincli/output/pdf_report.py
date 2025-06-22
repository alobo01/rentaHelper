# file: fincli/output/pdf_report.py
from __future__ import annotations
import datetime as dt # Renamed to dt to avoid conflict with models.datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Literal, Annotated, Any, Union

from abc import ABC, abstractmethod # Added for AbstractOutputPipe

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, BaseDocTemplate, KeepInFrame
)
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from .abstract import AbstractOutputPipe
from ..models import *
from pandas._libs.tslibs.nattype import NaTType  # Add this import at the top if pandas is used

# --- Color Palette ---
PRIMARY_COLOR = colors.HexColor("#1A5276")
SECONDARY_COLOR = colors.HexColor("#2980B9")
TEXT_COLOR = colors.HexColor("#34495E")
LIGHT_GREY = colors.HexColor("#F4F6F6")
MID_GREY = colors.HexColor("#D5DBDB")
BORDER_COLOR = colors.HexColor("#AAB7B8")
WHITE = colors.white
POSITIVE_COLOR = colors.HexColor("#27AE60")
NEGATIVE_COLOR = colors.HexColor("#C0392B")


class PdfReportOutput(AbstractOutputPipe):
    """Generates a visually appealing PDF tax report using ReportLab."""

    def __init__(self,
                 out_file: str = "report.pdf",
                 report_main_title: str = "Financial Tax Report",
                 author_name: str = "FinCLI Financial Reporting",
                 report_period: str | None = None):
        self.out_file = Path(out_file).expanduser().resolve()
        self.report_main_title = report_main_title
        self.author_name = author_name
        self.report_period = report_period

        self.styles = getSampleStyleSheet()
        self.page_width, self.page_height = A4
        
        self.left_margin = 1.8 * cm
        self.right_margin = 1.8 * cm
        self.top_margin = 2.5 * cm
        self.bottom_margin = 2.0 * cm
        
        self.content_width = self.page_width - self.left_margin - self.right_margin

        self._define_styles()
        self.elements: list = []

    def _define_styles(self): 
        self.styles.add(ParagraphStyle(
            name="ReportTitle", fontSize=26, leading=32, spaceAfter=10,
            textColor=PRIMARY_COLOR, fontName="Helvetica-Bold", alignment=TA_CENTER
        ))
        self.styles.add(ParagraphStyle(
            name="ReportSubTitle", fontSize=14, leading=18, spaceAfter=20,
            textColor=SECONDARY_COLOR, alignment=TA_CENTER, fontName="Helvetica"
        ))
        self.styles.add(ParagraphStyle(
            name="H1", fontSize=20, leading=24, spaceBefore=12, spaceAfter=8,
            textColor=PRIMARY_COLOR, fontName="Helvetica-Bold", keepWithNext=1
        ))
        self.styles.add(ParagraphStyle(
            name="H2", fontSize=16, leading=20, spaceBefore=10, spaceAfter=6,
            textColor=PRIMARY_COLOR, fontName="Helvetica-Bold", keepWithNext=1
        ))
        self.styles.add(ParagraphStyle(
            name="H3", fontSize=13, leading=16, spaceBefore=8, spaceAfter=4,
            textColor=TEXT_COLOR, fontName="Helvetica-Bold", keepWithNext=1
        ))
        normal_style = self.styles['Normal']
        normal_style.textColor = TEXT_COLOR; normal_style.fontSize = 10
        normal_style.leading = 12; normal_style.spaceBefore = 2; normal_style.spaceAfter = 2
        
        self.styles.add(ParagraphStyle(name="NormalBold", parent=self.styles["Normal"], fontName="Helvetica-Bold"))
        
        self.styles.add(ParagraphStyle(name="SmallText", parent=self.styles["Normal"], fontSize=8.5, leading=10, textColor=colors.HexColor("#566573")))
        self.styles.add(ParagraphStyle(name="SmallTextBold", parent=self.styles["SmallText"], fontName="Helvetica-Bold"))
        self.styles.add(ParagraphStyle(name="SmallTextBoldRight", parent=self.styles["SmallTextBold"], alignment=TA_RIGHT))


        self.styles.add(ParagraphStyle(name="RightAlign", parent=self.styles["Normal"], alignment=TA_RIGHT))
        
        self.styles.add(ParagraphStyle(name="TableHeader", parent=self.styles["NormalBold"], textColor=WHITE, alignment=TA_CENTER, fontSize=9))
        
        self.styles.add(ParagraphStyle(name="TableCell", parent=self.styles["Normal"], alignment=TA_LEFT, fontSize=9))
        self.styles.add(ParagraphStyle(name="TableCellRight", parent=self.styles["TableCell"], alignment=TA_RIGHT))
        
        self.styles.add(ParagraphStyle(name="TableCellSmall", parent=self.styles["SmallText"], alignment=TA_LEFT))
        self.styles.add(ParagraphStyle(name="TableCellSmallRight", parent=self.styles["TableCellSmall"], alignment=TA_RIGHT))
        
        self.styles.add(ParagraphStyle(name="PositivePnl", parent=self.styles["TableCellSmallRight"], textColor=POSITIVE_COLOR, fontName="Helvetica-Bold"))
        self.styles.add(ParagraphStyle(name="NegativePnl", parent=self.styles["TableCellSmallRight"], textColor=NEGATIVE_COLOR, fontName="Helvetica-Bold"))

    def _header_footer(self, canvas, doc: BaseDocTemplate): 
        canvas.saveState()
        footer_text = f"Page {doc.page} | {self.report_main_title}"
        canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.grey)
        canvas.drawRightString(self.page_width - self.right_margin, 1.2*cm, footer_text)
        generated_text = f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" 
        canvas.drawString(self.left_margin, 1.2*cm, generated_text)
        canvas.restoreState()

    def _get_safe_float(self, value: Money | Decimal | float | None, default_val: float = 0.0) -> float:
        if isinstance(value, Money):
            return float(value.amount)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (float, int)):
            return float(value)
        return default_val

    def _format_money(self, money_obj: Money | None, default_str: str = "N/A") -> str:
        if isinstance(money_obj, Money):
            return str(money_obj) 
        return default_str
    
    def _format_decimal(self, dec_val: Decimal | None, precision: int = 2, default_str: str = "N/A") -> str:
        if isinstance(dec_val, Decimal):
            return f"{dec_val:,.{precision}f}"
        return default_str

    def _add_cover_page(self): 
        self.elements.append(Spacer(1, self.page_height / 5))
        self.elements.append(Paragraph(self.report_main_title, self.styles["ReportTitle"]))
        if self.report_period:
            self.elements.append(Paragraph(f"For the Period: {self.report_period}", self.styles["ReportSubTitle"]))
        self.elements.append(Paragraph(f"Prepared by: {self.author_name}", self.styles["ReportSubTitle"]))
        self.elements.append(Spacer(1, 1*cm))
        current_date_str = dt.datetime.now().strftime('%B %d, %Y') 
        self.elements.append(Paragraph(f"Report Date: {current_date_str}", self.styles["Normal"]))
        self.elements.append(PageBreak())

    def _build_summary_table(self, data: list[list[Any]], col_widths: list[float]): 
        processed_data = []
        for row_idx, row in enumerate(data):
            processed_row = []
            for cell_idx, cell_content in enumerate(row):
                if not isinstance(cell_content, (Paragraph, Spacer, Table, KeepInFrame)):
                    style_to_use = self.styles["TableCell"] # Default for data cells
                    if row_idx == 0: # Header row
                        style_to_use = self.styles["TableHeader"]
                    elif cell_idx == 1 : # Amount column (index 1) in data rows
                         style_to_use = self.styles["TableCellRight"]
                    # First column of data rows can be bold if needed:
                    # elif cell_idx == 0 and row_idx > 0: style_to_use = self.styles["NormalBold"]
                    
                    processed_row.append(Paragraph(str(cell_content) if cell_content is not None else "", style_to_use))
                else: # cell_content is already a Flowable (e.g. Spacer)
                    processed_row.append(cell_content)
            processed_data.append(processed_row)
        
        table = Table(processed_data, colWidths=col_widths, hAlign='LEFT')
        style_cmds = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR), # Header background
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ]
        # Alternating row colors for data rows
        for i_row in range(1, len(processed_data)): # Start from 1 for data rows
            if i_row % 2 == 1: # Odd data rows (1st, 3rd, etc. data row)
                 if not isinstance(processed_data[i_row][0], Spacer): # Don't color spacer rows
                    style_cmds.append(('BACKGROUND', (0, i_row), (-1, i_row), LIGHT_GREY))
        
        table.setStyle(TableStyle(style_cmds))
        self.elements.append(table)
        self.elements.append(Spacer(1, 1*cm))

    def _add_overall_summary(self, savings_data: SavingPerformanceOut | None, trading_data: TradingPerformanceOut | None):
        self.elements.append(Paragraph("Overall Financial Summary", self.styles["H1"]))
        summary_rows_data = [["Category", "Amount (EUR)"]] 
        has_data = False

        if savings_data:
            has_data = True
            total_gross_income = savings_data.total_eur 
            total_passive_tax_decimal = Decimal(0)
            for op in savings_data.records:
                if isinstance(op, (Interest, Dividend)) and op.tax: # Ensure op.tax is Money
                    total_passive_tax_decimal += op.tax.amount
            
            net_passive_income = total_gross_income - total_passive_tax_decimal

            summary_rows_data.extend([
                ["Total Gross Passive Income", f"{total_gross_income:,.2f}"],
                ["Total Withholding Tax (Passive)", f"{total_passive_tax_decimal:,.2f}"],
                ["Net Passive Income", f"{net_passive_income:,.2f}"],
            ])

        if trading_data:
            has_data = True
            total_net_realized_pnl_dec = Decimal(0)
            total_trading_commissions_dec = Decimal(0)
            total_transaction_taxes_dec = Decimal(0)

            for asset_pnl in trading_data.summary:
                total_net_realized_pnl_dec += asset_pnl.pnl.amount # Assuming pnl is EUR and Money
                for trade in asset_pnl.trades:
                    if trade.sell.commission: # Ensure is Money
                         total_trading_commissions_dec += trade.sell.commission.amount 
                    if trade.sell.tax: # Ensure is Money
                         total_transaction_taxes_dec += trade.sell.tax.amount 
            
            if savings_data and summary_rows_data and not isinstance(summary_rows_data[-1][0], Spacer):
                 summary_rows_data.append([Spacer(0,0.2*cm), Spacer(0,0.2*cm)])
            
            summary_rows_data.extend([
                ["Net Realized P/L (Trading)", f"{total_net_realized_pnl_dec:,.2f}"],
                ["Total Trading Commissions", f"{total_trading_commissions_dec:,.2f}"],
                ["Total Trading Transaction Taxes", f"{total_transaction_taxes_dec:,.2f}"],
            ])
        
        if has_data:
            col_widths = [self.content_width * 0.65, self.content_width * 0.35]
            self._build_summary_table(summary_rows_data, col_widths) 
        else:
            self.elements.append(Paragraph("No financial data available for summary.", self.styles["Normal"]))
        self.elements.append(PageBreak())

    def _add_passive_income_details(self, savings: SavingPerformanceOut):
        title = "Passive Income Details"
        if savings.year and (not self.report_period or str(savings.year) not in self.report_period):
            title += f" ({savings.year})"
        self.elements.append(Paragraph(title, self.styles["H1"]))
        
        tbl_header = [
            Paragraph("Date", self.styles["TableHeader"]), Paragraph("Source/Asset", self.styles["TableHeader"]),
            Paragraph("Type", self.styles["TableHeader"]),
            Paragraph("Gross", self.styles["TableHeader"]), Paragraph("Tax Paid", self.styles["TableHeader"]),
            Paragraph("Net", self.styles["TableHeader"]),
        ]
        tbl_data = [tbl_header]

        for op in savings.records:
            if not isinstance(op, (Interest, Dividend)):
                continue 
            
            gross_amount = op.gross.amount
            tax_amount = op.tax.amount if op.tax else Decimal(0)
            net_amount = gross_amount - tax_amount
            
            op_source_name = "N/A"
            if isinstance(op, Interest):
                op_source_name = op.source or "Unknown Interest Source"
                op_type_str = "Interest"
            elif isinstance(op, Dividend):
                op_source_name = op.asset.name + (f" ({op.asset.ticker})" if op.asset.ticker else "")
                if op.source: # Append dividend source if available
                    op_source_name += f" via {op.source}"
                op_type_str = "Dividend"
            else: 
                op_source_name = "Unknown Operation" # Should not happen with the guard clause
                op_type_str = op.class__

            tbl_data.append([
                Paragraph(op.date.date().strftime('%Y-%m-%d'), self.styles["TableCellSmall"]),
                Paragraph(op_source_name, self.styles["TableCellSmall"]), # Potentially long, ensure width is adequate
                Paragraph(op_type_str, self.styles["TableCellSmall"]),
                Paragraph(self._format_money(op.gross), self.styles["TableCellSmallRight"]),
                Paragraph(self._format_money(op.tax), self.styles["TableCellSmallRight"]),
                Paragraph(f"{net_amount:,.2f} {op.gross.currency}", self.styles["TableCellSmallRight"]), 
            ])
        
        if len(tbl_data) > 1:
            fixed_cols_width = 2*cm + 2*cm + 2.5*cm + 2.5*cm + 2.5*cm 
            source_col_width = self.content_width - fixed_cols_width
            min_source_col_width = 4*cm # Ensure minimum width for source/asset details
            if source_col_width < min_source_col_width: source_col_width = min_source_col_width
            
            col_widths = [2*cm, source_col_width, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm]
            # Rescale if total width is not matching content_width (e.g. if source_col_width was capped)
            current_sum = sum(col_widths)
            if abs(current_sum - self.content_width) > 0.01 * cm: # Check for significant deviation
                 scale = self.content_width / current_sum
                 col_widths = [w * scale for w in col_widths]


            passive_table = Table(tbl_data, colWidths=col_widths, repeatRows=1)
            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR), 
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), 
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
                ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]
            for i_row in range(1, len(tbl_data)): 
                if i_row % 2 == 1: 
                    style_cmds.append(('BACKGROUND', (0, i_row), (-1, i_row), LIGHT_GREY))
            passive_table.setStyle(TableStyle(style_cmds))
            self.elements.append(passive_table)
        else:
            self.elements.append(Paragraph("No passive income records for this period.", self.styles["Normal"]))
        self.elements.append(PageBreak())

    def _add_trading_performance_details(self, trading: TradingPerformanceOut):
        title = "Trading Performance Details (FIFO)"
        if trading.year and (not self.report_period or str(trading.year) not in self.report_period):
             title += f" ({trading.year})"
        self.elements.append(Paragraph(title, self.styles["H1"]))

        for asset_pnl_summary in trading.summary: 
            asset = asset_pnl_summary.asset
            asset_name_str = asset.name + (f" ({asset.ticker})" if asset.ticker else "")
            self.elements.append(Paragraph(f"Asset: {asset_name_str}", self.styles["H2"]))
            
            if not asset_pnl_summary.trades:
                self.elements.append(Paragraph("No trades recorded for this asset.", self.styles["SmallText"]))
                self.elements.append(Spacer(1, 0.5*cm))
                continue

            tbl_header = [
                Paragraph("Buy Date", self.styles["TableHeader"]), Paragraph("Sell Date", self.styles["TableHeader"]),
                Paragraph("Qty", self.styles["TableHeader"]), Paragraph("Buy Price", self.styles["TableHeader"]),
                Paragraph("Sell Price", self.styles["TableHeader"]), Paragraph("Comm.", self.styles["TableHeader"]),
                Paragraph("Tax (Sell)", self.styles["TableHeader"]), Paragraph("P/L", self.styles["TableHeader"]),
            ]
            tbl_data = [tbl_header]
            
            asset_total_comm_dec = Decimal(0)
            asset_total_tax_dec = Decimal(0)

            for trade in asset_pnl_summary.trades: 
                pnl_float = self._get_safe_float(trade.pnl)
                
                if trade.sell.commission: asset_total_comm_dec += trade.sell.commission.amount
                if trade.sell.tax: asset_total_tax_dec += trade.sell.tax.amount

                pnl_style = self.styles["PositivePnl"] if pnl_float > 0 else \
                            (self.styles["NegativePnl"] if pnl_float < 0 else self.styles["TableCellSmallRight"])
                
                tbl_data.append([
                    Paragraph(self._safe_date_str(trade.buy.date), self.styles["TableCellSmall"]),
                    Paragraph(self._safe_date_str(trade.sell.date), self.styles["TableCellSmall"]),
                    Paragraph(self._format_decimal(trade.sell.quantity, 4), self.styles["TableCellSmallRight"]),
                    Paragraph(self._format_money(trade.buy.unit_price), self.styles["TableCellSmallRight"]),
                    Paragraph(self._format_money(trade.sell.unit_price), self.styles["TableCellSmallRight"]),
                    Paragraph(self._format_money(trade.sell.commission, "-"), self.styles["TableCellSmallRight"]),
                    Paragraph(self._format_money(trade.sell.tax, "-"), self.styles["TableCellSmallRight"]),
                    Paragraph(self._format_money(trade.pnl), pnl_style),
                ])
            
            comm_currency_str = asset_pnl_summary.pnl.currency 
            if asset_pnl_summary.trades and asset_pnl_summary.trades[0].sell.commission:
                comm_currency_str = asset_pnl_summary.trades[0].sell.commission.currency
            
            tax_currency_str = asset_pnl_summary.pnl.currency 
            if asset_pnl_summary.trades and asset_pnl_summary.trades[0].sell.tax:
                tax_currency_str = asset_pnl_summary.trades[0].sell.tax.currency
            
            # Asset Totals Row
            tbl_data.append([
                Paragraph("Asset Totals:", self.styles["SmallTextBold"]), '', '', '', '', # Spanned cells
                Paragraph(f"{asset_total_comm_dec:,.2f} {comm_currency_str}", self.styles["SmallTextBoldRight"]),
                Paragraph(f"{asset_total_tax_dec:,.2f} {tax_currency_str}", self.styles["SmallTextBoldRight"]),
                Paragraph(self._format_money(asset_pnl_summary.pnl), self.styles["SmallTextBoldRight"]), 
            ])

            col_widths = [1.9*cm, 1.9*cm, 1.8*cm, 2.3*cm, 2.3*cm, 2.0*cm, 2.0*cm, 2.3*cm]
            current_sum = sum(col_widths)
            if current_sum > self.content_width: # Scale down if too wide
                scale = self.content_width / current_sum
                col_widths = [w * scale for w in col_widths]
            elif self.content_width - current_sum > 0.1 * cm: # Distribute remainder if significantly narrower
                remainder = self.content_width - current_sum
                # Distribute to price/pnl columns (indices 3,4,7) or asset name (if that was dynamic)
                # For simplicity, add to the last P/L column
                col_widths[-1] += remainder
            
            trade_table = Table(tbl_data, colWidths=col_widths, repeatRows=1)
            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR), 
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), 
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('LEFTPADDING', (0,0), (-1,-1), 4), ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                # Totals row styling
                ('SPAN', (0, -1), (4, -1)), 
                ('ALIGN', (0, -1), (0, -1), 'LEFT'), # For the "Asset Totals:" text itself
                ('BACKGROUND', (0, -1), (-1, -1), MID_GREY), 
            ]
            for i_row in range(1, len(tbl_data) -1):
                if i_row % 2 == 1: 
                    style_cmds.append(('BACKGROUND', (0, i_row), (-1, i_row), LIGHT_GREY))
            trade_table.setStyle(TableStyle(style_cmds))
            self.elements.append(trade_table)
            self.elements.append(Spacer(1, 0.7*cm))
        self.elements.append(PageBreak())


    def _add_raw_data_details(self, raw_data_list: list[RawDataOut]):
        self.elements.append(Paragraph("Appendix: Raw Data Input", self.styles["H1"]))
        if not raw_data_list:
            self.elements.append(Paragraph("No raw data provided.", self.styles["Normal"]))
            self.elements.append(PageBreak()); return

        for raw_data_item in raw_data_list:
            self.elements.append(Paragraph(f"Source Parser: {raw_data_item.parser_name}", self.styles["H2"]))
            if not raw_data_item.records:
                self.elements.append(Paragraph("No records from this parser.", self.styles["SmallText"]))
                self.elements.append(Spacer(1, 0.3*cm)); continue

            tbl_header_texts = ["Date", "Type", "Asset/Details", "Qty/Gross", "Price/Tax", "Comm.", "Source"]
            tbl_header = [Paragraph(text, self.styles["TableHeader"]) for text in tbl_header_texts]
            tbl_data = [tbl_header]

            for op in raw_data_item.records: 
                if isinstance(op.date, NaTType): # Handle NaT dates
                    op_date = "N/A"
                else:  
                    op_date = op.date.date().strftime('%Y-%m-%d')
                op_type_str = op.class__
                asset_details_str, qty_gross_str, price_tax_str, comm_str, op_source_val_str = "N/A", "N/A", "N/A", "N/A", "N/A"

                if isinstance(op, Interest):
                    asset_details_str = op.source or "Interest Income"
                    qty_gross_str = self._format_money(op.gross)
                    price_tax_str = self._format_money(op.tax, "-")
                    comm_str = self._format_money(op.commission, "-")
                    op_source_val_str = op.source or ""
                elif isinstance(op, Dividend):
                    asset_details_str = op.asset.name + (f" ({op.asset.ticker})" if op.asset.ticker else "")
                    if op.source: asset_details_str += f" via {op.source}"
                    qty_gross_str = self._format_money(op.gross)
                    price_tax_str = self._format_money(op.tax, "-")
                    comm_str = "-" # Dividend model has no commission field
                    op_source_val_str = op.source or ""
                
                elif isinstance(op, (BuyOperation, SellOperation)):
                    asset_details_str = op.asset.name + (f" ({op.asset.ticker})" if op.asset.ticker else "")
                    qty_gross_str = self._format_decimal(op.quantity, 4)
                    unit_price_fmt = self._format_money(op.unit_price)
                    comm_str = self._format_money(op.commission, "-")
                    op_source_val_str = raw_data_item.parser_name # Default source
                    if isinstance(op, SellOperation): 
                        sell_tax_fmt = self._format_money(op.tax, "-")
                        if sell_tax_fmt != "-" and sell_tax_fmt != self._format_money(ZERO_EUR, "-"):
                             price_tax_str = f"{unit_price_fmt} (Tax: {sell_tax_fmt})"
                        else:
                             price_tax_str = unit_price_fmt
                    else: # BuyOperation
                        price_tax_str = unit_price_fmt
                
                elif isinstance(op, AssetTrade): 
                    asset_details_str = op.buy.asset.name + (f" ({op.buy.asset.ticker})" if op.buy.asset.ticker else "")
                    qty_gross_str = f"PnL: {self._format_money(op.pnl)}"
                    buy_price_fmt = self._format_money(op.buy.unit_price)
                    sell_price_fmt = self._format_money(op.sell.unit_price)
                    price_tax_str = f"Buy: {buy_price_fmt}, Sell: {sell_price_fmt}"
                    # Show combined or sell commission for AssetTrade. Sell is usually more relevant for PNL.
                    comm_str = self._format_money(op.sell.commission, "-") 
                    op_source_val_str = "Processor Aggregated"


                tbl_data.append([
                    Paragraph(op_date, self.styles["TableCellSmall"]),
                    Paragraph(op_type_str, self.styles["TableCellSmall"]),
                    Paragraph(asset_details_str, self.styles["TableCellSmall"]), # Potentially long
                    Paragraph(qty_gross_str, self.styles["TableCellSmallRight"]),
                    Paragraph(price_tax_str, self.styles["TableCellSmallRight"]),
                    Paragraph(comm_str, self.styles["TableCellSmallRight"]),
                    Paragraph(op_source_val_str, self.styles["TableCellSmall"]),
                ])
            
            fixed_cols_width = sum([2*cm, # Date
                                    2*cm, # Type
                                    2.5*cm, # Qty/Gross
                                    2.5*cm, # Price/Tax
                                    2*cm, # Comm.
                                    2*cm  # Source
                                    ]) 
            details_col_width = self.content_width - fixed_cols_width
            min_details_col_width = 4*cm
            if details_col_width < min_details_col_width: details_col_width = min_details_col_width
            
            col_widths = [2*cm, 2*cm, details_col_width, 2.5*cm, 2.5*cm, 2*cm, 2*cm]
            current_sum = sum(col_widths)
            if abs(current_sum - self.content_width) > 0.01 * cm:
                 scale = self.content_width / current_sum
                 col_widths = [w * scale for w in col_widths]

            raw_table = Table(tbl_data, colWidths=col_widths, repeatRows=1)
            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), SECONDARY_COLOR), 
                ('VALIGN', (0, 0), (-1, -1), 'TOP'), 
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('LEFTPADDING', (0,0), (-1,-1), 4), ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ]
            for i_row in range(1, len(tbl_data)):
                if i_row % 2 == 1: 
                    style_cmds.append(('BACKGROUND', (0, i_row), (-1, i_row), LIGHT_GREY))
            raw_table.setStyle(TableStyle(style_cmds))

            self.elements.append(raw_table)
            self.elements.append(Spacer(1, 0.7*cm))
        self.elements.append(PageBreak())

    def render(self, *all_results: Any) -> str: 
        self.elements = [] 
        doc = SimpleDocTemplate(
            str(self.out_file), pagesize=A4, title=self.report_main_title, author=self.author_name,
            leftMargin=self.left_margin, rightMargin=self.right_margin,
            topMargin=self.top_margin, bottomMargin=self.bottom_margin
        )
        savings_data: SavingPerformanceOut | None = None
        savings_data_list = [r for r in all_results if isinstance(r, SavingPerformanceOut)]
        if len(savings_data_list) > 0:
            savings_data = savings_data_list[0]  
        trading_data: TradingPerformanceOut | None = None
        trading_data_list = [r for r in all_results if isinstance(r, TradingPerformanceOut)]
        if len(trading_data_list) > 0:
            trading_data = trading_data_list[0]
        raw_data_list: list[RawDataOut] = [r for r in all_results if isinstance(r, RawDataOut)]

        self._add_cover_page()

        if not savings_data and not trading_data and not raw_data_list:
            self.elements.append(Paragraph("No financial data provided for this report period.", self.styles["H2"]))
            doc.build(self.elements, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
            return str(self.out_file)

        self._add_overall_summary(savings_data, trading_data)
        
        if savings_data and savings_data.records:
             self._add_passive_income_details(savings_data)
        
        if trading_data and trading_data.summary:
            self._add_trading_performance_details(trading_data)
            
        if raw_data_list:
            self._add_raw_data_details(raw_data_list)

        doc.build(self.elements, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return str(self.out_file)

    def _safe_date_str(self, dt_obj):
        """Return a safe date string or 'N/A' if dt_obj is None or NaTType."""
        if dt_obj is None:
            return "N/A"
        # Handle pandas NaTType
        if type(dt_obj).__name__ == "NaTType" or str(dt_obj) == "NaT":
            return "N/A"
        try:
            return dt_obj.date().strftime('%Y-%m-%d')
        except Exception:
            try:
                return dt_obj.strftime('%Y-%m-%d')
            except Exception:
                return "N/A"

if __name__ == '__main__':
    # --- Example Usage with Mock Data ---
    
    asset_btc = Asset(name="Bitcoin", ticker="BTC", isin=None)
    asset_eth = Asset(name="Ethereum", ticker="ETH", isin=None)
    asset_stock_a = Asset(name="Global Growth Fund", isin="IE00B03HCZ61", ticker="GGF")
    asset_savings_platform = Asset(name="Nexo Platform", isin=None, ticker="NEXO") 

    mock_raw_interest = Interest(
        date=dt.datetime(2023,1,10, 10,0,0), 
        source="Bank A Savings", 
        gross=Money(amount=Decimal("10.50"), currency="EUR"),
        tax=Money(amount=Decimal("1.05"), currency="EUR")
    )
    mock_raw_dividend = Dividend(
        asset=asset_stock_a,
        date=dt.datetime(2023,2,15, 10,0,0),
        gross=Money(amount=Decimal("25.00"), currency="EUR"),
        tax=Money(amount=Decimal("3.75"), currency="EUR"),
        source="Fund Manager X"
    )
    mock_raw_buy = BuyOperation(
        asset=asset_btc,
        date=dt.datetime(2023,1,5, 10,0,0),
        quantity=Decimal("0.1"),
        unit_price=Money(amount=Decimal("20000"), currency="EUR"),
        commission=Money(amount=Decimal("2.0"), currency="EUR")
    )

    mock_raw_data1 = RawDataOut(
        parser_name="BankStatementParser",
        records=[mock_raw_interest, mock_raw_dividend]
    )
    mock_raw_data2 = RawDataOut(
        parser_name="CryptoExchangeParser",
        records=[mock_raw_buy] 
    )

    saving_op1 = Interest(
        gross=Money(amount=Decimal("50.25"), currency="EUR"),
        date=dt.datetime(2023, 1, 15, 12,0,0),
        tax=Money(amount=Decimal("5.03"), currency="EUR"),
        source="Nexo Savings Interest"
    )
    saving_op2 = Dividend( 
        asset=asset_savings_platform, 
        gross=Money(amount=Decimal("100.50"), currency="EUR"),
        date=dt.datetime(2023, 2, 20, 12,0,0),
        tax=Money(amount=Decimal("10.05"), currency="EUR"),
        source="BlockFi Rewards"
    )
    mock_savings_data = SavingPerformanceOut(
        year=2023,
        total_eur=Decimal("150.75"), 
        records=[saving_op1, saving_op2]
    )
    
    trade1_buy = BuyOperation(asset=asset_eth, unit_price=Money(amount=Decimal("1500"), currency="EUR"), quantity=Decimal("1.0"), date=dt.datetime(2023,3,1,0,0,0), commission=Money(amount=Decimal("1"), currency="EUR"))
    trade1_sell = SellOperation(asset=asset_eth, unit_price=Money(amount=Decimal("1800"), currency="EUR"), quantity=Decimal("1.0"), date=dt.datetime(2023,3,15,0,0,0), commission=Money(amount=Decimal("1"), currency="EUR"), tax=Money(amount=Decimal("2.50"), currency="EUR"))
    asset_trade_eth = AssetTrade(buy=trade1_buy, sell=trade1_sell, pnl=Money(amount=Decimal("299.00"), currency="EUR")) # PNL = (1800-1500)*1 - 1(sell_comm) = 299

    trade2_buy = BuyOperation(asset=asset_btc, unit_price=Money(amount=Decimal("20000"), currency="EUR"), quantity=Decimal("0.1"), date=dt.datetime(2023,1,5,0,0,0))
    trade2_sell = SellOperation(asset=asset_btc, unit_price=Money(amount=Decimal("22000"), currency="EUR"), quantity=Decimal("0.1"), date=dt.datetime(2023,1,10,0,0,0), commission=Money(amount=Decimal("2"), currency="EUR"), tax=Money(amount=Decimal("1"), currency="EUR"))
    asset_trade_btc1 = AssetTrade(buy=trade2_buy, sell=trade2_sell, pnl=Money(amount=Decimal("198.00"), currency="EUR")) # PNL = (22000-20000)*0.1 - 2(sell_comm) = 198

    asset_pnl_eth = AssetPNL(asset=asset_eth, pnl=Money(amount=Decimal("299.00"), currency="EUR"), trades=[asset_trade_eth])
    asset_pnl_btc = AssetPNL(asset=asset_btc, pnl=Money(amount=Decimal("198.00"), currency="EUR"), trades=[asset_trade_btc1]) 

    mock_trading_data = TradingPerformanceOut(
        year=2023,
        summary=[asset_pnl_eth, asset_pnl_btc] # Assume CLI sorts PNL: ETH (299) then BTC (198)
    )
    
    reporter = PdfReportOutput(
        out_file="example_report_full.pdf",
        report_main_title="Comprehensive Financial Overview",
        report_period="Fiscal Year 2023"
    )
    report_file = reporter.render(mock_raw_data1, mock_savings_data, mock_trading_data, mock_raw_data2)
    print(f"Full Report generated: {report_file}")

    reporter_raw_only = PdfReportOutput(out_file="example_report_raw_only.pdf", report_period="Q1 Raw Data")
    report_file_raw = reporter_raw_only.render(mock_raw_data1, mock_raw_data2)
    print(f"Raw Data Only Report generated: {report_file_raw}")

    reporter_no_data = PdfReportOutput(out_file="example_report_no_data.pdf", report_period="Empty Period")
    report_file_no_data = reporter_no_data.render()
    print(f"No Data Report generated: {report_file_no_data}")

    reporter_savings_only = PdfReportOutput(out_file="example_report_savings_only.pdf", report_period="Savings Data 2023")
    report_file_savings = reporter_savings_only.render(mock_savings_data, mock_raw_data1) # Include some raw data for context
    print(f"Savings Only Report generated: {report_file_savings}")

    reporter_trading_only = PdfReportOutput(out_file="example_report_trading_only.pdf", report_period="Trading Data 2023")
    report_file_trading = reporter_trading_only.render(mock_trading_data, mock_raw_data2) # Include some raw data for context
    print(f"Trading Only Report generated: {report_file_trading}")