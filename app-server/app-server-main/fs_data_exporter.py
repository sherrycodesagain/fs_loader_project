import pandas as pd
import os
from services.loaders.fsaccount_loader import FSAccountLoader
from datetime import datetime
from utils.period_utils import get_fiscal_year  # ADD THIS LINE
class FSDataExporter:
    def __init__(self, tb_path: str, coa_path: str, output_path: str):
        """
        Initialize the Financial Statement Data Exporter
        
        Args:
            tb_path: Path to Trial Balance Excel file (TB11.xlsx)
            coa_path: Path to Chart of Accounts Excel file
            output_path: Path where the enriched output file will be saved
        """
        self.tb_path = tb_path
        self.coa_path = coa_path
        self.output_path = output_path
        self.loader = None
        
    def process_and_export(self):
        """
        Main method: Load 2 input files, process with FSAccountLoader functions, 
        and export enriched 3rd file
        """
        print("🚀 Starting Financial Data Export Process...")
        
        try:
            # Validate input files exist
            self._validate_input_files()
            
            # Initialize FSAccountLoader with custom dataset_id
            print("📊 Initializing data loader...")
            self.loader = FSAccountLoader(
                tb_path=self.tb_path,
                coa_path=self.coa_path,
                dataset_id="fs_export_dataset"
            )
            
            # Run the complete processing pipeline (same as original)
            print("🔄 Loading and merging Trial Balance + Chart of Accounts...")
            self.loader._load_and_merge()
            
            print("🧹 Cleaning and transforming data...")
            self.loader._clean_and_transform()
            
            print("📅 Tagging periods (YTD, LTM, Fiscal Quarters)...")
            self.loader._tag_basic_periods()
            
            print("✅ Excluding incomplete fiscal years...")
            self.loader._exclude_incomplete_fiscal_years()
            
            print("📈 Assigning period columns...")
            self.loader._assign_period_column()
            
            print("🎯 Finalizing data structure...")
            self.loader._finalize()
            
            # Add period labels (replicating the logic from load_and_store)
            print("🏷️ Determining period labels...")
            self._add_period_labels()
            
            # Generate all metadata
            print("📋 Building metadata...")
            period_ranges = self.loader._build_period_ranges()
            filters = self.loader._extract_filter_metadata()
            waterfall_periods = self.loader._build_waterfall_periods()
            month_to_quarter = self._build_month_to_quarter_mapping()
            
            # Export everything to Excel with formulas
            print(f"💾 Exporting enriched data with formulas to {self.output_path}...")
            self._export_income_statements_with_formulas()
            
            # Also export metadata sheets
            self._export_metadata_sheets(period_ranges, filters, waterfall_periods, month_to_quarter)
            
            # Print summary
            self._print_export_summary()
            
            print("✅ Export completed successfully!")
            return self.loader.df
            
        except Exception as e:
            print(f"❌ Error during export: {str(e)}")
            raise
    
    def _validate_input_files(self):
        """Check if input files exist"""
        if not os.path.exists(self.tb_path):
            raise FileNotFoundError(f"Trial Balance file not found: {self.tb_path}")
        if not os.path.exists(self.coa_path):
            raise FileNotFoundError(f"Chart of Accounts file not found: {self.coa_path}")
    
    def _add_period_labels(self):
        """Add period_label column (same logic as original FSAccountLoader)"""
        def determine_period_label(row):
            if row["ytd"]:
                return row["ytd"]
            if row["ltm"]:
                return row["ltm"]
            if row["fiscal_year"] in self.loader.valid_fys:
                return row["fiscal_year"]
            return ""
        
        self.loader.df["period_label"] = self.loader.df.apply(determine_period_label, axis=1)
    
    def _build_month_to_quarter_mapping(self):
        """Build month to quarter mapping (same as original)"""
        month_to_quarter = {}
        for _, row in self.loader.df.iterrows():
            month = row.get("month")
            quarter = row.get("fiscal_quarter")
            if isinstance(month, str) and isinstance(quarter, str):
                month_to_quarter[month] = quarter
        return month_to_quarter

    def _export_income_statements_with_formulas(self):
        """Export Income Statements with Excel formulas and proper formatting"""
        
        # Filter for Income Statement accounts only
        self.loader.filter_income_statement_accounts()
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        with pd.ExcelWriter(self.output_path, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Define formats
            self._define_excel_formats(workbook)
            
            # 1. Export source data (TB11 + COA merged)
            self._export_source_data_sheet(writer)
            
            # 2. Create Annual Income Statement with formulas
            self._create_annual_income_statement_with_formulas(writer, workbook)
            
            # 3. Create Quarterly Income Statement with formulas
            self._create_quarterly_income_statement_with_formulas(writer, workbook)
            
            # 4. Create Monthly Income Statement with formulas
            self._create_monthly_income_statement_with_formulas(writer, workbook)
            
            print("✅ Income statements with formulas exported successfully!")

    def _define_excel_formats(self, workbook):
        """Define Excel formatting styles"""
        self.header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D9E1F2',
            'border': 1,
            'font_size': 11
        })
        
        self.currency_format = workbook.add_format({
            'num_format': '#,##0',
            'border': 1
        })
        
        self.text_format = workbook.add_format({
            'border': 1,
            'text_wrap': True
        })
        
        self.subtotal_format = workbook.add_format({
            'bold': True,
            'num_format': '#,##0',
            'border': 1,
            'fg_color': '#F2F2F2'
        })
        
        self.total_format = workbook.add_format({
            'bold': True,
            'num_format': '#,##0',
            'border': 2,
            'fg_color': '#E6E6FA'
        })

    def _export_source_data_sheet(self, writer):
        """Export the source data (processed TB11 + COA) for formula references"""
        self.loader.df.to_excel(writer, sheet_name='Source_Data', index=False)
        
        worksheet = writer.sheets['Source_Data']
        
        # Format headers
        for col_num, value in enumerate(self.loader.df.columns.values):
            worksheet.write(0, col_num, value, self.header_format)
        
        # Auto-adjust column widths
        for i, col in enumerate(self.loader.df.columns):
            max_len = max(
                self.loader.df[col].astype(str).map(len).max(),
                len(str(col))
            )
            worksheet.set_column(i, i, min(max_len + 2, 50))

    def _create_annual_income_statement_with_formulas(self, writer, workbook):
        """Create Annual Income Statement with Excel formulas"""
        worksheet = workbook.add_worksheet('Annual_Income_Statement')
        writer.sheets['Annual_Income_Statement'] = worksheet
        
        # Get unique accounts for Income Statement
        is_accounts = self.loader.df.groupby(['account', 'account_name', 'top_level_grouping', 
                                             'fs_grouping', 'detailed_grouping']).first().reset_index()
        
        # Get unique fiscal years + LTM + YTD
        fiscal_years = sorted(self.loader.valid_fys)
        # current_fy = f"F{self.loader._get_fiscal_year(self.loader.current_date)}"
        current_fy_num = get_fiscal_year(self.loader.current_date, self.loader.fiscal_month, self.loader.fiscal_day)
        current_fy = f"F{current_fy_num}"
        ltm_label = f"LTM {self.loader.current_date.strftime('%b %Y')}"
        ytd_label = f"YTD {current_fy}"
        
        # Create headers
        headers = ['Account', 'Account Name', 'Top Level Grouping', 'FS Grouping', 'Detailed Grouping']
        headers.extend(fiscal_years)
        headers.extend([ltm_label, ytd_label])
        
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, self.header_format)
        
        # Find column indexes in Source_Data sheet
        source_cols = list(self.loader.df.columns)
        account_col = self._get_excel_column_letter(source_cols.index('account'))
        balance_col = self._get_excel_column_letter(source_cols.index('ending_balance'))
        fy_col = self._get_excel_column_letter(source_cols.index('fiscal_year'))
        ltm_col_letter = self._get_excel_column_letter(source_cols.index('ltm'))
        ytd_col_letter = self._get_excel_column_letter(source_cols.index('ytd'))
        
        # Write account data with FIXED formulas using Source_Data! syntax
        for row_idx, account_row in enumerate(is_accounts.itertuples(), start=1):
            # Write account info
            worksheet.write(row_idx, 0, account_row.account, self.text_format)
            worksheet.write(row_idx, 1, account_row.account_name, self.text_format)
            worksheet.write(row_idx, 2, account_row.top_level_grouping, self.text_format)
            worksheet.write(row_idx, 3, account_row.fs_grouping, self.text_format)
            worksheet.write(row_idx, 4, account_row.detailed_grouping, self.text_format)
            
            # Write formulas for each fiscal year - FIXED
            for col_idx, fy in enumerate(fiscal_years, start=5):
                formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row.account}", Source_Data!{fy_col}:{fy_col}, "{fy}")'
                worksheet.write_formula(row_idx, col_idx, formula, self.currency_format)
            
            # LTM formula - FIXED
            ltm_col_idx = len(headers) - 2
            ltm_formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row.account}", Source_Data!{ltm_col_letter}:{ltm_col_letter}, "<>")'
            worksheet.write_formula(row_idx, ltm_col_idx, ltm_formula, self.currency_format)
            
            # YTD formula - FIXED
            ytd_col_idx = len(headers) - 1
            ytd_formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row.account}", Source_Data!{ytd_col_letter}:{ytd_col_letter}, "<>")'
            worksheet.write_formula(row_idx, ytd_col_idx, ytd_formula, self.currency_format)
        
        # Add subtotals by FS Grouping
        self._add_subtotals_by_grouping(worksheet, is_accounts, headers, 'fs_grouping')
        
        # Set column widths
        self._set_column_widths(worksheet, headers)

    def _create_quarterly_income_statement_with_formulas(self, writer, workbook):
        """Create Quarterly Income Statement with Excel formulas"""
        worksheet = workbook.add_worksheet('Quarterly_Income_Statement')
        writer.sheets['Quarterly_Income_Statement'] = worksheet
        
        # Get unique accounts
        is_accounts = self.loader.df.groupby(['account', 'account_name', 'top_level_grouping', 
                                             'fs_grouping', 'detailed_grouping']).first().reset_index()
        
        # Get unique fiscal quarters (sorted chronologically)
        quarters = sorted(self.loader.df['fiscal_quarter'].dropna().unique())
        
        # Create headers
        headers = ['Account', 'Account Name', 'Top Level Grouping', 'FS Grouping', 'Detailed Grouping']
        headers.extend(quarters)
        
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, self.header_format)
        
        # Find column indexes in Source_Data sheet
        source_cols = list(self.loader.df.columns)
        account_col = self._get_excel_column_letter(source_cols.index('account'))
        balance_col = self._get_excel_column_letter(source_cols.index('ending_balance'))
        quarter_col = self._get_excel_column_letter(source_cols.index('fiscal_quarter'))
        
        # Write account data with FIXED formulas
        for row_idx, account_row in enumerate(is_accounts.itertuples(), start=1):
            # Write account info
            worksheet.write(row_idx, 0, account_row.account, self.text_format)
            worksheet.write(row_idx, 1, account_row.account_name, self.text_format)
            worksheet.write(row_idx, 2, account_row.top_level_grouping, self.text_format)
            worksheet.write(row_idx, 3, account_row.fs_grouping, self.text_format)
            worksheet.write(row_idx, 4, account_row.detailed_grouping, self.text_format)
            
            # Write formulas for each quarter - FIXED
            for col_idx, quarter in enumerate(quarters, start=5):
                formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row.account}", Source_Data!{quarter_col}:{quarter_col}, "{quarter}")'
                worksheet.write_formula(row_idx, col_idx, formula, self.currency_format)
        
        # Add subtotals
        self._add_subtotals_by_grouping(worksheet, is_accounts, headers, 'fs_grouping')
        
        # Set column widths
        self._set_column_widths(worksheet, headers)

    def _create_monthly_income_statement_with_formulas(self, writer, workbook):
        """Create Monthly Income Statement with Excel formulas"""
        worksheet = workbook.add_worksheet('Monthly_Income_Statement')
        writer.sheets['Monthly_Income_Statement'] = worksheet
        
        # Get unique accounts
        is_accounts = self.loader.df.groupby(['account', 'account_name', 'top_level_grouping', 
                                             'fs_grouping', 'detailed_grouping']).first().reset_index()
        
        # Get unique months (sorted chronologically)
        months = sorted(self.loader.df['month'].dropna().unique(), 
                       key=lambda x: pd.to_datetime(x))
        
        # Create headers
        headers = ['Account', 'Account Name', 'Top Level Grouping', 'FS Grouping', 'Detailed Grouping']
        headers.extend(months)
        
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, self.header_format)
        
        # Find column indexes in Source_Data sheet
        source_cols = list(self.loader.df.columns)
        account_col = self._get_excel_column_letter(source_cols.index('account'))
        balance_col = self._get_excel_column_letter(source_cols.index('ending_balance'))
        month_col = self._get_excel_column_letter(source_cols.index('month'))
        
        # Write account data with FIXED formulas
        for row_idx, account_row in enumerate(is_accounts.itertuples(), start=1):
            # Write account info
            worksheet.write(row_idx, 0, account_row.account, self.text_format)
            worksheet.write(row_idx, 1, account_row.account_name, self.text_format)
            worksheet.write(row_idx, 2, account_row.top_level_grouping, self.text_format)
            worksheet.write(row_idx, 3, account_row.fs_grouping, self.text_format)
            worksheet.write(row_idx, 4, account_row.detailed_grouping, self.text_format)
            
            # Write formulas for each month - FIXED
            for col_idx, month in enumerate(months, start=5):
                formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row.account}", Source_Data!{month_col}:{month_col}, "{month}")'
                worksheet.write_formula(row_idx, col_idx, formula, self.currency_format)
        
        # Add subtotals
        self._add_subtotals_by_grouping(worksheet, is_accounts, headers, 'fs_grouping')
        
        # Set column widths
        self._set_column_widths(worksheet, headers)

    def _add_subtotals_by_grouping(self, worksheet, accounts_df, headers, grouping_col):
        """Add subtotal rows for each financial statement grouping"""
        current_row = len(accounts_df) + 2  # Start after data + 1 blank row
        
        # Group by FS Grouping
        grouped = accounts_df.groupby(grouping_col)
        
        for group_name, group_data in grouped:
            # Write subtotal label
            worksheet.write(current_row, 0, f"TOTAL {group_name.upper()}", self.subtotal_format)
            
            # Write subtotal formulas for each period column (skip the first 5 description columns)
            for col_idx in range(5, len(headers)):
                # Find the row range for this group in the main data
                start_row = 2  # Data starts at row 2 (1-indexed)
                end_row = len(accounts_df) + 1
                
                col_letter = self._get_excel_column_letter(col_idx)
                formula = f'=SUMIF(D{start_row}:D{end_row}, "{group_name}", {col_letter}{start_row}:{col_letter}{end_row})'
                worksheet.write_formula(current_row, col_idx, formula, self.subtotal_format)
            
            current_row += 1

    def _get_excel_column_letter(self, col_idx):
        """Convert column index to Excel column letter (A, B, C, etc.) - FIXED VERSION"""
        result = ""
        col_idx += 1  # Excel columns are 1-indexed
        while col_idx > 0:
            col_idx -= 1
            result = chr(col_idx % 26 + ord('A')) + result
            col_idx //= 26
        return result

    def _set_column_widths(self, worksheet, headers):
        """Set appropriate column widths"""
        width_map = {
            'Account': 25,
            'Account Name': 30,
            'Top Level Grouping': 20,
            'FS Grouping': 25,
            'Detailed Grouping': 25
        }
        
        for col_idx, header in enumerate(headers):
            if header in width_map:
                worksheet.set_column(col_idx, col_idx, width_map[header])
            else:
                worksheet.set_column(col_idx, col_idx, 15)  # Default width for period columns

    def _export_metadata_sheets(self, period_ranges, filters, waterfall_periods, month_to_quarter):
        """Export metadata sheets (keeping original functionality)"""
        with pd.ExcelWriter(self.output_path, mode='a', engine='openpyxl') as writer:
            
            # Period ranges metadata
            self._export_period_ranges(writer, period_ranges)
            
            # Filter options for dropdowns
            self._export_filter_options(writer, filters)
            
            # Waterfall period transitions
            self._export_waterfall_periods(writer, waterfall_periods)
            
            # Month to Quarter mapping
            self._export_month_quarter_mapping(writer, month_to_quarter)
            
            # Summary statistics
            self._export_summary_stats(writer)

    def _export_period_ranges(self, writer, period_ranges):
        """Export period ranges with start/end dates and months"""
        ranges_data = []
        for period, info in period_ranges.items():
            ranges_data.append({
                'Period': period,
                'Start_Date': info['start'].strftime('%Y-%m-%d'),
                'End_Date': info['end'].strftime('%Y-%m-%d'),
                'Month_Count': len(info['months']),
                'Months': '; '.join(info['months'])
            })
        
        if ranges_data:
            pd.DataFrame(ranges_data).to_excel(writer, sheet_name='Period_Ranges', index=False)
    
    def _export_filter_options(self, writer, filters):
        """Export all available filter values for each field"""
        filter_data = []
        for field, values in filters.items():
            for value in values:
                filter_data.append({
                    'Field': field,
                    'Value': str(value),
                    'Field_Type': type(value).__name__
                })
        
        if filter_data:
            pd.DataFrame(filter_data).to_excel(writer, sheet_name='Filter_Options', index=False)
    
    def _export_waterfall_periods(self, writer, waterfall_periods):
        """Export waterfall chart period transitions"""
        waterfall_data = []
        for transition, (start_period, end_period) in waterfall_periods.items():
            waterfall_data.append({
                'Transition_Name': transition,
                'Start_Period': start_period,
                'End_Period': end_period
            })
        
        if waterfall_data:
            pd.DataFrame(waterfall_data).to_excel(writer, sheet_name='Waterfall_Periods', index=False)
    
    def _export_month_quarter_mapping(self, writer, month_to_quarter):
        """Export month to fiscal quarter mapping"""
        mapping_data = []
        for month, quarter in month_to_quarter.items():
            mapping_data.append({
                'Month': month,
                'Fiscal_Quarter': quarter
            })
        
        if mapping_data:
            pd.DataFrame(mapping_data).to_excel(writer, sheet_name='Month_Quarter_Map', index=False)
    
    def _export_summary_stats(self, writer):
        """Export summary statistics about the processed data"""
        summary_data = []
        
        # Basic counts
        summary_data.append({'Metric': 'Total Rows', 'Value': len(self.loader.df)})
        summary_data.append({'Metric': 'Unique Accounts', 'Value': self.loader.df['account'].nunique()})
        summary_data.append({'Metric': 'Date Range Start', 'Value': self.loader.df['date'].min().strftime('%Y-%m-%d')})
        summary_data.append({'Metric': 'Date Range End', 'Value': self.loader.df['date'].max().strftime('%Y-%m-%d')})
        summary_data.append({'Metric': 'Valid Fiscal Years', 'Value': '; '.join(self.loader.valid_fys)})
        summary_data.append({'Metric': 'Fiscal Year End Month', 'Value': self.loader.fiscal_month})
        summary_data.append({'Metric': 'Export Timestamp', 'Value': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        
        # Period counts
        ytd_count = len(self.loader.df[self.loader.df['ytd'].str.strip().astype(bool)])
        ltm_count = len(self.loader.df[self.loader.df['ltm'].str.strip().astype(bool)])
        
        summary_data.append({'Metric': 'YTD Records', 'Value': ytd_count})
        summary_data.append({'Metric': 'LTM Records', 'Value': ltm_count})
        
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary_Stats', index=False)
    
    def _print_export_summary(self):
        """Print summary of the export process"""
        print("\n📊 EXPORT SUMMARY")
        print("=" * 50)
        print(f"📁 Output file: {self.output_path}")
        print(f"📈 Total records: {len(self.loader.df):,}")
        print(f"🏢 Unique accounts: {self.loader.df['account'].nunique():,}")
        print(f"📅 Date range: {self.loader.df['date'].min().strftime('%Y-%m-%d')} to {self.loader.df['date'].max().strftime('%Y-%m-%d')}")
        print(f"📊 Valid fiscal years: {', '.join(self.loader.valid_fys)}")
        print(f"📋 Excel sheets created: Source_Data, Annual_Income_Statement, Quarterly_Income_Statement, Monthly_Income_Statement + metadata sheets")
        print("=" * 50)


# Usage example and main execution
if __name__ == "__main__":
    # Define file paths
    tb_file_path = "data-sets/TB11.xlsx"
    coa_file_path = "data-sets/Chart of Accounts.xlsx"
    output_file_path = "data-sets/Income_Statements_With_Formulas_FINAL.xlsx"
    
    try:
        # Create and run the exporter
        exporter = FSDataExporter(
            tb_path=tb_file_path,
            coa_path=coa_file_path,
            output_path=output_file_path
        )
        
        # Process and export
        enriched_df = exporter.process_and_export()
        
        print(f"\n🎉 Success! Check your Income Statements with formulas at: {output_file_path}")
        
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        print("Make sure TB11.xlsx and Chart of Accounts.xlsx are in the data-sets folder")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")