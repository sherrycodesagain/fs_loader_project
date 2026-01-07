from services.charts.base_chart import BaseChart
from services.chart_registry import register_chart
from utils.filter_resolution import PeriodResolver
from utils.chart_utils import pivot_and_group
from cache.memory_store import memory_store
import pandas as pd
from config import DEFAULT_FISCAL_YEAR_END, CURRENT_DATE_INPUT
from datetime import datetime
GROUPING_FIELDS = [
    "top_level_grouping",
    "fs_grouping",
    "detailed_grouping",
    "account_name"
]

@register_chart(
    "financial_statement_accounts",
    category="financials",
    supports_periods=True,
    supports_period_type=True,
    supports_top_n=False
)
class FSAccountsChart(BaseChart):
    def get_chart_data(self):
        print("\n📊 [Chart] Starting FSAccountsChart.get_chart_data")
        df = self.df.copy()
        accounts = set(self.extra.get("accounts", []))
        if not accounts:
            raise ValueError("Accounts not provided")
        matched_rows = []
        matched_indices = set()

        for label in accounts:
            for field in GROUPING_FIELDS:
                if field in df.columns:
                    subset = df[df[field] == label].copy()
                    if not subset.empty:
                        # Avoid duplicates
                        subset = subset[~subset.index.isin(matched_indices)]
                        matched_indices.update(subset.index)
                        subset["group_key"] = label
                        matched_rows.append(subset)

        if not matched_rows:
            raise ValueError("No matching accounts found for selection")

        df = pd.concat(matched_rows, ignore_index=True)
        df = self.apply_filters(df)
        df, group_col = self.apply_period_filter(df)

        resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type=self.period_type,
            selected_months=self.filters.get("dates", []),
            selected_quarters=self.filters.get("quarters", []),
            selected_years=self.filters.get("years", []),
            memory_store={"active_time_filter_type": getattr(self, "active_time_filter_type", None)}
        )

        resolved_months = resolver.resolve_months()
        selected_months = self.filters.get("dates", [])
        months_to_keep = list(set(resolved_months).intersection(set(selected_months))) if selected_months else resolved_months
        selected_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
        if selected_range:
            start = selected_range["start"]
            end = selected_range["end"]
            
            df_selected = df[
                (df["date"] >= start) & (df["date"] <= end)
            ]

            df_selected = df_selected[df_selected["month"].isin(months_to_keep)]
            df_other = df[~((df["date"] >= start) & (df["date"] <= end))]
            df = pd.concat([df_selected, df_other], ignore_index=True)

        available_periods = memory_store[self.dataset_id]["filters"].get(group_col, [])
        if self.period_type == "Quarterly":
            print("\n🧪 [DEBUG: Quarterly Dataset]")
            print(f"🔍 Selected period: {self.selected_period}")
            print(f"📦 Group column: {group_col}")
            print(f"📁 Available periods: {available_periods}")
            print(f"📆 Filtered quarters (based on selected_period): {[p for p in available_periods if self.selected_period in p]}")

        if self.period_type == "Monthly":
            all_periods = resolved_months
        elif self.period_type == "Quarterly" and self.selected_period:
            
            all_periods = [p for p in available_periods if self.selected_period in p]
            print("all peruisd", all_periods)
        elif self.period_type == "Yearly":
            all_periods = sorted([
                p for p in available_periods if p.startswith("F") or p.startswith("YTD") or p.startswith("LTM")
            ])
        else:
            all_periods = available_periods
        #self._debug_month_coverage(all_periods, group_col)
   
        pivot, periods = self._build_fs_pivot(df, group_col, all_periods, self.period_type)

        print("📊 [DEBUG] Final Pivot Columns:", pivot.columns.tolist())
        print("📊 [DEBUG] Final Pivot Index:", pivot.index.tolist())
        print("📆 Periods to pull data for:", periods)

        datasets = [
            {"label": key, "data": [float(pivot.loc[key, p]) for p in periods]}
            for key in pivot.index
        ]
        updated_filters = self.get_updated_filters(df)
        current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()
        return {
            **self.build_response(labels=periods, datasets=datasets),
            "updated_filters": updated_filters,
            "monthly_datasets": self._build_additional_dataset("Monthly", accounts),
            "quarterly_datasets": self._build_additional_dataset("Quarterly", accounts),
            "annual_datasets": self._build_additional_dataset("Annual", accounts),
             "current_date": current_date.isoformat()
        }
    # # ── Place this right before you call pivot_and_group ────────────────────────
    # def _debug_month_coverage(self, all_periods, group_col):
    #     period_map = memory_store[self.dataset_id]["period_ranges"]
    #     print("\n🗓️  [DEBUG] Month coverage per period label:")
    #     for label in all_periods:
    #         meta = period_map.get(label)



    #         if not meta:
    #             print(f"  • {label:<12}  →  ❌ not in period_ranges")
    #             continue
    #         months = meta["months"]
    #         print(f"  • {label:<12}  →  {len(months):2d} months | {months}")

   
    def match_account_rows(self, df, accounts):
        matched_rows = []
        matched_indices = set()
        for label in accounts:
            for field in GROUPING_FIELDS:
                if field in df.columns:
                    subset = df[df[field] == label].copy()
                    if not subset.empty:
                        subset = subset[~subset.index.isin(matched_indices)]
                        matched_indices.update(subset.index)
                        subset["group_key"] = label
                        matched_rows.append(subset)
        return pd.concat(matched_rows, ignore_index=True) if matched_rows else pd.DataFrame()


    def _build_fs_pivot(self, df, group_col, all_periods, period_type: str):

        if "group_key" not in df.columns:
            print("❗ [DEBUG] 'group_key' missing in pivot DataFrame. Available columns:", df.columns.tolist())
        else:
            print("✅ [DEBUG] 'group_key' present in pivot DataFrame.")

        
        is_df = df[df["type"] == "IS"].copy()
        bs_df = df[df["type"] == "BS"].copy()

        if period_type in [ "Annual"]:
            period_ranges = memory_store[self.dataset_id]["period_ranges"]
            print("peeriod_ranges", period_ranges)
            period_filtered_dfs = []

            for label in all_periods:
                meta = period_ranges.get(label)
                if not meta:
                    continue

                start, end = meta["start"], meta["end"]
                valid_months = meta.get("months", [])

                subset = is_df[(is_df["date"] >= start) & (is_df["date"] <= end)]
                subset = subset[subset["month"].isin(valid_months)]
                subset = subset.copy()
                subset["Period"] = label
                period_filtered_dfs.append(subset)

            is_df = pd.concat(period_filtered_dfs, ignore_index=True) if period_filtered_dfs else pd.DataFrame()
        else:
            is_df["Period"] = is_df[group_col]

        period_dfs = []

        if period_type == "Monthly":
            # For Monthly, pivot on the calendar-month
            temp = bs_df.copy()
            temp["Period"] = temp["month"]
            temp = temp[temp["Period"].isin(all_periods)]
            period_dfs.append(temp)

        elif period_type == "Quarterly":
            temp = bs_df.copy()
            temp["Period"] = temp[group_col]
            temp = temp[temp["Period"].isin(all_periods)]
            period_dfs.append(temp)

        else:
            # Annual: use the LTM/YTD/FY tags as before
            for col in ["ltm", "ytd", "fiscal_year"]:
                temp = bs_df.copy()
                temp["Period"] = temp[col]
                temp = temp[temp["Period"].isin(all_periods)]
                period_dfs.append(temp)

        bs_df = pd.concat(period_dfs, ignore_index=True) if period_dfs else pd.DataFrame()
        df["group_key"] = df.get("group_key", df.get("account_name", "Unknown"))

        # # ----------------- DEBUG: show latest month+value per BS period -------------
        # if not bs_df.empty:
        #     for period in sorted(bs_df["Period"].unique()):
        #         rows_this_period = bs_df[bs_df["Period"] == period]

        #         # latest date in that period
        #         latest_date = rows_this_period["date"].max()

        #         # rows that fall on that latest date (there can be several bank accounts etc.)
        #         latest_rows   = rows_this_period[rows_this_period["date"] == latest_date]

        #         # calendar label of the latest date (e.g. 'December 2023')
        #         latest_month  = latest_date.strftime("%B %Y")

        #         # total ending balance for that period at the latest date
        #         latest_total  = latest_rows["ending_balance"].sum()

        #         print(f"[DEBUG] BS Period '{period}': latest month = {latest_month}, "
        #             f"value = {latest_total:,.2f}")
        #         # optional: inspect individual rows
        #         # print(latest_rows[["account", "ending_balance"]])

        is_grouped = (
            is_df.groupby(["group_key", "Period"])["ending_balance"]
            .sum()
            .reset_index()
        )
              
        # print("\n📘 [DEBUG] IS Aggregation Breakdown by Period:")
        # for period in sorted(is_df["Period"].unique()):
        #     subset = is_df[is_df["Period"] == period]
        #     month_vals = (
        #         subset.groupby("month")["ending_balance"]
        #         .sum()
        #         .reset_index()
        #         .sort_values("month")
        #     )
        #     print(f" • {period}:")
        #     for _, row in month_vals.iterrows():
        #         print(f"    - {row['month']}: {row['ending_balance']:.2f}")
        #     total = subset["ending_balance"].sum()
        #     print(f"    ➕ IS Total for {period}: {total:,.2f}")


        if period_type in ["Quarterly", "Annual"]:
    
            # Find latest date per period
            latest_dates = (
                bs_df.groupby("Period")["date"].max().reset_index().rename(columns={"date": "latest_date"})
            )
            # Join to keep only rows from latest date per Period
            bs_df = bs_df.merge(latest_dates, on="Period")
            bs_filtered = bs_df[bs_df["date"] == bs_df["latest_date"]]
            

            # Group and sum all accounts on that latest date
            bs_grouped = (
                bs_filtered.groupby(["group_key", "Period"])["ending_balance"]
                .sum()
                .reset_index()
            )
        else:
            # Monthly: sum across all rows (normal)
            bs_grouped = (
                bs_df.groupby(["group_key", "Period"])["ending_balance"]
                .sum()
                .reset_index()
            )



        # Combine both
        final_df = pd.concat([is_grouped, bs_grouped], ignore_index=True)

        # Pivot using "Period" as the group_col
        pivot, periods = pivot_and_group(
            final_df,
            group_col="Period",
            index_col="group_key",
            value_col="ending_balance",
            all_periods=all_periods
        )

        return pivot, periods


    def _build_additional_dataset(self, period_type, accounts):
        try:
            temp_chart = self.__class__(
                dataset_id=self.dataset_id,
                period_type=period_type,
                selected_period=self.selected_period,
                filters=self.filters,
                extra={"accounts": list(accounts)}
            )
            print(f"\n📂 [DEBUG] Loaded temp_chart.df for period_type='{period_type}': {len(temp_chart.df) if temp_chart.df is not None else 'None'} rows")
            if temp_chart.df is not None:
                print("🧩 Columns in temp_chart.df:", list(temp_chart.df.columns))


            df = self.match_account_rows(temp_chart.df.copy(), accounts)
            df = self.match_account_rows(temp_chart.df.copy(), accounts)
            print(f"🔍 [DEBUG] After match_account_rows: {len(df)} rows")
            print("🧩 Columns after matching:", list(df.columns))


            if df.empty:
                return {"labels": [], "datasets": []}

            df = temp_chart.apply_filters(df)
            df, group_col = temp_chart.apply_period_filter(df)

            available_periods = memory_store[self.dataset_id]["filters"].get(group_col, [])

            resolver = PeriodResolver(
                df=df,
                period_type=period_type,
                selected_period=self.selected_period,
                selected_months=self.filters.get("dates", []),
                selected_quarters=self.filters.get("quarters", []),
                selected_years=self.filters.get("years", []),
                memory_store={
                    "active_time_filter_type": getattr(self, "active_time_filter_type", None)
                }
            )

            resolved_months = resolver.resolve_months()
            selected_months = self.filters.get("dates", [])
            months_to_keep = list(set(resolved_months).intersection(set(selected_months))) if selected_months else resolved_months

            if period_type == "Annual":
                df_selected = df[df["fiscal_year"] == self.selected_period]
                df_selected = df_selected[df_selected["month"].isin(months_to_keep)]
                df_other = df[df["fiscal_year"] != self.selected_period]
                df = pd.concat([df_selected, df_other], ignore_index=True)
            else:
                df = df[df["month"].isin(months_to_keep)]

            available_periods = memory_store[self.dataset_id]["filters"].get(group_col, [])

           # NEW: for Monthly use resolved_months; keep existing logic for Qtr/Annual
            if period_type == "Monthly":
                filtered_periods = resolver.resolve_months()
            elif period_type == "Quarterly" and self.selected_period:
                filtered_periods = [p for p in available_periods if self.selected_period in p]
            elif period_type == "Annual":
                filtered_periods = sorted(
                    p for p in available_periods
                    if p.startswith("F") or p.startswith("YTD") or p.startswith("LTM")
                )
            else:
                filtered_periods = available_periods

            
            # print(f"\n🔍 [DEBUG] Building {period_type} dataset")
            # print(f"🧭 Selected period: {self.selected_period}")
            # print(f"🧮 Group column: {group_col}")
            # print(f"📆 Months resolved by PeriodResolver: {resolved_months}")
            # print(f"🗓️ Months to keep (after intersecting filters): {months_to_keep}")
            # print(f"📦 Available periods for group_col: {available_periods}")
            # print(f"✅ Filtered periods to pivot: {filtered_periods}")
            # print(f"🧾 Rows in DataFrame before pivot: {len(df)}")

            print(f"\n📊 [DEBUG] Pivot input — period_type: {period_type}")
            print("🧮 Columns in DataFrame:", df.columns.tolist())
            print("🔢 Unique group_keys:", df["group_key"].unique() if "group_key" in df.columns else "❌ MISSING")

            pivot, periods = self._build_fs_pivot(df, group_col, filtered_periods, period_type)

            print("📊 [DEBUG] Pivot shape:", pivot.shape)
            print("🔢 Pivot index (group_key):", pivot.index.tolist())
            print("🧭 Pivot columns (periods):", pivot.columns.tolist())
            print("📆 Expected periods:", periods)


            datasets = [
                {"label": acc, "data": [float(pivot.loc[acc, p]) for p in periods]}
                for acc in pivot.index
            ]

            return {"labels": periods, "datasets": datasets, "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,}

        except Exception as e:
            print(f"⚠️ Error in _build_additional_dataset({period_type}):", e)
            return {"labels": [], "datasets": []}

    def get_updated_filters(self, df: pd.DataFrame) -> dict:
        updated = super().get_updated_filters(df)
        updated["dates"] = sorted(df["month"].dropna().unique().tolist())
        updated["quarters"] = sorted(df["fiscal_quarter"].dropna().unique().tolist())

        filters_meta = memory_store[self.dataset_id]["filters"]
        valid_fys = memory_store[self.dataset_id].get("valid_fiscal_years", [])

        fiscal_years = [fy for fy in filters_meta.get("fiscal_year", []) if fy in valid_fys]
        ytd_labels = filters_meta.get("ytd", [])
        ltm_labels = filters_meta.get("ltm", [])

        all_year_labels = set()
        for label in fiscal_years + ytd_labels + ltm_labels:
            label = str(label).strip()
            if label:
                all_year_labels.add(label)

        updated["years"] = sorted(all_year_labels, key=lambda x: (x[:3], x))
        return updated
