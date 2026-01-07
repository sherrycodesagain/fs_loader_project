from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.worksheet.worksheet import Worksheet
from config import COMPANY_NAME, CURRENCY, DENOMINATION

class WorksheetFormatter:
    def __init__(self, base_exporter):
        self.base = base_exporter

    def write_header(self, ws: Worksheet, column_labels: list, mode: str = "annual"):
        """Writes the title and column headers to the given worksheet."""
        header_fill_black = PatternFill("solid", fgColor="000000")
        white_font = Font(name="Arial", bold=True, color="FFFFFF")

        # Row 1: Title
        col_multiplier = 2 if mode == "annual" else 1
        total_cols = 1 + len(column_labels) * col_multiplier + (3 if mode == "annual" else 0)

        last_col_letter = get_column_letter(total_cols)

        ws.merge_cells(f"A1:{last_col_letter}1")
        ws["A1"] = "Annual Income Statements"
        ws["A1"].font = Font(name="Arial", bold=True, size=14, color="FFFFFF")
        ws["A1"].fill = header_fill_black
        ws["A1"].alignment = Alignment(horizontal="left")

        # Row 2-4: Company name, currency, fiscal year end
        header_data = [
            COMPANY_NAME,
            f"({CURRENCY}){DENOMINATION}",
            f"Year End: {self.base.fiscal_year_end.strftime('%B %d')}"
        ]

        for row_num, value in enumerate(header_data, start=2):
            ws[f"A{row_num}"] = value

            for col in range(1, total_cols + 1):
                cell = ws.cell(row=row_num, column=col)
                cell.fill = header_fill_black
                cell.font = white_font
                cell.alignment = Alignment(horizontal="left" if col == 1 else "center")

        # Row 6: Column headers
        start_row = 6
        start_col = 2  # Column B

        black_fill = PatternFill("solid", fgColor="000000")
        white_bold_font = Font(name="Arial", bold=True, color="FFFFFF")

        for i, label in enumerate(column_labels):
            col_start = start_col + i * col_multiplier
            if mode == "annual":
                col_end = col_start + 1
                ws.merge_cells(f"{get_column_letter(col_start)}{start_row}:{get_column_letter(col_end)}{start_row}")
            else:
                col_end = col_start 

            start_letter = get_column_letter(col_start)
            end_letter = get_column_letter(col_end)

            if mode == "annual":
                col_end = col_start + 1
                ws.merge_cells(f"{get_column_letter(col_start)}{start_row}:{get_column_letter(col_end)}{start_row}")
            else:
                col_end = col_start  # No merge for non-annual

            start_letter = get_column_letter(col_start)
            end_letter = get_column_letter(col_end)

            ws.merge_cells(f"{start_letter}{start_row}:{end_letter}{start_row}")

            cell = ws[f"{start_letter}{start_row}"]
            cell.value = label
            cell.fill = black_fill
            cell.font = white_bold_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        return start_row + 1

    def apply_styles(self):
        """Apply column widths and freeze panes for Annual sheet."""
        ws = self.base.wb["Annual Income Statement"]

        # Column A = account labels
        ws.column_dimensions["A"].width = 40

        num_fiscal = len(self.base.annual_pivot.columns)
        base_col = 2  # Start at column B

        # Unified width for all numeric columns
        value_col_width = 11
        percent_col_width = 7
        spacer_width = 4

        # Set widths for fiscal value and % columns
        for i in range(num_fiscal):
            value_col = base_col + i * 2
            pct_col = value_col + 1

            ws.column_dimensions[get_column_letter(value_col)].width = value_col_width
            ws.column_dimensions[get_column_letter(pct_col)].width = percent_col_width

        # Spacer column after fiscal periods
        spacer_col = base_col + num_fiscal * 2
        ws.column_dimensions[get_column_letter(spacer_col)].width = spacer_width

        # Delta columns (Δ value and Δ%)
        delta_col = spacer_col + 1
        delta_pct_col = delta_col + 1

        if delta_pct_col <= ws.max_column:
            ws.column_dimensions[get_column_letter(delta_col)].width = value_col_width
            ws.column_dimensions[get_column_letter(delta_pct_col)].width = percent_col_width
    
    def apply_column_widths(self, ws, mode, num_columns):
        """Set column widths for quarterly/monthly uniformly."""
        if mode == "annual":
            return  # Handled separately
        ws.column_dimensions["A"].width = 40
        for i in range(num_columns):
            col_idx = 2 + i
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = 12

    def bold_top_level_rows(self, ws: Worksheet, start_data_row: int):
        """Apply bold only to known KPI rows (like Gross Margin, Net Income, etc.)."""
        kpi_labels = {
            "gross margin",
            "operating margin",
            "net income before taxes",
            "net income",
            "ebitda"
        }

        for row in range(start_data_row, ws.max_row + 1):
            label = ws.cell(row=row, column=1).value
            if label and str(label).strip().lower() in kpi_labels:
                for col in range(1, ws.max_column + 1):
                    ws.cell(row=row, column=col).font = self.base.bold_font

    def preallocate_percentage_columns(self, ws, fiscal_columns):
        """Inserts empty % columns next to each value column before any data is written."""
        print("[INFO] Pre-allocating % of total columns...")
        for i in range(len(fiscal_columns)):
            pct_col = 2 + i * 2 + 1
            ws.insert_cols(pct_col)
            ws.column_dimensions[get_column_letter(pct_col)].width = 7  # Optional: width for % columns
    
    def fill_percentage_formulas(self, ws, fiscal_columns, start_row):
        """Fills in % of Sales formulas into the already-inserted % columns."""
        print("[INFO] Filling % of total formulas...")

        # Find the Sales row
        sales_row = None
        for row in range(start_row, ws.max_row + 1):
            label = str(ws.cell(row=row, column=1).value).strip().lower()
            if label == "sales":
                sales_row = row
                break

        if not sales_row:
            print("[WARNING] Could not find Sales row — skipping % formulas.")
            return

        for row in range(start_row, ws.max_row + 1):
            if not ws.cell(row=row, column=1).value:
                continue

            for i in range(len(fiscal_columns)):
                val_col = 2 + i * 2
                pct_col = val_col + 1
                letter = get_column_letter(val_col)

                pct_cell = ws.cell(row=row, column=pct_col)
                pct_cell.value = f"={letter}{row}/${letter}${sales_row}"
                pct_cell.number_format = self.base.percent_format