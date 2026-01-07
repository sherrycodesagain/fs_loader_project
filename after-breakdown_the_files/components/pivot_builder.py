import pandas as pd
from cache.memory_store import memory_store

class PivotBuilder:
    def __init__(self, base_exporter):
        self.base = base_exporter
        
    def build_pivots(self):
        print("[INFO] Building annual pivot...")
        df = self.base.df.copy()
        df = df[df["type"] == "IS"]  # Only include income statement accounts
        valid_fys = memory_store[self.base.df["dataset_id"].iloc[0]]["valid_fiscal_years"]

        fy_rows = df[df["fiscal_year"].isin(valid_fys)].copy()
        fy_rows["column_label"] = fy_rows["fiscal_year"]

        ltm_rows = df[df["ltm"].str.strip().astype(bool)].copy()
        ltm_rows["column_label"] = ltm_rows["ltm"]

        # Combine both
        df = pd.concat([fy_rows, ltm_rows], ignore_index=True)
        # Drop rows without a column label
        df = df[df["column_label"].notna() & df["column_label"].str.strip().astype(bool)]

        # Build pivot table
        self.base.annual_pivot = pd.pivot_table(
            df,
            index=["fs_grouping", "detailed_grouping", "account"],
            columns="column_label",
            values="ending_balance",
            aggfunc="sum",
            fill_value=0
        )
        
        print("[DEBUG] Sales rows in pivot (any column):")
        for idx in self.base.annual_pivot.index:
            if idx[0].strip().lower() == "sales":
                print(f"{idx}: {self.base.annual_pivot.loc[idx].to_dict()}")

        # Sort columns: Fiscal years first, then YTD, then LTM
        cols = list(self.base.annual_pivot.columns)

        def sort_key(label):
            if label.startswith("F") and label[1:].isdigit():
                return (0, int(label[1:]))  
            if label.startswith("YTD"):
                return (1, label)
            if label.startswith("LTM"):
                return (2, label)
            return (3, label)
            
        print("[INFO] Building monthly pivot...")
        monthly_df = self.base.df.copy()
        monthly_df = monthly_df[monthly_df["type"] == "IS"]
        monthly_df = monthly_df[monthly_df["month"].notna()]
        monthly_df["column_label"] = pd.to_datetime(monthly_df["date"]) + pd.offsets.MonthEnd(0)
        monthly_df["column_label"] = monthly_df["column_label"].dt.strftime("%d-%b-%y")

        self.base.monthly_pivot = pd.pivot_table(
            monthly_df,
            index=["fs_grouping", "detailed_grouping", "account"],
            columns="column_label",
            values="ending_balance",
            aggfunc="sum",
            fill_value=0
        )

        # Sort by calendar date, not alphabetical month names
        self.base.monthly_pivot = self.base.monthly_pivot.reindex(
            sorted(self.base.monthly_pivot.columns, key=lambda m: pd.to_datetime(m)),
            axis=1
        )
        
        print("[INFO] Building quarterly pivot...")
        quarterly_df = self.base.df.copy()
        quarterly_df = quarterly_df[quarterly_df["type"] == "IS"]
        quarterly_df = quarterly_df[quarterly_df["fiscal_quarter"].notna()]
        quarterly_df["column_label"] = quarterly_df["fiscal_quarter"]

        self.base.quarterly_pivot = pd.pivot_table(
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

        self.base.quarterly_pivot = self.base.quarterly_pivot.reindex(
            sorted(self.base.quarterly_pivot.columns, key=quarter_sort_key),
            axis=1
        )

        self.base.annual_pivot = self.base.annual_pivot.reindex(sorted(cols, key=sort_key), axis=1)