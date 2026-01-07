# # main_export_test.py

# import pandas as pd
# from services.loaders.fsaccount_loader import FSAccountLoader
# from services.exporter.fs_excel_exporter_backup import FSExcelExporter

# from config import TB_PATH, COA_PATH

# # Load enriched data
# loader = FSAccountLoader(TB_PATH, COA_PATH)
# loader.load_and_store()

# df = loader.df.copy()
# value_date = loader.current_date
# fye = loader.fiscal_year_end

# # Export to Excel
# exporter = FSExcelExporter(
#     enriched_df=df,
#     value_date=value_date,
#     fiscal_year_end=fye,
#     output_path="output/income_statement.xlsx"
# )

# exporter.export()
############ ORIGINAL ############





import pandas as pd
import time
from services.loaders.fsaccount_loader import FSAccountLoader
from services.exporter.fs_excel_exporter_backup import FSExcelExporter
from config import TB_PATH, COA_PATH

print("Testing CSV Optimization vs Original Method")
print("=" * 50)

# Test 1: Original method (current way)
print("\n🔄 Testing Original Excel Loading...")
start_time = time.time()

loader_original = FSAccountLoader(TB_PATH, COA_PATH, use_csv_cache=False)
loader_original.load_and_store()

original_time = time.time() - start_time
print(f"⏱️ Original method took: {original_time:.2f} seconds")

# Test 2: CSV optimized method
print("\n🚀 Testing CSV Optimized Loading...")
start_time = time.time()

loader_optimized = FSAccountLoader(TB_PATH, COA_PATH, use_csv_cache=True)
loader_optimized.load_and_store()

optimized_time = time.time() - start_time
print(f"⏱️ Optimized method took: {optimized_time:.2f} seconds")

# Performance comparison
if optimized_time < original_time:
    speedup = original_time / optimized_time
    print(f"🎉 CSV optimization is {speedup:.1f}x faster!")
else:
    print("📊 Performance similar (CSV cache may already exist)")

# Verify data integrity
print("\n🔍 Verifying data integrity...")
df_original = loader_original.df
df_optimized = loader_optimized.df

print(f"Original shape: {df_original.shape}")
print(f"Optimized shape: {df_optimized.shape}")
print(f"Data identical: {df_original.equals(df_optimized)}")


###################### INTEGRITY CHECKER STARTS HERE ######################
# ONLY DEPENDING ON THE DATA IDENTICAL FLAG, 
if not df_original.equals(df_optimized):
    print("\n🔍 Investigating differences...")
    
    # Check for differences in specific columns
    for col in df_original.columns:
        if col in df_optimized.columns:
            if not df_original[col].equals(df_optimized[col]):
                print(f"❗ Difference in column: {col}")
                
                # Check data types
                print(f"  Original dtype: {df_original[col].dtype}")
                print(f"  Optimized dtype: {df_optimized[col].dtype}")
                
                # Show first few different values
                diff_mask = df_original[col] != df_optimized[col]
                if diff_mask.any():
                    print(f"  Sample differences:")
                    print(f"    Original: {df_original[col][diff_mask].head(3).tolist()}")
                    print(f"    Optimized: {df_optimized[col][diff_mask].head(3).tolist()}")
    
    # Check if it's just data type differences (which is fine)
    try:
        df_original_normalized = df_original.copy()
        df_optimized_normalized = df_optimized.copy()
        
        # Convert object columns to string for comparison
        for col in df_original.columns:
            if df_original[col].dtype == 'object':
                df_original_normalized[col] = df_original_normalized[col].astype(str)
                df_optimized_normalized[col] = df_optimized_normalized[col].astype(str)
        
        if df_original_normalized.equals(df_optimized_normalized):
            print("✅ Data is functionally identical (just data type differences)")
        else:
            print("❗ Data has actual value differences")
            
    except Exception as e:
        print(f"🔍 Comparison check failed: {e}")
###################### INTEGRITY CHECKER ENDS HERE ######################

# Use the optimized loader for export (or original - both work the same)
print("\n📤 Exporting with optimized data...")
df = loader_optimized.df.copy()
value_date = loader_optimized.current_date
fye = loader_optimized.fiscal_year_end

exporter = FSExcelExporter(
    enriched_df=df,
    value_date=value_date,
    fiscal_year_end=fye,
    output_path="output/income_statement.xlsx"
)

exporter.export()
print("✅ Export completed successfully!")

############ MAKING EXCEL VS CSV COMPARISONS  ABOVE ############



# import pandas as pd
# import time
# from services.loaders.fsaccount_loader import FSAccountLoader
# from services.exporter.fs_excel_exporter_backup import FSExcelExporter
# from config import TB_PATH, COA_PATH

# print("Loading Financial Data with CSV Optimization")
# print("=" * 50)

# # Load using CSV cache optimization
# print("\n🚀 Loading data with CSV optimization...")
# start_time = time.time()

# loader = FSAccountLoader(TB_PATH, COA_PATH, use_csv_cache=True)
# loader.load_and_store()

# loading_time = time.time() - start_time
# print(f"⏱️ Data loaded in: {loading_time:.2f} seconds")

# # Display data info
# df = loader.df
# print(f"\n📊 Data loaded successfully:")
# print(f"   Shape: {df.shape}")
# print(f"   Columns: {list(df.columns)}")

# # Export to Excel
# print("\n📤 Exporting to Excel...")
# value_date = loader.current_date
# fye = loader.fiscal_year_end

# exporter = FSExcelExporter(
#     enriched_df=df.copy(),
#     value_date=value_date,
#     fiscal_year_end=fye,
#     output_path="output/income_statement.xlsx"
# )

# exporter.export()
# print("✅ Export completed successfully!")

############ CSV ONLY LOADER ABOVE ############
