import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.worksheet import Worksheet
from config import COMPANY_NAME, DENOMINATION, CURRENCY
from openpyxl.utils import get_column_letter
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment
from cache.memory_store import memory_store

DERIVED_LABELS = [
    "Sales",
    "Cost of sales",
    "Operating expenses",
    "Other income/expenses",
    "Income taxes"
]

class FSExcelExporter:
    def __init__(self, enriched_df: pd.DataFrame, value_date: pd.Timestamp,
                 fiscal_year_end: pd.Timestamp, output_path: str = "output/income_statement.xlsx"):
        self.df = enriched_df.copy()
        self.value_date = value_date
        self.fiscal_year_end = fiscal_year_end
        self.output_path = output_path
        self.wb = Workbook()
        self.row_tracker = {} 

        # Default styles
        self.arial_font = Font(name="Arial", size=10)
        self.bold_font = Font(name="Arial", bold=True, size=10)
        self.italic_font = Font(name="Arial", italic=True, size=10)
        self.level4_font = Font(name="Arial", size=8.5)
        self.header_fill = PatternFill("solid", fgColor="DDEBF7")
        self.total_fill = PatternFill("solid", fgColor="F2F2F2")
        self.thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        self.currency_format = '#,##0_);(#,##0)'
        self.percent_format = '0%;(0%)'

        # To be built inside methods
        self.annual_pivot = None
        self.quarterly_pivot = None
        self.monthly_pivot = None

    def export(self):
        """Main entry point to export all income statement formats to Excel."""
        print("[INFO] Starting Excel export...")
        self._build_pivots()
        self._write_annual_income_statement()
        self._write_quarterly_income_statement()
        self._write_monthly_income_statement()
        self._apply_styles()
        self._finalize_file()

    def _insert_percentage_below_row(self, ws, label_row: int, label_text: str, sales_row: int, fiscal_columns: list):
        """
        Insert a new row below `label_row` with % values (label_text + " (%)") for derived KPIs only.
        """
        pct_row = label_row + 1
        ws.insert_rows(pct_row)

        # Label column (A)
        ws.cell(row=pct_row, column=1, value=f"{label_text} (%)")
        ws.cell(row=pct_row, column=1).font = self.arial_font
        ws.cell(row=pct_row, column=1).alignment = Alignment(indent=0)

        for i, _ in enumerate(fiscal_columns):
            col_idx = 2 + i 
            letter = get_column_letter(col_idx)
            
            formula = f"=IF(${letter}${sales_row}=0, 0, {letter}{label_row}/${letter}${sales_row})"

            cell = ws.cell(row=pct_row, column=col_idx)
            cell.value = formula
            cell.number_format = self.percent_format
            cell.font = self.italic_font

    def _build_pivots(self):
        print("[INFO] Building annual pivot...")
        df = self.df.copy()
        df = df[df["type"] == "IS"]  # Only include income statement accounts
        valid_fys = memory_store[self.df["dataset_id"].iloc[0]]["valid_fiscal_years"]

        fy_rows = df[df["fiscal_year"].isin(valid_fys)].copy()
        fy_rows["column_label"] = fy_rows["fiscal_year"]

        ltm_rows = df[df["ltm"].str.strip().astype(bool)].copy()
        ltm_rows["column_label"] = ltm_rows["ltm"]

        # Combine both
        df = pd.concat([fy_rows, ltm_rows], ignore_index=True)
        # Drop rows without a column label
        df = df[df["column_label"].notna() & df["column_label"].str.strip().astype(bool)]

        # Build pivot table
        self.annual_pivot = pd.pivot_table(
            df,
            index=["fs_grouping", "detailed_grouping", "account"],
            columns="column_label",
            values="ending_balance",
            aggfunc="sum",
            fill_value=0
        )
        
        print("[DEBUG] Sales rows in pivot (any column):")
        for idx in self.annual_pivot.index:
            if idx[0].strip().lower() == "sales":
                print(f"{idx}: {self.annual_pivot.loc[idx].to_dict()}")


        # Sort columns: Fiscal years first, then YTD, then LTM
        cols = list(self.annual_pivot.columns)

        def sort_key(label):
            if label.startswith("F") and label[1:].isdigit():
                return (0, int(label[1:]))  
            if label.startswith("YTD"):
                return (1, label)
            if label.startswith("LTM"):
                return (2, label)
            return (3, label)
            
        print("[INFO] Building monthly pivot...")
        monthly_df = self.df.copy()
        monthly_df = monthly_df[monthly_df["type"] == "IS"]
        monthly_df = monthly_df[monthly_df["month"].notna()]
        monthly_df["column_label"] = pd.to_datetime(monthly_df["date"]) + pd.offsets.MonthEnd(0)
        monthly_df["column_label"] = monthly_df["column_label"].dt.strftime("%d-%b-%y")

        self.monthly_pivot = pd.pivot_table(
            monthly_df,
            index=["fs_grouping", "detailed_grouping", "account"],
            columns="column_label",
            values="ending_balance",
            aggfunc="sum",
            fill_value=0
        )

        # Sort by calendar date, not alphabetical month names
        self.monthly_pivot = self.monthly_pivot.reindex(
            sorted(self.monthly_pivot.columns, key=lambda m: pd.to_datetime(m)),
            axis=1
        )
        print("[INFO] Building quarterly pivot...")
        quarterly_df = self.df.copy()
        quarterly_df = quarterly_df[quarterly_df["type"] == "IS"]
        quarterly_df = quarterly_df[quarterly_df["fiscal_quarter"].notna()]
        quarterly_df["column_label"] = quarterly_df["fiscal_quarter"]

        self.quarterly_pivot = pd.pivot_table(
            quarterly_df,
            index=["fs_grouping", "detailed_grouping", "account"],
            columns="column_label",
            values="ending_balance",
            aggfunc="sum",
            fill_value=0
        )

        # Optional: sort quarters chronologically
        def quarter_sort_key(q):
            try:
                q_num = int(q[1])
                fy = int(q.split("F")[1])
                return (fy, q_num)
            except:
                return (9999, 99)

        self.quarterly_pivot = self.quarterly_pivot.reindex(
            sorted(self.quarterly_pivot.columns, key=quarter_sort_key),
            axis=1
        )


        self.annual_pivot = self.annual_pivot.reindex(sorted(cols, key=sort_key), axis=1)
    
    
    def _write_top_level_grouping(self, ws, is_df, top, fiscal_columns, current_row, row_tracker, mode):
        ws.cell(row=current_row, column=1, value=top)
        ws.cell(row=current_row, column=1).font = self.arial_font
        ws.cell(row=current_row, column=1).alignment = Alignment(indent=0)
        ws.row_dimensions[current_row].outlineLevel = 0
        ws.row_dimensions[current_row].hidden = False

        for idx, col in enumerate(fiscal_columns):
            keys = [
                (fs, detail, acct)
                for fs in is_df[is_df["top_level_grouping"] == top]["fs_grouping"].dropna().unique()
                for detail in is_df[(is_df["top_level_grouping"] == top) & (is_df["fs_grouping"] == fs)]["detailed_grouping"].dropna().unique()
                for acct in is_df[(is_df["top_level_grouping"] == top) & (is_df["fs_grouping"] == fs) & (is_df["detailed_grouping"] == detail)]["account"].unique()
                if (fs, detail, acct) in self.annual_pivot.index
            ]
            val = sum(self.annual_pivot.at[k, col] for k in keys)
            col_idx = self._get_col_idx(idx, mode)
            ws.cell(row=current_row, column=col_idx, value=val).number_format = self.currency_format

        ws.row_dimensions[current_row].outlineLevel = 0
        ws.row_dimensions[current_row].hidden = False

        fs_groupings = sorted(is_df[is_df["top_level_grouping"] == top]["fs_grouping"].dropna().unique())

        if top.strip().lower() in [label.lower() for label in DERIVED_LABELS]:
            row_tracker[top.strip().lower()] = current_row

        current_row += 1

        for fs in fs_groupings:
            current_row = self._write_fs_grouping(
                ws, is_df, top, fs, fiscal_columns, current_row, row_tracker, mode
            )

        return current_row
    
    def _write_fs_grouping(self, ws, is_df, top, fs, fiscal_columns, current_row, row_tracker,mode):
        ws.cell(row=current_row, column=1, value=fs)
        ws.cell(row=current_row, column=1).font = self.arial_font
        ws.cell(row=current_row, column=1).alignment = Alignment(indent=1)
        ws.row_dimensions[current_row].outlineLevel = 1
        ws.row_dimensions[current_row].hidden = False

        keys = [
            (fs, detail, acct)
            for detail in is_df[(is_df["top_level_grouping"] == top) & (is_df["fs_grouping"] == fs)]["detailed_grouping"].dropna().unique()
            for acct in is_df[(is_df["top_level_grouping"] == top) & (is_df["fs_grouping"] == fs) & (is_df["detailed_grouping"] == detail)]["account"].unique()
            if (fs, detail, acct) in self.annual_pivot.index
        ]
        for idx, col in enumerate(fiscal_columns):
            subtotal = sum(self.annual_pivot.at[k, col] for k in keys)
            col_idx = self._get_col_idx(idx, mode)
            ws.cell(row=current_row, column=col_idx, value=subtotal).number_format = self.currency_format

        fs_clean = fs.strip().lower()
        if fs_clean in ["amortization", "interest expense"]:
            row_tracker[fs_clean] = current_row

        current_row += 1

        detail_groups = sorted(
            is_df[(is_df["top_level_grouping"] == top) & (is_df["fs_grouping"] == fs)]["detailed_grouping"].dropna().unique()
        )

        for detail in detail_groups:
            current_row = self._write_detailed_grouping(
                ws, is_df, top, fs, detail, fiscal_columns, current_row, row_tracker, mode
            )

        return current_row

    def _write_detailed_grouping(self, ws, is_df, top, fs, detail, fiscal_columns, current_row, row_tracker, mode):
        detail_row = current_row
        ws.cell(row=detail_row, column=1, value=detail)
        ws.cell(row=detail_row, column=1).font = self.arial_font
        ws.cell(row=detail_row, column=1).alignment = Alignment(indent=2)
        ws.row_dimensions[detail_row].outlineLevel = 2
        ws.row_dimensions[detail_row].hidden = False

        keys = [
            (fs, detail, acct)
            for acct in is_df[
                (is_df["top_level_grouping"] == top)
                & (is_df["fs_grouping"] == fs)
                & (is_df["detailed_grouping"] == detail)
            ]["account"].unique()
            if (fs, detail, acct) in self.annual_pivot.index
        ]

        for idx, col in enumerate(fiscal_columns):
            subtotal = sum(self.annual_pivot.at[k, col] for k in keys)
            col_idx = self._get_col_idx(idx, mode)
            ws.cell(row=current_row, column=col_idx, value=subtotal).number_format = self.currency_format

        current_row += 1

        # Write account-level rows under this detailed group
        current_row = self._write_account_rows(
            ws, is_df, top, fs, detail, fiscal_columns, current_row, row_tracker, mode
        )

        # Group account rows under the detail
        if current_row > detail_row + 1:
            ws.row_dimensions.group(detail_row + 1, current_row - 1, outline_level=3, hidden=True)

        return current_row

    def _write_account_rows(self, ws, is_df, top, fs, detail, fiscal_columns, current_row, row_tracker, mode):
        account_rows = is_df[
            (is_df["top_level_grouping"] == top) &
            (is_df["fs_grouping"] == fs) &
            (is_df["detailed_grouping"] == detail)
        ]

        for acct in sorted(account_rows["account"].unique()):
            ws.cell(row=current_row, column=1, value=acct)
            ws.cell(row=current_row, column=1).font = self.level4_font
            ws.cell(row=current_row, column=1).alignment = Alignment(indent=3)

            for idx, col in enumerate(fiscal_columns):
                value = self.annual_pivot.at[(fs, detail, acct), col] if (fs, detail, acct) in self.annual_pivot.index else 0
                col_idx = self._get_col_idx(idx, mode)
                ws.cell(row=current_row, column=col_idx, value=value).number_format = self.currency_format

            
            ws.row_dimensions[current_row].outlineLevel = 3
            ws.row_dimensions[current_row].hidden = True
            current_row += 1
            

        return current_row

    def _write_annual_income_statement(self):
        print("[INFO] Writing Annual sheet...")
        self._write_generic_income_statement(
            sheet_title="Annual Income Statement",
            pivot_df=self.annual_pivot,
            header_title="Annual Income Statement"
        )

    def _write_quarterly_income_statement(self):
        print("[INFO] Writing Quarterly sheet...")
        self._write_generic_income_statement(
            sheet_title="Quarterly Income Statement",
            pivot_df=self.quarterly_pivot,
            header_title="Quarterly Income Statement",
            mode="quarterly"
        )

    def _write_monthly_income_statement(self):
        print("[INFO] Writing Monthly sheet...")
        self._write_generic_income_statement(
            sheet_title="Monthly Income Statement",
            pivot_df=self.monthly_pivot,
            header_title="Monthly Income Statement",
            mode="monthly"
        )

    def _write_generic_income_statement(self, sheet_title: str, pivot_df: pd.DataFrame, header_title: str, mode: str = "annual"):
        ws = self.wb.create_sheet(title=sheet_title)
        ws.sheet_properties.outlinePr.summaryBelow = False
        ws.sheet_properties.outlinePr.applyStyles = True
        ws.sheet_properties.outlinePr.showOutlineSymbols = True

        print(f"[INFO] Writing {sheet_title} sheet...")

        # Temporarily swap pivot
        original_pivot = self.annual_pivot
        self.annual_pivot = pivot_df

        fiscal_columns = list(pivot_df.columns)
        start_row = 7
        is_df = self.df[self.df["type"] == "IS"]
        top_levels = is_df["top_level_grouping"].dropna().unique()
        current_row = start_row
        row_tracker = {}

        if mode == "annual":
            self._preallocate_percentage_columns(ws, fiscal_columns)

        for top in top_levels:
            current_row = self._write_top_level_grouping(
                ws, is_df, top, fiscal_columns, current_row, row_tracker, mode
            )
            top_key = top.strip().lower()
            current_row += 1

            if top_key == "cost of sales":
                current_row = self._insert_derived_row(
                    ws, "Gross Margin", fiscal_columns,
                    formula=lambda c: f"={get_column_letter(c)}{row_tracker['sales']}-{get_column_letter(c)}{row_tracker['cost of sales']}",
                    base_row=current_row,
                    row_tracker=row_tracker,
                    mode=mode,
                    sales_row=row_tracker.get("sales")
                )
                current_row += 1

            if top_key == "operating expenses":
                gross_row = row_tracker.get("gross margin")
                op_total_row = row_tracker.get("operating expenses")
                current_row = self._insert_derived_row(
                    ws, "Operating Margin", fiscal_columns,
                    formula=lambda c: f"={get_column_letter(c)}{gross_row}-{get_column_letter(c)}{op_total_row}",
                    base_row=current_row,
                    row_tracker=row_tracker,
                    mode=mode,
                    sales_row=row_tracker.get("sales")
                )
                current_row += 1

            if top_key == "other income/expenses":
                op_margin_row = row_tracker.get("operating margin")
                other_total_row = row_tracker.get("other income/expenses")
                current_row = self._insert_derived_row(
                    ws, "Net Income Before Taxes", fiscal_columns,
                    formula=lambda c: f"={get_column_letter(c)}{op_margin_row}-{get_column_letter(c)}{other_total_row}",
                    base_row=current_row,
                    row_tracker=row_tracker,
                    mode=mode,
                    sales_row=row_tracker.get("sales")
                )
                current_row += 1

            if top_key == "income taxes":
                before_tax_row = row_tracker.get("net income before taxes")
                tax_row = row_tracker.get("income taxes")
                current_row = self._insert_derived_row(
                    ws, "Net Income", fiscal_columns,
                    formula=lambda c: f"={get_column_letter(c)}{before_tax_row}-{get_column_letter(c)}{tax_row}",
                    base_row=current_row,
                    row_tracker=row_tracker,
                    mode=mode,
                    sales_row=row_tracker.get("sales")
                )
                current_row += 1

                # Add EBITDA Subcomponents and Total
                current_row, _ = self._write_ebitda_subcomponents(ws, row_tracker, current_row, len(fiscal_columns), mode)
                net_income_row = row_tracker.get("net income")
                ebitda_adj_row = current_row - 1
                current_row = self._insert_derived_row(
                    ws, "EBITDA", fiscal_columns,
                    formula=lambda c: f"={get_column_letter(c)}{net_income_row}+{get_column_letter(c)}{ebitda_adj_row}",
                    base_row=current_row,
                    row_tracker=row_tracker,
                    mode=mode,
                    sales_row=row_tracker.get("sales")
                )
                current_row += 1

        if mode == "annual":
            self._fill_percentage_formulas(ws, fiscal_columns, start_row)
        if mode in ["quarterly", "monthly"]:
            self._apply_column_widths(ws, mode, len(fiscal_columns))

        self._write_header(ws, fiscal_columns, mode)

        if mode == "annual":
            self._insert_delta_columns(ws, fiscal_columns, start_row)

        self._bold_top_level_rows(ws, start_row)

        for row in range(ws.min_row, ws.max_row + 1):
            if ws.row_dimensions[row].outlineLevel > 0:
                ws.row_dimensions[row].hidden = True
                ws.row_dimensions[row].collapsed = True

        # Restore original pivot
        self.annual_pivot = original_pivot


    def _insert_derived_row(self, ws, label, fiscal_columns, formula, base_row, row_tracker, mode, sales_row=None):
        ws.cell(row=base_row, column=1, value=label)
        ws.cell(row=base_row, column=1).font = self.bold_font
        ws.cell(row=base_row, column=1).alignment = Alignment(indent=0)

        for i, _ in enumerate(fiscal_columns):
            col_idx = self._get_col_idx(i, mode)
            formula_str = formula(col_idx)
            ws.cell(row=base_row, column=col_idx, value=formula_str)
            ws.cell(row=base_row, column=col_idx).number_format = self.currency_format
            ws.cell(row=base_row, column=col_idx).font = self.bold_font

        row_tracker[label.strip().lower()] = base_row
        next_row = base_row + 1

        # ⬇️ For non-annual: add inline % row
        if mode != "annual" and sales_row:
            self._insert_percentage_below_row(ws, base_row, label, sales_row, fiscal_columns, mode)
            next_row += 1

        return next_row

    def _insert_percentage_below_row(self, ws, label_row, label_text, sales_row, fiscal_columns, mode):
        pct_row = label_row + 1
        ws.insert_rows(pct_row)

        ws.cell(row=pct_row, column=1, value=f"{label_text} (%)")
        ws.cell(row=pct_row, column=1).font = self.italic_font
        ws.cell(row=pct_row, column=1).alignment = Alignment(indent=0)

        for i, _ in enumerate(fiscal_columns):
            col_idx = self._get_col_idx(i, mode)

            letter = get_column_letter(col_idx)
            formula = f"=IF(${letter}${sales_row}=0, 0, {letter}{label_row}/${letter}${sales_row})"

            cell = ws.cell(row=pct_row, column=col_idx)
            cell.value = formula
            cell.number_format = self.percent_format
            cell.font = self.arial_font

    def _apply_styles(self):
        """Apply column widths and freeze panes for Annual sheet."""
        ws = self.wb["Annual Income Statement"]

        # Column A = account labels
        ws.column_dimensions["A"].width = 40

        num_fiscal = len(self.annual_pivot.columns)
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
    
    def _apply_column_widths(self, ws, mode, num_columns):
        """Set column widths for quarterly/monthly uniformly."""
        if mode == "annual":
            return  # Handled separately
        ws.column_dimensions["A"].width = 40
        for i in range(num_columns):
            col_idx = 2 + i
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = 12
            
    def _preallocate_percentage_columns(self, ws, fiscal_columns):
        """Inserts empty % columns next to each value column before any data is written."""
        print("[INFO] Pre-allocating % of total columns...")
        for i in range(len(fiscal_columns)):
            pct_col = 2 + i * 2 + 1
            ws.insert_cols(pct_col)
            ws.column_dimensions[get_column_letter(pct_col)].width = 7  # Optional: width for % columns
    
    def _fill_percentage_formulas(self, ws, fiscal_columns, start_row):
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
                pct_cell.number_format = self.percent_format

    def _finalize_file(self):
        """Save the Excel file with cleanup of ghost columns."""
        print("[INFO] Saving workbook...")
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        from openpyxl.utils import get_column_letter

        # Get the worksheet
        ws = self.wb["Annual Income Statement"]

        # Clear extra ghost columns beyond J (col 10)
       # self._clear_extra_columns(ws, start_col=11)
        
        # Save workbook
        from openpyxl.utils import get_column_letter

        num_fiscal = len(self.annual_pivot.columns)
        spacer_col = 2 + num_fiscal * 2
        spacer_letter = get_column_letter(spacer_col)
        self.wb["Annual Income Statement"].column_dimensions[spacer_letter].width = 4

        self.wb.save(self.output_path)

        print(f"[SUCCESS] File saved at: {self.output_path}")

    def _write_header(self, ws: Worksheet, column_labels: list, mode: str = "annual"):
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
            f"Year End: {self.fiscal_year_end.strftime('%B %d')}"
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
    
    def _get_col_idx(self, i: int, mode: str = "annual") -> int:
        return 2 + i * 2 if mode == "annual" else 2 + i

    def _insert_delta_columns(self, ws: Worksheet, fiscal_columns: list, start_data_row: int):
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

        # ➤ Don't insert cols anymore — just write directly to them (they are preallocated in _write_header)

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
        self._write_all_delta_formulas(ws, start_data_row)

    def _insert_percentage_of_total_columns(self, ws: Worksheet, fiscal_columns: list, start_data_row: int):
        """Insert % of total (e.g., % of sales) columns next to each fiscal column."""
        if not fiscal_columns:
            return
        print("[INFO] Inserting % of Total columns...")

        num_fiscal = len(fiscal_columns)
        percentage_cols = []  # Track new columns inserted

        for i, col_name in enumerate(fiscal_columns):
            # Where to insert % column (every other one, after col B = idx+2)
            insert_idx = 2 + i * 2 + 1
            ws.insert_cols(insert_idx)

            percentage_cols.append(insert_idx)

        # Determine the row number where "Sales" total is located
        sales_label_row = None
        for row in range(start_data_row, ws.max_row + 1):
            if str(ws.cell(row=row, column=1).value).strip().lower() == "sales":
                sales_label_row = row
                break

        if sales_label_row is None:
            print("[WARNING] Could not find 'Sales' row for percentage calculation.")
            return

        # Now loop again to apply formulas to all rows
        for row in range(start_data_row, ws.max_row + 1):
            # Skip blank or non-numeric rows
            if ws.cell(row=row, column=1).value is None:
                continue

            for i in range(num_fiscal):
                value_col = 2 + i * 2  # actual value col
                pct_col = value_col + 1

                value_letter = get_column_letter(value_col)
                sales_value = ws[f"{value_letter}{sales_label_row}"].value  # Get sales cell value directly

                if not sales_value or abs(sales_value) < 1e-6:
                    ws.cell(row=row, column=pct_col).value = 0
                else:
                    ws.cell(row=row, column=pct_col).value = f"={value_letter}{row}/${value_letter}${sales_label_row}"

                ws.cell(row=row, column=pct_col).number_format = self.percent_format

    def _clear_extra_columns(self, ws: Worksheet, start_col: int):
        """Safely clears content and styles from non-merged cells beyond start_col."""
        from openpyxl.cell.cell import Cell  # ensure correct type check

        # Create a set of merged cell coordinates to skip
        merged_coords = set()
        for merged_range in ws.merged_cells.ranges:
            merged_coords.update(merged_range.cells)

        for col in range(start_col, ws.max_column + 1):
            for row in range(1, ws.max_row + 1):
                cell = ws.cell(row=row, column=col)

                # Skip merged cells (only process the top-left cell of merged region)
                if (row, col) in merged_coords:
                    continue

                if isinstance(cell, Cell):
                    cell.value = None
                    cell.fill = PatternFill(fill_type=None)
                    cell.border = Border()
                    cell.font = Font(name="Arial", size=10)

    def _bold_top_level_rows(self, ws: Worksheet, start_data_row: int):
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
                    ws.cell(row=row, column=col).font = self.bold_font

    from openpyxl.utils import get_column_letter
    
    def _write_all_delta_formulas(self, ws: Worksheet, start_data_row: int):
        """Applies Δ and Δ% formulas across the worksheet after all values are written."""
        num_fiscal = len(self.annual_pivot.columns)
        if num_fiscal < 2:
            return

        prev_val_col = 2 + (num_fiscal - 2) * 2
        curr_val_col = 2 + (num_fiscal - 1) * 2
        spacer_col = 2 + num_fiscal * 2
        delta_col = spacer_col + 1
        delta_pct_col = delta_col + 1

        prev_letter = get_column_letter(prev_val_col)
        curr_letter = get_column_letter(curr_val_col)
        delta_letter = get_column_letter(delta_col)
        delta_pct_letter = get_column_letter(delta_pct_col)

        print("[INFO] Writing delta formulas row-by-row...")
        for row in range(start_data_row, ws.max_row + 1):
            label = ws.cell(row=row, column=1).value
            if not label or str(label).strip() == "":
                continue

            # Δ value
            delta_cell = ws.cell(row=row, column=delta_col)
            delta_cell.value = f"={curr_letter}{row}-{prev_letter}{row}"
            delta_cell.number_format = self.currency_format
            delta_cell.alignment = Alignment(horizontal="center")

            # Δ %
            delta_pct_cell = ws.cell(row=row, column=delta_pct_col)
            delta_pct_cell.value = f"=IF({prev_letter}{row}=0,0,({curr_letter}{row}/{prev_letter}{row})-1)"
            delta_pct_cell.number_format = self.percent_format
            delta_pct_cell.alignment = Alignment(horizontal="center")

    def _insert_derived_totals(self, ws: Worksheet, fiscal_columns: list, row_tracker: dict, current_row: int, mode: str) -> int:
        def make_formula(col_idx, row1, row2, op='-'):
            col_letter = get_column_letter(col_idx)
            return f"={col_letter}{row1}{op}{col_letter}{row2}"

        num_fiscal = len(fiscal_columns)
        
        for label, formula_func in [
            ("Gross margin", lambda c: make_formula(c, row_tracker["sales"], row_tracker["cost of sales"])),
            ("Operating margin", lambda c: make_formula(c, current_row - 1, row_tracker["operating expenses"])),
            ("Net income before taxes", lambda c: make_formula(c, current_row - 1, row_tracker["other income/expenses"])),
            ("Net income", lambda c: make_formula(c, current_row - 1, row_tracker["income taxes"])),
            ("EBITDA", lambda c: (
                f"={get_column_letter(c)}{row_tracker.get('net income', 0)}"
                f"+{get_column_letter(c)}{row_tracker.get('amortization', 0)}"
                f"+{get_column_letter(c)}{row_tracker.get('interest expense', 0)}"
                f"+{get_column_letter(c)}{row_tracker.get('income taxes', 0)}"
            )),
        ]:
            if label.lower() == "net income":
                row_tracker["net income"] = current_row
            
            if label == "EBITDA":
                current_row, eb_sub_rows = self._write_ebitda_subcomponents(ws, row_tracker, current_row, num_fiscal, mode)
                print(f"[DEBUG][EBITDA] EBITDA formula for col {col_idx} → {formula}")

            ws.cell(row=current_row, column=1, value=label).font = self.bold_font
            ws.cell(row=current_row, column=1).alignment = Alignment(indent=0)

            # Write values for fiscal columns
            for i in range(num_fiscal):
                col_idx = self._get_col_idx(i, mode)
                if label == "EBITDA":
                    subtotal_row = current_row - 1  
                    net_income_row = row_tracker.get("net income")

                    if net_income_row:
                        formula = (
                            f"={get_column_letter(col_idx)}{net_income_row}"
                            f"+{get_column_letter(col_idx)}{subtotal_row}"
                        )
                    
                    else:
                        formula = f"={get_column_letter(col_idx)}{subtotal_row}" 
                    print(f"[DEBUG][EBITDA] col {get_column_letter(col_idx)} → net_income_row: {net_income_row}, subtotal_row (adjustments): {subtotal_row}")

                else:
                    formula = formula_func(col_idx)
                    

                cell = ws.cell(row=current_row, column=col_idx)
                
                cell.value = formula
                cell.font = self.bold_font
                cell.number_format = self.currency_format

                pct_col_idx = col_idx + 1
                sales_row = row_tracker["sales"]

                value_letter = get_column_letter(col_idx)
                sales_letter = get_column_letter(col_idx)

                pct_cell = ws.cell(row=current_row, column=pct_col_idx)
                sales_value = ws[f"{sales_letter}{sales_row}"].value

                if sales_value == 0 or sales_value is None:
                    pct_cell.value = 0  # or "-" if you prefer
                else:
                    pct_cell.value = f"={value_letter}{current_row}/${sales_letter}${sales_row}"

                pct_cell.number_format = "0%"
                pct_cell.number_format = self.percent_format
                pct_cell.font = self.bold_font


            # --- Add Δ and Δ% columns if possible ---
            if num_fiscal >= 2:
                prev_val_col = 2 + (num_fiscal - 2) * 2
                curr_val_col = 2 + (num_fiscal - 1) * 2
                spacer_col = 2 + num_fiscal * 2
                delta_col = spacer_col + 1
                delta_pct_col = delta_col + 1

                row_num = current_row
                prev_letter = get_column_letter(prev_val_col)
                curr_letter = get_column_letter(curr_val_col)
                delta_letter = get_column_letter(delta_col)
                delta_pct_letter = get_column_letter(delta_pct_col)

                # Δ value formula
    # Get formula strings from the source cells
                prev_formula = ws[f"{prev_letter}{row_num}"].value
                curr_formula = ws[f"{curr_letter}{row_num}"].value

                is_valid_formula = (
                    isinstance(prev_formula, str) and prev_formula.strip().startswith("=") and
                    isinstance(curr_formula, str) and curr_formula.strip().startswith("=")
                )

                # Δ value
                delta_cell = ws[f"{delta_letter}{row_num}"]
                if is_valid_formula:
                    delta_cell.value = f"={curr_letter}{row_num}-{prev_letter}{row_num}"
                else:
                    delta_cell.value = "-"
                delta_cell.number_format = self.currency_format
                delta_cell.font = self.bold_font
                delta_cell.alignment = Alignment(horizontal="center")

                # Δ %
                delta_pct_cell = ws[f"{delta_pct_letter}{row_num}"]
                if is_valid_formula:
                    delta_pct_cell.value = f"=({curr_letter}{row_num}/{prev_letter}{row_num})-1"
                else:
                    delta_pct_cell.value = "-"
            delta_pct_cell.number_format = self.percent_format
            delta_pct_cell.font = self.bold_font
            delta_pct_cell.alignment = Alignment(horizontal="center")

            current_row += 1

        return current_row


    def _write_ebitda_subcomponents(self, ws: Worksheet, row_tracker: dict, start_row: int, num_fiscal: int, mode: str) -> tuple[int, dict]:
        """
        Write EBITDA components (excluding Net Income) as level 2 rows,
        and return a dict mapping fiscal column index → row numbers of the subcomponents.
        """
        subcomponents = ["Amortization", "Interest expense", "Income taxes"]
        subcomponent_rows = {}  

        for i in range(num_fiscal):
            col_idx = self._get_col_idx(i, mode)
            if col_idx not in subcomponent_rows:
                subcomponent_rows[col_idx] = []
        for label in subcomponents:
            key = label.strip().lower()
            source_row = row_tracker.get(key)
            if not source_row:
                continue

            ws.cell(row=start_row, column=1, value=label)
            ws.cell(row=start_row, column=1).font = self.arial_font
            ws.cell(row=start_row, column=1).alignment = Alignment(indent=1)

            for i in range(num_fiscal):
                col_idx = self._get_col_idx(i, mode)
                pct_col_idx = col_idx + 1

                if col_idx not in subcomponent_rows:
                    subcomponent_rows[col_idx] = []
                subcomponent_rows[col_idx].append(start_row)

                # Reference original value row (source_row)
                ws.cell(row=start_row, column=col_idx).value = f"={get_column_letter(col_idx)}{source_row}"
                ws.cell(row=start_row, column=col_idx).number_format = self.currency_format
                ws.cell(row=start_row, column=col_idx).font = self.arial_font

                # % of Sales
                sales_row = row_tracker.get("sales")
                if sales_row:
                    ws.cell(row=start_row, column=pct_col_idx).value = (
                        f"={get_column_letter(col_idx)}{start_row}/${get_column_letter(col_idx)}${sales_row}"
                    )
                    ws.cell(row=start_row, column=pct_col_idx).number_format = self.percent_format
                    ws.cell(row=start_row, column=pct_col_idx).font = self.arial_font

            ws.row_dimensions[start_row].outlineLevel = 2
            ws.row_dimensions[start_row].hidden = True
            start_row += 1

        subtotal_row = start_row
        ws.cell(row=subtotal_row, column=1, value="total")
        ws.cell(row=subtotal_row, column=1).font = self.italic_font
        ws.cell(row=subtotal_row, column=1).alignment = Alignment(indent=1)

        for i in range(num_fiscal):
            col_idx = 2 + i * 2
            pct_col_idx = col_idx + 1

            row_nums = subcomponent_rows.get(col_idx, [])
            if row_nums:
                formula = "+".join([f"{get_column_letter(col_idx)}{r}" for r in row_nums])
                formula = f"={formula}"
            else:
                formula = "=0"

            ws.cell(row=subtotal_row, column=col_idx).value = formula
            ws.cell(row=subtotal_row, column=col_idx).number_format = self.currency_format
            ws.cell(row=subtotal_row, column=col_idx).font = self.bold_font

            sales_row = row_tracker.get("sales")
            if sales_row:
                ws.cell(row=subtotal_row, column=pct_col_idx).value = (
                    f"={get_column_letter(col_idx)}{subtotal_row}/${get_column_letter(col_idx)}${sales_row}"
                )
            else:
                ws.cell(row=subtotal_row, column=pct_col_idx).value = 0

            ws.cell(row=subtotal_row, column=pct_col_idx).number_format = self.percent_format
            ws.cell(row=subtotal_row, column=pct_col_idx).font = self.bold_font

        ws.row_dimensions[subtotal_row].outlineLevel = 2
        ws.row_dimensions[subtotal_row].hidden = True

        start_row += 1  # For the main EBITDA row next
        return start_row, subcomponent_rows

