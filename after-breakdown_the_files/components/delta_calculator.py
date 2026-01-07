from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.worksheet.worksheet import Worksheet

class DeltaCalculator:
    def __init__(self, base_exporter):
        self.base = base_exporter

    def insert_delta_columns(self, ws: Worksheet, fiscal_columns: list, start_data_row: int):
        """Write delta and delta % columns (no longer inserts new columns)."""
        if len(fiscal_columns) < 2:
            return

        print("[INFO] Writing Δ value and Δ % columns...")

        num_fiscal = len(fiscal_columns)
        last_value_col = 2 + (num_fiscal - 1) * 2      # Last value col (e.g., G)
        last_pct_col = last_value_col + 1              # % of total column (e.g., H)

        spacer_col = last_pct_col + 1                  # I
        delta_col = spacer_col + 1                     # J
        delta_pct_col = delta_col + 1                  # K

        # Write delta column headers in row 6
        prev_label = fiscal_columns[-2]
        curr_label = fiscal_columns[-1].split()[0]
        delta_header = f"Δ ({prev_label} to {curr_label})"

        col_letter_start = get_column_letter(delta_col)
        col_letter_end = get_column_letter(delta_pct_col)

        ws.merge_cells(f"{col_letter_start}6:{col_letter_end}6")
        header_cell = ws[f"{col_letter_start}6"]
        header_cell.value = delta_header
        header_cell.fill = PatternFill("solid", fgColor="000000")
        header_cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        header_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Format column widths
        ws.column_dimensions[get_column_letter(delta_col)].width = 12
        ws.column_dimensions[get_column_letter(delta_pct_col)].width = 7
        ws.column_dimensions[get_column_letter(spacer_col)].width = 4

        # Write Δ formulas row-by-row
        self.write_all_delta_formulas(ws, start_data_row)

    def write_all_delta_formulas(self, ws: Worksheet, start_data_row: int):
        """Applies Δ and Δ% formulas across the worksheet after all values are written."""
        num_fiscal = len(self.base.annual_pivot.columns)
        if num_fiscal < 2:
            return

        prev_val_col = 2 + (num_fiscal - 2) * 2
        curr_val_col = 2 + (num_fiscal - 1) * 2
        spacer_col = 2 + num_fiscal * 2
        delta_col = spacer_col + 1
        delta_pct_col = delta_col + 1

        prev_letter = get_column_letter(prev_val_col)
        curr_letter = get_column_letter(curr_val_col)

        print("[INFO] Writing delta formulas row-by-row...")
        for row in range(start_data_row, ws.max_row + 1):
            label = ws.cell(row=row, column=1).value
            if not label or str(label).strip() == "":
                continue

            # Δ value
            delta_cell = ws.cell(row=row, column=delta_col)
            delta_cell.value = f"={curr_letter}{row}-{prev_letter}{row}"
            delta_cell.number_format = self.base.currency_format
            delta_cell.alignment = Alignment(horizontal="center")

            # Δ %
            delta_pct_cell = ws.cell(row=row, column=delta_pct_col)
            delta_pct_cell.value = f"=IF({prev_letter}{row}=0,0,({curr_letter}{row}/{prev_letter}{row})-1)"
            delta_pct_cell.number_format = self.base.percent_format
            delta_pct_cell.alignment = Alignment(horizontal="center")