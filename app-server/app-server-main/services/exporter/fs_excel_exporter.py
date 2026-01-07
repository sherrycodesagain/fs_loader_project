
import os
import pandas as pd
from openpyxl.utils import get_column_letter

from .components.base_exporter import BaseExporter
from .components.pivot_builder import PivotBuilder
from .components.row_writer import RowWriter
from .components.derived_calculations import DerivedCalculations
from .components.worksheet_formatter import WorksheetFormatter
from .components.delta_calculator import DeltaCalculator
from .components.statement_writer import StatementWriter

class FSExcelExporter(BaseExporter):
    def __init__(self, enriched_df: pd.DataFrame, value_date: pd.Timestamp,
                 fiscal_year_end: pd.Timestamp, output_path: str = "output/income_statement.xlsx"):
        super().__init__(enriched_df, value_date, fiscal_year_end, output_path)
        
        # Initialize all components
        self.pivot_builder = PivotBuilder(self)
        self.row_writer = RowWriter(self)
        self.derived_calc = DerivedCalculations(self)
        self.formatter = WorksheetFormatter(self)
        self.delta_calc = DeltaCalculator(self)
        self.statement_writer = StatementWriter(self, self.row_writer, self.derived_calc, self.formatter, self.delta_calc)

    def export(self):
        """Main entry point to export all income statement formats to Excel."""
        print("[INFO] Starting Excel export...")
        self.pivot_builder.build_pivots()
        self._write_annual_income_statement()
        self._write_quarterly_income_statement()
        self._write_monthly_income_statement()
        self.formatter.apply_styles()
        self._finalize_file()

    def _write_annual_income_statement(self):
        print("[INFO] Writing Annual sheet...")
        self.statement_writer.write_generic_income_statement(
            sheet_title="Annual Income Statement",
            pivot_df=self.annual_pivot,
            header_title="Annual Income Statement"
        )

    def _write_quarterly_income_statement(self):
        print("[INFO] Writing Quarterly sheet...")
        self.statement_writer.write_generic_income_statement(
            sheet_title="Quarterly Income Statement",
            pivot_df=self.quarterly_pivot,
            header_title="Quarterly Income Statement",
            mode="quarterly"
        )

    def _write_monthly_income_statement(self):
        print("[INFO] Writing Monthly sheet...")
        self.statement_writer.write_generic_income_statement(
            sheet_title="Monthly Income Statement",
            pivot_df=self.monthly_pivot,
            header_title="Monthly Income Statement",
            mode="monthly"
        )

    def _finalize_file(self):
        """Save the Excel file with cleanup of ghost columns."""
        print("[INFO] Saving workbook...")
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        num_fiscal = len(self.annual_pivot.columns)
        spacer_col = 2 + num_fiscal * 2
        spacer_letter = get_column_letter(spacer_col)
        self.wb["Annual Income Statement"].column_dimensions[spacer_letter].width = 4

        self.wb.save(self.output_path)
        print(f"[SUCCESS] File saved at: {self.output_path}")