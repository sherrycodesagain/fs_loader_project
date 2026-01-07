import pandas as pd
from datetime import datetime, timedelta
from utils.period_utils import get_fiscal_year, safe_date
from cache.memory_store import memory_store
from config import (
    COMPANY_NAME, CURRENCY, DENOMINATION,
    CURRENT_DATE_INPUT, DEFAULT_FISCAL_YEAR_END, FS_DATASET_ID
)
from utils.csv_converter import CSVConverter

class FSAccountLoader:
    # def __init__(self, tb_path: str, coa_path: str, dataset_id: str = FS_DATASET_ID):
    #     self.tb_path = tb_path
    #     self.coa_path = coa_path
    #     self.dataset_id = dataset_id
    #     self.df = None
    #     self.current_date = pd.to_datetime(CURRENT_DATE_INPUT)
    #     self.fiscal_year_end = pd.to_datetime(DEFAULT_FISCAL_YEAR_END)
    #     self.fiscal_month = self.fiscal_year_end.month
    #     self.fiscal_day = self.fiscal_year_end.day
    #     self.fiscal_month_start = (self.fiscal_month % 12) + 1

    def __init__(self, tb_path: str, coa_path: str, dataset_id: str = FS_DATASET_ID, use_csv_cache: bool = False):
        self.tb_path = tb_path
        self.coa_path = coa_path
        self.dataset_id = dataset_id
        # ADD THESE LINES
        self.use_csv_cache = use_csv_cache
        self.csv_converter = CSVConverter() if use_csv_cache else None
        # ...existing code...
        self.df = None
        self.current_date = pd.to_datetime(CURRENT_DATE_INPUT)
        self.fiscal_year_end = pd.to_datetime(DEFAULT_FISCAL_YEAR_END)
        self.fiscal_month = self.fiscal_year_end.month
        self.fiscal_day = self.fiscal_year_end.day
        self.fiscal_month_start = (self.fiscal_month % 12) + 1


    def load_and_store(self):
        self._load_and_merge()
        self._clean_and_transform()
        self._tag_basic_periods()
        self._exclude_incomplete_fiscal_years()
        self._assign_period_column()
        self._finalize()

        def determine_period_label(row):
            if row["ytd"]:
                return row["ytd"]
            if row["ltm"]:
                return row["ltm"]
            if row["fiscal_year"] in self.valid_fys:
                return row["fiscal_year"]
            return ""

        self.df["period_label"] = self.df.apply(determine_period_label, axis=1)

        # month_to_quarter = {}
        # for _, row in self.df.iterrows():
        #     month = row.get("month")
        #     quarter = row.get("fiscal_quarter")
        #     if isinstance(month, str) and isinstance(quarter, str):
        #         month_to_quarter[month] = quarter
        #with vector now below
        
        valid_mapping = self.df.dropna(subset=["month", "fiscal_quarter"])
        month_to_quarter = dict(zip(valid_mapping["month"], valid_mapping["fiscal_quarter"]))
                
        memory_store[self.dataset_id] = {
            "enriched_df": self.df,
            "filters": self._extract_filter_metadata(),
            "chart_cache": {},
            "period_ranges": self._build_period_ranges(),
            "valid_fiscal_years": self.valid_fys,
            "fiscal_year_end": self.fiscal_year_end,
            "month_to_quarter": month_to_quarter,
            "waterfall_periods": self._build_waterfall_periods()
        }

    def _finalize(self):
        self.df = self.df.rename(columns=lambda col: col.strip())
        self.df.fillna("", inplace=True)
        for col in ["account", "account_name", "top_level_grouping", "fs_grouping", "detailed_grouping"]:
            if col in self.df.columns:
                self.df[col] = self.df[col].apply(lambda x: str(x).strip() if isinstance(x, str) else x)
        self.df["company"] = COMPANY_NAME
        self.df["denomination"] = DENOMINATION
        self.df["dataset_id"] = self.dataset_id

    def _tag_basic_periods(self):
        self.df["fiscal_quarter"] = self.df["date"].apply(self._get_fiscal_quarter)
        self.df["ytd"] = self.df["date"].apply(self._assign_ytd)
        self.df["ltm"] = self.df["date"].apply(self._assign_ltm)

    # def _load_and_merge(self):
    #     tb_df = pd.read_excel(self.tb_path)
    #     coa_df = pd.read_excel(self.coa_path)

    #     tb_melted = pd.melt(tb_df, id_vars=["Account #", "Account Name"], var_name="date", value_name="ending_balance")
    #     tb_melted["date"] = pd.to_datetime(tb_melted["date"])
    #     tb_melted = tb_melted.drop_duplicates(subset=["Account #", "date"])
    #     merged = pd.merge(tb_melted, coa_df, on="Account #", how="left")

    #     if "Account Name_x" in merged.columns:
    #         merged["account_name"] = merged["Account Name_x"]
    #         merged.drop(columns=["Account Name_x", "Account Name_y"], inplace=True, errors="ignore")
    #     else:
    #         merged["account_name"] = merged["Account Name"]

    #     merged["account"] = merged["Account #"].astype(str) + " - " + merged["account_name"]
    #     self.df = merged.rename(columns=lambda x: x.strip().lower().replace(" ", "_"))


    def _load_and_merge(self):
        # NEW: Add CSV optimization option
        if self.use_csv_cache:
            print(" Using CSV optimization for faster loading...")
            tb_csv, coa_csv = self.csv_converter.get_csv_paths(self.tb_path, self.coa_path)
            tb_df = pd.read_csv(tb_csv)
            coa_df = pd.read_csv(coa_csv)
        else:
            # Original Excel loading (unchanged)
            tb_df = pd.read_excel(self.tb_path)
            coa_df = pd.read_excel(self.coa_path)

        # Everything below stays exactly the same
        tb_melted = pd.melt(tb_df, id_vars=["Account #", "Account Name"], var_name="date", value_name="ending_balance")
        tb_melted["date"] = pd.to_datetime(tb_melted["date"])
        tb_melted = tb_melted.drop_duplicates(subset=["Account #", "date"])
        merged = pd.merge(tb_melted, coa_df, on="Account #", how="left")

        if "Account Name_x" in merged.columns:
            merged["account_name"] = merged["Account Name_x"]
            merged.drop(columns=["Account Name_x", "Account Name_y"], inplace=True, errors="ignore")
        else:
            merged["account_name"] = merged["Account Name"]

        merged["account"] = merged["Account #"].astype(str) + " - " + merged["account_name"]
        self.df = merged.rename(columns=lambda x: x.strip().lower().replace(" ", "_"))



    def _clean_and_transform(self):
        self.df["date"] = pd.to_datetime(self.df["date"])
        self.df["month"] = self.df["date"].dt.strftime("%B %Y")
        self.df["fiscal_year"] = self.df["date"].apply(lambda d: f"F{get_fiscal_year(d, self.fiscal_month, self.fiscal_day)}")
        self.df["is_original_row"] = True
        self.df["xl_row_id"] = self.df.index

        sign_fix = ["Sales", "Current liabilities", "Long term liabilities", "Equity"]
        self.df.loc[self.df["top_level_grouping"].isin(sign_fix), "ending_balance"] *= -1
        self._fill_missing_detailed_grouping()

    # def _fill_missing_detailed_grouping(self):
    #     for group in self.df["fs_grouping"].dropna().unique():
    #         mask = self.df["fs_grouping"] == group
    #         if self.df.loc[mask, "detailed_grouping"].notna().any():
    #             self.df.loc[mask & self.df["detailed_grouping"].isna(), "detailed_grouping"] = f"Other {group}"
    # without for loop below:
    def _fill_missing_detailed_grouping(self):
        
        groups_with_detailed = self.df.groupby("fs_grouping")["detailed_grouping"].apply(lambda x: x.notna().any())
        valid_groups = groups_with_detailed[groups_with_detailed].index
        
        mask = (self.df["fs_grouping"].isin(valid_groups) & 
                self.df["detailed_grouping"].isna())
        self.df.loc[mask, "detailed_grouping"] = "Other " + self.df.loc[mask, "fs_grouping"]            

    def _assign_period_column(self):
        self.df["is_ytd"] = self.df["ytd"].str.strip().astype(bool)
        self.df["is_ltm"] = self.df["ltm"].str.strip().astype(bool)
        self.df["is_fy"] = self.df["fiscal_year"].isin(self.valid_fys)
        self.df["quarter_ytd"] = self.df.apply(lambda row: self._get_quarter_period(row["date"], row["ytd"]), axis=1)
        self.df["quarter_ltm"] = self.df.apply(lambda row: self._get_quarter_period(row["date"], row["ltm"]), axis=1)

    def _get_fiscal_quarter(self, date):
        offset = (date.month - self.fiscal_month_start + 12) % 12
        quarter = (offset // 3) + 1
        fy = get_fiscal_year(date, self.fiscal_month, self.fiscal_day)
        return f"Q{quarter} F{fy}"

    def _assign_ytd(self, date):
        fy = get_fiscal_year(self.current_date, self.fiscal_month, self.fiscal_day)
        start = safe_date(fy - 1, self.fiscal_month, self.fiscal_day) + timedelta(days=1)
        return f"YTD F{fy}" if start <= date <= self.current_date else ""

    def _assign_ltm(self, date):
        start = self.current_date - pd.DateOffset(years=1) + timedelta(days=1)
        return f"LTM {self.current_date.strftime('%b %Y')}" if start <= date <= self.current_date else ""

    def _assign_period(self, row):
        date = row["date"]
        fy = f"F{get_fiscal_year(date, self.fiscal_month, self.fiscal_day)}"
        current_fy = get_fiscal_year(self.current_date, self.fiscal_month, self.fiscal_day)
        fiscal_start = datetime(current_fy - 1, self.fiscal_month, self.fiscal_day) + timedelta(days=1)
        ltm_start = self.current_date - pd.DateOffset(years=1) + timedelta(days=1)

        periods = []
        if fiscal_start <= date <= self.current_date:
            periods.append(f"YTD F{current_fy}")
        if ltm_start <= date <= self.current_date:
            periods.append(f"LTM {self.current_date.strftime('%b %Y')}")
        if fy in self.valid_fys:
            periods.append(fy)
        return periods if periods else None

    def _get_quarter_period(self, date, period):
        if not isinstance(period, str) or not period:
            return ""

        def relative_quarter(d, start):
            offset = (d.year - start.year) * 12 + (d.month - start.month)
            return f"Q{(offset // 3) + 1}" if 0 <= offset <= 11 else ""

        if period.startswith("LTM"):
            start = self.current_date - pd.DateOffset(years=1) + timedelta(days=1)
        elif period.startswith("YTD"):
            fy = get_fiscal_year(self.current_date, self.fiscal_month, self.fiscal_day)
            start = safe_date(fy - 1, self.fiscal_month, self.fiscal_day) + timedelta(days=1)
        else:
            return ""

        return f"{relative_quarter(date, start)} {period}"

    def _exclude_incomplete_fiscal_years(self):
        grouped = (
            self.df[self.df["fiscal_year"].str.match(r"^F\d{4}$")]
            .groupby("fiscal_year")["month"]
            .nunique()
        )
        self.valid_fys = grouped[grouped == 12].index.tolist()
        self.df = self.df[
            self.df["fiscal_year"].isin(self.valid_fys) |
            self.df["ytd"].str.strip().astype(bool)
        ]
    def _build_waterfall_periods(self):
        """Build valid waterfall transitions from available periods dynamically."""
        periods = {}
        valid_fys = sorted(self.valid_fys)  # ensure chronological order
        ltm_labels = sorted(self.df["ltm"].dropna().unique().tolist(), key=lambda l: self.df[self.df["ltm"] == l]["date"].max())

        # Add FY to FY transitions (e.g. F2022 to F2023)
        for i in range(len(valid_fys) - 1):
            start = valid_fys[i]
            end = valid_fys[i + 1]
            periods[f"{start} to {end}"] = (start, end)

        # Add FY to LTM transition if last FY and LTM overlap
        if valid_fys and ltm_labels:
            last_fy = valid_fys[-1]
            latest_ltm = ltm_labels[-1]
            # Check if LTM has entries later than last FY
            latest_ltm_date = self.df[self.df["ltm"] == latest_ltm]["date"].max()
            last_fy_end = self.df[self.df["fiscal_year"] == last_fy]["date"].max()
            if latest_ltm_date > last_fy_end:
                periods[f"{last_fy} to {latest_ltm}"] = (last_fy, latest_ltm)

        return periods


    def _determine_period_label(self, row):
        if row["ytd"]:
            return row["ytd"]
        if row["ltm"]:
            return row["ltm"]
        if row["fiscal_year"] in self.valid_fys:
            return row["fiscal_year"]
        return ""

    def _extract_filter_metadata(self):
        filters = {}
        for field in [
            "account", "account_name", "top_level_grouping", "fs_grouping", "detailed_grouping",
            "month", "fiscal_year", "fiscal_quarter", "ytd", "ltm",
            "quarter_ytd", "quarter_ltm", "period_label"
        ]:
            if field in self.df.columns:
                filters[field] = sorted([
                    p for p in self.df[field].dropna().unique().tolist() if str(p).strip()
                ])
        return filters
    
    
    def _build_period_ranges(self):
        period_ranges = {}

        def extract_range(label, date_mask):
            months = self.df[date_mask]["month"].dropna().unique().tolist()
            dates = self.df[date_mask]["date"]
            if not dates.empty:
                return {
                    "start": dates.min().normalize(),
                    "end": dates.max().normalize(),
                    "months": sorted(months, key=lambda x: pd.to_datetime(x))
                }
            return None

        for fy in self.valid_fys:
            mask = self.df["fiscal_year"] == fy
            result = extract_range(fy, mask)
            if result:
                period_ranges[fy] = result

        for tag in self.df["ytd"].dropna().unique():
            if tag.strip():
                mask = self.df["ytd"] == tag
                result = extract_range(tag, mask)
                if result:
                    period_ranges[tag] = result

        for tag in self.df["ltm"].dropna().unique():
            if tag.strip():
                mask = self.df["ltm"] == tag
                result = extract_range(tag, mask)
                if result:
                    period_ranges[tag] = result

        return period_ranges
    
    # #################### written by shehryar below ####################

    # def filter_income_statement_accounts(self):
    #     """Filter for only accounts with Type 'IS' (Income Statement)"""
    #     original_count = len(self.df)
        
    #     if 'type' in self.df.columns:
    #         # Filter for Income Statement accounts
    #         self.df = self.df[self.df['type'].str.upper() == 'IS'].copy()
    #         filtered_count = len(self.df)
    #         print(f"✅ Filtered to Income Statement accounts: {filtered_count:,} records (removed {original_count - filtered_count:,})")
    #     else:
    #         # If no 'type' column, check if we have other indicators
    #         if 'top_level_grouping' in self.df.columns:
    #             # Filter for typical IS categories
    #             is_categories = ['Sales', 'Revenue', 'Income', 'Expense', 'Cost', 'Operating']
    #             mask = self.df['top_level_grouping'].str.contains('|'.join(is_categories), case=False, na=False)
    #             self.df = self.df[mask].copy()
    #             filtered_count = len(self.df)
    #             print(f"⚠️ No 'type' column found. Filtered by top_level_grouping: {filtered_count:,} records (removed {original_count - filtered_count:,})")
    #         else:
    #             print("⚠️ Warning: No 'type' column found and unable to determine IS accounts. Using all accounts.")
    #             print(f"📊 Total accounts: {original_count:,}")
        
    #     if len(self.df) == 0:
    #         print("❌ Warning: No Income Statement accounts found after filtering!")

    # def create_annual_income_statement(self):
    #     """Create aggregated annual income statement with fiscal years, LTM, and YTD"""
    #     # Group by account and fiscal year, sum the ending balances
    #     annual_pivot = self.df.groupby(['account', 'account_name', 'top_level_grouping', 
    #                                 'fs_grouping', 'detailed_grouping', 'fiscal_year'])['ending_balance'].sum().reset_index()
        
    #     # Pivot to get fiscal years as columns
    #     annual_is = annual_pivot.pivot_table(
    #         index=['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping'],
    #         columns='fiscal_year',
    #         values='ending_balance',
    #         fill_value=0
    #     ).reset_index()
        
    #     # Add LTM column
    #     ltm_data = self.df[self.df['ltm'].str.strip().astype(bool)].groupby(
    #         ['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping']
    #     )['ending_balance'].sum().reset_index()
    #     ltm_data = ltm_data.rename(columns={'ending_balance': f'LTM {self.current_date.strftime("%b %Y")}'})
        
    #     # Add YTD column
    #     ytd_data = self.df[self.df['ytd'].str.strip().astype(bool)].groupby(
    #         ['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping']
    #     )['ending_balance'].sum().reset_index()
    #     current_fy = f"F{get_fiscal_year(self.current_date, self.fiscal_month, self.fiscal_day)}"
    #     ytd_data = ytd_data.rename(columns={'ending_balance': f'YTD {current_fy}'})
        
    #     # Merge LTM and YTD data
    #     annual_is = annual_is.merge(ltm_data, on=['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping'], how='left')
    #     annual_is = annual_is.merge(ytd_data, on=['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping'], how='left')
        
    #     # Fill NaN values with 0
    #     annual_is = annual_is.fillna(0)
        
    #     return annual_is

    # def create_quarterly_income_statement(self):
    #     """Create aggregated quarterly income statement (no LTM/YTD)"""
    #     # Group by account and fiscal quarter, sum the ending balances
    #     quarterly_pivot = self.df.groupby(['account', 'account_name', 'top_level_grouping', 
    #                                     'fs_grouping', 'detailed_grouping', 'fiscal_quarter'])['ending_balance'].sum().reset_index()
        
    #     # Pivot to get fiscal quarters as columns
    #     quarterly_is = quarterly_pivot.pivot_table(
    #         index=['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping'],
    #         columns='fiscal_quarter',
    #         values='ending_balance',
    #         fill_value=0
    #     ).reset_index()
        
    #     return quarterly_is

    # def create_monthly_income_statement(self):
    #     """Create aggregated monthly income statement (no LTM/YTD)"""
    #     # Group by account and month, sum the ending balances
    #     monthly_pivot = self.df.groupby(['account', 'account_name', 'top_level_grouping', 
    #                                     'fs_grouping', 'detailed_grouping', 'month'])['ending_balance'].sum().reset_index()
        
    #     # Pivot to get months as columns
    #     monthly_is = monthly_pivot.pivot_table(
    #         index=['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping'],
    #         columns='month',
    #         values='ending_balance',
    #         fill_value=0
    #     ).reset_index()
        
    #     # Sort month columns chronologically
    #     month_cols = [col for col in monthly_is.columns if col not in ['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping']]
    #     sorted_month_cols = sorted(month_cols, key=lambda x: pd.to_datetime(x))
        
    #     # Reorder columns
    #     base_cols = ['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping']
    #     monthly_is = monthly_is[base_cols + sorted_month_cols]
        
    #     return monthly_is

    # def export_income_statements_to_excel(self, output_path: str):
    #     """Export annual, quarterly, and monthly income statements to Excel with proper formatting"""
    #     from datetime import datetime
    #     import os
        
    #     # Create output directory if it doesn't exist
    #     os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
    #     # Filter for Income Statement accounts first
    #     self.filter_income_statement_accounts()
        
    #     # Create the three statement types
    #     annual_is = self.create_annual_income_statement()
    #     quarterly_is = self.create_quarterly_income_statement()
    #     monthly_is = self.create_monthly_income_statement()
        
    #     # Export to Excel with multiple sheets
    #     with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
    #         # Get the workbook and add formats
    #         workbook = writer.book
            
    #         # Define formats
    #         header_format = workbook.add_format({
    #             'bold': True,
    #             'text_wrap': True,
    #             'valign': 'top',
    #             'fg_color': '#D9E1F2',
    #             'border': 1
    #         })
            
    #         currency_format = workbook.add_format({
    #             'num_format': '#,##0',
    #             'border': 1
    #         })
            
    #         # Annual Income Statement
    #         annual_is.to_excel(writer, sheet_name='Annual_Income_Statement', index=False)
    #         worksheet_annual = writer.sheets['Annual_Income_Statement']
            
    #         # Apply formatting to annual sheet
    #         for col_num, value in enumerate(annual_is.columns.values):
    #             worksheet_annual.write(0, col_num, value, header_format)
                
    #         # Format currency columns (exclude text columns)
    #         text_cols = ['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping']
    #         for col_num, col_name in enumerate(annual_is.columns):
    #             if col_name not in text_cols:
    #                 worksheet_annual.set_column(col_num, col_num, 15, currency_format)
    #             else:
    #                 worksheet_annual.set_column(col_num, col_num, 25)
            
    #         # Quarterly Income Statement
    #         quarterly_is.to_excel(writer, sheet_name='Quarterly_Income_Statement', index=False)
    #         worksheet_quarterly = writer.sheets['Quarterly_Income_Statement']
            
    #         # Apply formatting to quarterly sheet
    #         for col_num, value in enumerate(quarterly_is.columns.values):
    #             worksheet_quarterly.write(0, col_num, value, header_format)
                
    #         for col_num, col_name in enumerate(quarterly_is.columns):
    #             if col_name not in text_cols:
    #                 worksheet_quarterly.set_column(col_num, col_num, 15, currency_format)
    #             else:
    #                 worksheet_quarterly.set_column(col_num, col_num, 25)
            
    #         # Monthly Income Statement
    #         monthly_is.to_excel(writer, sheet_name='Monthly_Income_Statement', index=False)
    #         worksheet_monthly = writer.sheets['Monthly_Income_Statement']
            
    #         # Apply formatting to monthly sheet
    #         for col_num, value in enumerate(monthly_is.columns.values):
    #             worksheet_monthly.write(0, col_num, value, header_format)
                
    #         for col_num, col_name in enumerate(monthly_is.columns):
    #             if col_name not in text_cols:
    #                 worksheet_monthly.set_column(col_num, col_num, 12, currency_format)
    #             else:
    #                 worksheet_monthly.set_column(col_num, col_num, 25)
            
    #         # Add summary sheet
    #         summary_data = {
    #             'Statement_Type': ['Annual', 'Quarterly', 'Monthly'],
    #             'Account_Count': [len(annual_is), len(quarterly_is), len(monthly_is)],
    #             'Period_Columns': [
    #                 len([c for c in annual_is.columns if c not in text_cols]),
    #                 len([c for c in quarterly_is.columns if c not in text_cols]),
    #                 len([c for c in monthly_is.columns if c not in text_cols])
    #             ],
    #             'Export_Date': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] * 3
    #         }
            
    #         summary_df = pd.DataFrame(summary_data)
    #         summary_df.to_excel(writer, sheet_name='Export_Summary', index=False)
            
    #         # Format summary sheet
    #         worksheet_summary = writer.sheets['Export_Summary']
    #         for col_num, value in enumerate(summary_df.columns.values):
    #             worksheet_summary.write(0, col_num, value, header_format)
    #             worksheet_summary.set_column(col_num, col_num, 20)
        
    #     print(f"✅ Income statements exported to: {output_path}")
    #     print(f"📊 Annual IS: {len(annual_is)} accounts")
    #     print(f"📊 Quarterly IS: {len(quarterly_is)} accounts") 
    #     print(f"📊 Monthly IS: {len(monthly_is)} accounts")
        
    #     return {
    #         'annual': annual_is,
    #         'quarterly': quarterly_is,
    #         'monthly': monthly_is
    #     }

    # def create_all_income_statements(self):
    #     """Convenience method to create all three income statement types"""
    #     self.filter_income_statement_accounts()
        
    #     return {
    #         'annual': self.create_annual_income_statement(),
    #         'quarterly': self.create_quarterly_income_statement(),
    #         'monthly': self.create_monthly_income_statement()
    #     }