import pandas as pd
import os
from pathlib import Path

class CSVConverter:
    def __init__(self, cache_dir: str = "cache/csv"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def excel_to_csv(self, excel_path: str, csv_path: str = None, sheet_name: int = 0) -> str:
        """Convert Excel file to CSV and return the CSV path"""
        excel_path = Path(excel_path)
        
        if csv_path is None:
            csv_path = self.cache_dir / f"{excel_path.stem}.csv"
        else:
            csv_path = Path(csv_path)
        
        # Check if CSV exists and is newer than Excel file
        if csv_path.exists() and csv_path.stat().st_mtime > excel_path.stat().st_mtime:
            print(f"✅ Using cached CSV: {csv_path}")
            return str(csv_path)
        
        # Convert Excel to CSV
        print(f"🔄 Converting {excel_path.name} to CSV...")
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        df.to_csv(csv_path, index=False)
        print(f"✅ CSV created: {csv_path}")
        
        return str(csv_path)
    
    def get_csv_paths(self, tb_path: str, coa_path: str) -> tuple:
        """Convert both TB and COA files to CSV and return paths"""
        tb_csv = self.excel_to_csv(tb_path)
        coa_csv = self.excel_to_csv(coa_path)
        return tb_csv, coa_csv