"""
Simple Financial Statement Exporter
Uses existing FSAccountLoader functions instead of recreating functionality
"""
import pandas as pd 
import os
from services.loaders.fsaccount_loader import FSAccountLoader

class SimpleFSExporter:
    def __init__(self, tb_path: str, coa_path: str, output_path: str):
        """
        Initialize the Simple Financial Statement Exporter
        
        Args:
            tb_path: Path to Trial Balance Excel file (TB11.xlsx)
            coa_path: Path to Chart of Accounts Excel file
            output_path: Path where the output file will be saved
        """
        self.tb_path = tb_path
        self.coa_path = coa_path
        self.output_path = output_path
        self.loader = None
        
    def process_and_export(self):
        """
        Main method: Uses FSAccountLoader functions to process and export data WITH formulas
        """
        print("🚀 Starting Simple Financial Data Export Process...")
        
        try:
            # Validate input files exist
            self._validate_input_files()
            
            # Initialize FSAccountLoader
            print("📊 Initializing data loader...")
            self.loader = FSAccountLoader(
                tb_path=self.tb_path,
                coa_path=self.coa_path,
                dataset_id="simple_fs_export"
            )
            
            # Run the complete processing pipeline using existing methods
            print("🔄 Loading and processing data...")
            self.loader._load_and_merge()
            self.loader._clean_and_transform()
            self.loader._tag_basic_periods()
            self.loader._exclude_incomplete_fiscal_years()
            self.loader._assign_period_column()
            self.loader._finalize()
            
            # Create Excel with both source data AND formula-based statements
            print(f"💾 Exporting to {self.output_path} with formulas...")
            statements = self._export_with_formulas()
            
            # Print summary using existing data
            self._print_export_summary(statements)
            
            print("✅ Export completed successfully with formulas in Excel!")
            return statements
            
        except Exception as e:
            print(f"❌ Error during export: {str(e)}")
            raise
    
    def _export_with_formulas(self):
        """Export using FSAccountLoader data but with Excel formulas"""
        import pandas as pd
        from datetime import datetime
        
        # Filter for Income Statement accounts using existing function
        self.loader.filter_income_statement_accounts()
        
        # Get the aggregated data using existing functions for reference
        annual_is = self.loader.create_annual_income_statement()
        quarterly_is = self.loader.create_quarterly_income_statement()
        monthly_is = self.loader.create_monthly_income_statement()
        
        # Create Excel with source data + formula sheets
        with pd.ExcelWriter(self.output_path, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D9E1F2',
                'border': 1
            })
            
            currency_format = workbook.add_format({
                'num_format': '#,##0',
                'border': 1
            })
            
            text_format = workbook.add_format({
                'border': 1,
                'text_wrap': True
            })
            
            # 1. Export source data sheet
            self.loader.df.to_excel(writer, sheet_name='Source_Data', index=False)
            
            # 2. Create Annual Income Statement with formulas
            self._create_annual_with_formulas(writer, workbook, annual_is, header_format, currency_format, text_format)
            
            # 3. Create Quarterly Income Statement with formulas  
            self._create_quarterly_with_formulas(writer, workbook, quarterly_is, header_format, currency_format, text_format)
            
            # 4. Create Monthly Income Statement with formulas
            self._create_monthly_with_formulas(writer, workbook, monthly_is, header_format, currency_format, text_format)
            
            # 5. Add summary sheet
            self._create_summary_sheet(writer, workbook, annual_is, quarterly_is, monthly_is, header_format)
        
        return {
            'annual': annual_is,
            'quarterly': quarterly_is,
            'monthly': monthly_is
        }
    
    def _create_annual_with_formulas(self, writer, workbook, annual_data, header_format, currency_format, text_format):
        """Create Annual Income Statement with Excel formulas"""
        worksheet = workbook.add_worksheet('Annual_Income_Statement')
        
        # Get column info from source data
        source_cols = list(self.loader.df.columns)
        account_col_idx = source_cols.index('account')
        balance_col_idx = source_cols.index('ending_balance')
        fy_col_idx = source_cols.index('fiscal_year')
        ltm_col_idx = source_cols.index('ltm')
        ytd_col_idx = source_cols.index('ytd')
        
        # Convert to Excel column letters
        account_col = self._get_excel_column_letter(account_col_idx)
        balance_col = self._get_excel_column_letter(balance_col_idx)
        fy_col = self._get_excel_column_letter(fy_col_idx)
        ltm_col = self._get_excel_column_letter(ltm_col_idx)
        ytd_col = self._get_excel_column_letter(ytd_col_idx)
        
        # Create headers based on actual data
        headers = ['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping']
        
        # Add fiscal year columns
        fiscal_years = sorted(self.loader.valid_fys)
        headers.extend(fiscal_years)
        
        # Add LTM and YTD columns
        ltm_label = f'LTM {self.loader.current_date.strftime("%b %Y")}'
        ytd_label = f'YTD F{self.loader.valid_fys[-1].replace("F", "")}'  # Use latest FY
        headers.extend([ltm_label, ytd_label])
        
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Write account data with formulas
        for row_idx, (_, account_row) in enumerate(annual_data.iterrows(), start=1):
            # Write account info
            worksheet.write(row_idx, 0, account_row['account'], text_format)
            worksheet.write(row_idx, 1, account_row['account_name'], text_format)
            worksheet.write(row_idx, 2, account_row['top_level_grouping'], text_format)
            worksheet.write(row_idx, 3, account_row['fs_grouping'], text_format)
            worksheet.write(row_idx, 4, account_row['detailed_grouping'], text_format)
            
            # Write formulas for fiscal years
            for col_idx, fy in enumerate(fiscal_years, start=5):
                formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row["account"]}", Source_Data!{fy_col}:{fy_col}, "{fy}")'
                worksheet.write_formula(row_idx, col_idx, formula, currency_format)
            
            # LTM formula
            ltm_col_idx = len(headers) - 2
            ltm_formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row["account"]}", Source_Data!{ltm_col}:{ltm_col}, "<>")'
            worksheet.write_formula(row_idx, ltm_col_idx, ltm_formula, currency_format)
            
            # YTD formula
            ytd_col_idx = len(headers) - 1
            ytd_formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row["account"]}", Source_Data!{ytd_col}:{ytd_col}, "<>")'
            worksheet.write_formula(row_idx, ytd_col_idx, ytd_formula, currency_format)
        
        # Set column widths
        for col_idx, header in enumerate(headers):
            if col_idx < 5:  # Text columns
                worksheet.set_column(col_idx, col_idx, 25)
            else:  # Number columns
                worksheet.set_column(col_idx, col_idx, 15)
    
    def _create_quarterly_with_formulas(self, writer, workbook, quarterly_data, header_format, currency_format, text_format):
        """Create Quarterly Income Statement with Excel formulas"""
        worksheet = workbook.add_worksheet('Quarterly_Income_Statement')
        
        # Get column info from source data
        source_cols = list(self.loader.df.columns)
        account_col = self._get_excel_column_letter(source_cols.index('account'))
        balance_col = self._get_excel_column_letter(source_cols.index('ending_balance'))
        quarter_col = self._get_excel_column_letter(source_cols.index('fiscal_quarter'))
        
        # Create headers
        headers = ['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping']
        quarters = sorted(self.loader.df['fiscal_quarter'].dropna().unique())
        headers.extend(quarters)
        
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Write account data with formulas
        for row_idx, (_, account_row) in enumerate(quarterly_data.iterrows(), start=1):
            # Write account info
            worksheet.write(row_idx, 0, account_row['account'], text_format)
            worksheet.write(row_idx, 1, account_row['account_name'], text_format)
            worksheet.write(row_idx, 2, account_row['top_level_grouping'], text_format)
            worksheet.write(row_idx, 3, account_row['fs_grouping'], text_format)
            worksheet.write(row_idx, 4, account_row['detailed_grouping'], text_format)
            
            # Write formulas for quarters
            for col_idx, quarter in enumerate(quarters, start=5):
                formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row["account"]}", Source_Data!{quarter_col}:{quarter_col}, "{quarter}")'
                worksheet.write_formula(row_idx, col_idx, formula, currency_format)
        
        # Set column widths
        for col_idx, header in enumerate(headers):
            if col_idx < 5:
                worksheet.set_column(col_idx, col_idx, 25)
            else:
                worksheet.set_column(col_idx, col_idx, 15)
    
    def _create_monthly_with_formulas(self, writer, workbook, monthly_data, header_format, currency_format, text_format):
        """Create Monthly Income Statement with Excel formulas"""
        worksheet = workbook.add_worksheet('Monthly_Income_Statement')
        
        # Get column info from source data
        source_cols = list(self.loader.df.columns)
        account_col = self._get_excel_column_letter(source_cols.index('account'))
        balance_col = self._get_excel_column_letter(source_cols.index('ending_balance'))
        month_col = self._get_excel_column_letter(source_cols.index('month'))
        
        # Create headers
        headers = ['account', 'account_name', 'top_level_grouping', 'fs_grouping', 'detailed_grouping']
        import pandas as pd
        months = sorted(self.loader.df['month'].dropna().unique(), key=lambda x: pd.to_datetime(x))
        headers.extend(months)
        
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Write account data with formulas
        for row_idx, (_, account_row) in enumerate(monthly_data.iterrows(), start=1):
            # Write account info
            worksheet.write(row_idx, 0, account_row['account'], text_format)
            worksheet.write(row_idx, 1, account_row['account_name'], text_format)
            worksheet.write(row_idx, 2, account_row['top_level_grouping'], text_format)
            worksheet.write(row_idx, 3, account_row['fs_grouping'], text_format)
            worksheet.write(row_idx, 4, account_row['detailed_grouping'], text_format)
            
            # Write formulas for months
            for col_idx, month in enumerate(months, start=5):
                formula = f'=SUMIFS(Source_Data!{balance_col}:{balance_col}, Source_Data!{account_col}:{account_col}, "{account_row["account"]}", Source_Data!{month_col}:{month_col}, "{month}")'
                worksheet.write_formula(row_idx, col_idx, formula, currency_format)
        
        # Set column widths
        for col_idx, header in enumerate(headers):
            if col_idx < 5:
                worksheet.set_column(col_idx, col_idx, 25)
            else:
                worksheet.set_column(col_idx, col_idx, 12)
    
    def _create_summary_sheet(self, writer, workbook, annual_is, quarterly_is, monthly_is, header_format):
        """Create summary sheet"""
        from datetime import datetime
        
        summary_data = {
            'Statement_Type': ['Annual', 'Quarterly', 'Monthly'],
            'Account_Count': [len(annual_is), len(quarterly_is), len(monthly_is)],
            'Export_Date': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] * 3,
            'Has_Formulas': ['Yes', 'Yes', 'Yes']
        }
        
        import pandas as pd
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Export_Summary', index=False)
        
        # Format summary sheet
        worksheet = writer.sheets['Export_Summary']
        for col_num, value in enumerate(summary_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
    
    def _get_excel_column_letter(self, col_idx):
        """Convert column index to Excel column letter (A, B, C, etc.)"""
        result = ""
        col_idx += 1  # Excel columns are 1-indexed
        while col_idx > 0:
            col_idx -= 1
            result = chr(col_idx % 26 + ord('A')) + result
            col_idx //= 26
        return result
    
    def _validate_input_files(self):
        """Check if input files exist"""
        if not os.path.exists(self.tb_path):
            raise FileNotFoundError(f"Trial Balance file not found: {self.tb_path}")
        if not os.path.exists(self.coa_path):
            raise FileNotFoundError(f"Chart of Accounts file not found: {self.coa_path}")
    
    def _print_export_summary(self, statements):
        """Print summary of the export process"""
        print("\n SIMPLE EXPORT SUMMARY")
        print("=" * 50)
        print(f" Output file: {self.output_path}")
        print(f" Total records processed: {len(self.loader.df):,}")
        print(f" Unique accounts: {self.loader.df['account'].nunique():,}")
        print(f" Date range: {self.loader.df['date'].min().strftime('%Y-%m-%d')} to {self.loader.df['date'].max().strftime('%Y-%m-%d')}")
        print(f" Valid fiscal years: {', '.join(self.loader.valid_fys)}")
        print(f" Excel sheets created using FSAccountLoader:")
        print(f"   - Annual Income Statement: {len(statements['annual'])} accounts")
        print(f"   - Quarterly Income Statement: {len(statements['quarterly'])} accounts") 
        print(f"   - Monthly Income Statement: {len(statements['monthly'])} accounts")
        print("=" * 50)


# Usage example and main execution
if __name__ == "__main__":
    # Define file paths
    tb_file_path = "data-sets/TB11.xlsx"
    coa_file_path = "data-sets/Chart of Accounts.xlsx"
    # output_file_path = "data-sets/Income_Statements_WITH_FORMULAS.xlsx"
    output_file_path = "data-sets/Income_Statements_WITH_FORMULAS_again.xlsx"
    
    try:
        # Create and run the simple exporter
        exporter = SimpleFSExporter(
            tb_path=tb_file_path,
            coa_path=coa_file_path,
            output_path=output_file_path
        )
        
        # Process and export using existing FSAccountLoader functions
        statements = exporter.process_and_export()
        
        print(f"\n🎉 Success! Check your Income Statements at: {output_file_path}")
        print("📝 This file was created using existing FSAccountLoader functions - much cleaner!")
        
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        print("Make sure TB11.xlsx and Chart of Accounts.xlsx are in the data-sets folder")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
