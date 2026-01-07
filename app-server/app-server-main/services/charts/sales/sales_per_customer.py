from services.charts.base_chart import BaseChart
from services.chart_registry import register_chart
from utils.chart_utils import pivot_and_group
from utils.filter_resolution import PeriodResolver
from cache.memory_store import memory_store

import pandas as pd

@register_chart(
    "sales_per_customer",
    category="sales",
    supports_periods=True,
    supports_top_n=False,
    supports_period_type=True
)
class SalesPerCustomerChart(BaseChart):
    def get_chart_data(self):
        print("\n🚀 [Chart] Starting SalesPerCustomerChart.get_chart_data")
        df = self.df

        df = self.apply_filters(df)
        df, group_col = self.apply_period_filter(df)

        resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type=self.period_type,
            selected_months=self.filters.get("dates", []),
            selected_quarters=self.filters.get("quarters", []),
            selected_years=self.filters.get("years", []),
            memory_store={
                "active_time_filter_type": getattr(self, "active_time_filter_type", None)
            }
        )

        months_to_keep = resolver.resolve_months()
        print(f"🧮 Selected Period: {self.selected_period}")
        print(f"📅 Period Type: {self.period_type}")
        print(f"📦 Months in scope: {months_to_keep}")
        print(f"🔢 Month count: {len(months_to_keep)}")

        selected_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
        if selected_range:
            start = selected_range["start"]
            end = selected_range["end"]
            df_selected = df[(df["date"] >= start) & (df["date"] <= end)]
            df_other = df[~((df["date"] >= start) & (df["date"] <= end))]
            df_selected = df_selected[df_selected["month"].isin(months_to_keep)]

            if self.selected_period and self.period_type == "Annual":
                print(f"\n📊 Debug for Annual Period: {self.selected_period}")
                
                monthly_breakdown = (
                    df_selected.groupby("month")["amount"]
                    .sum()
                    .reset_index()
                    .sort_values(by="month", key=lambda x: pd.to_datetime(x))
                )

                for _, row in monthly_breakdown.iterrows():
                    print(f"   📅 {row['month']}: {row['amount']:,.2f}")

                total = monthly_breakdown["amount"].sum()
                print(f"   ➕ Total across all months for {self.selected_period}: {total:,.2f}")
                print(f"   👤 Unique customers in {self.selected_period}: {df_selected['customer'].nunique()}")
                print(f"   📊 Sales per customer for {self.selected_period}: {total / df_selected['customer'].nunique():,.2f}")


            df = pd.concat([df_selected, df_other], ignore_index=True)

        available_periods = memory_store[self.dataset_id]["filters"].get(group_col, [])
        if self.period_type in ["Monthly", "Quarterly"] and self.selected_period:
            all_periods = [p for p in available_periods if self.selected_period in p]
        elif self.period_type == "Yearly":
            all_periods = sorted([
                p for p in available_periods if p.startswith("F") or p.startswith("YTD") or p.startswith("LTM")
            ])
        else:
            all_periods = available_periods

        grouped = df.groupby(group_col).agg(
            total_sales=("amount", "sum"),
            unique_customers=("customer", pd.Series.nunique)
        ).reset_index()

        grouped["sales_per_customer"] = grouped["total_sales"] / grouped["unique_customers"]
        grouped = grouped.sort_values(group_col)
        if group_col == "month":
            # Convert full month strings like "April 2023" to datetime
            grouped["month_dt"] = pd.to_datetime(grouped["month"], format="%B %Y", errors="coerce")
            grouped = grouped.sort_values("month_dt")
            labels = grouped["month"].astype(str).tolist()
        else:
            grouped = grouped.sort_values(group_col)
            labels = grouped[group_col].astype(str).tolist()


        labels = grouped[group_col].astype(str).tolist()
        values = grouped["sales_per_customer"].round(2).tolist()

        print("🚨 Month labels before sorting:", labels)

        datasets = [{
            "label": "Sales per Customer",
            "data": values
        }]

        return {
            **self.build_response(labels=labels, datasets=datasets),
            "updated_filters": self.get_updated_filters(df),
            "monthly_datasets": self._build_additional_dataset("Monthly"),
            "quarterly_datasets": self._build_additional_dataset("Quarterly"),
            "annual_datasets": self._build_additional_dataset("Annual")
        }

    def _build_additional_dataset(self, period_type):
        try:
            temp_chart = self.__class__(
                dataset_id=self.dataset_id,
                period_type=period_type,
                selected_period=self.selected_period,
                filters=self.filters
            )

            df = temp_chart.df
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

            months_to_keep = resolver.resolve_months()
            df = df[df["month"].isin(months_to_keep)]

            if period_type in ["Monthly", "Quarterly"] and self.selected_period:
                filtered_periods = [p for p in available_periods if self.selected_period in p]
            elif period_type == "Annual":
                filtered_periods = sorted([
                    p for p in available_periods if p.startswith("F") or p.startswith("YTD") or p.startswith("LTM")
                ])
            else:
                filtered_periods = available_periods

            if period_type == "Annual":
                period_ranges = memory_store[self.dataset_id]["period_ranges"]
                annual_data = []

                for label in filtered_periods:
                    date_range = period_ranges.get(label)
                    if not date_range:
                        continue

                    start = date_range["start"]
                    end = date_range["end"]
                    df_period = df[(df["date"] >= start) & (df["date"] <= end)]
                    df_period = df_period[df_period["month"].isin(months_to_keep)]
                    df_period = df_period.copy()
                    df_period[group_col] = label

                    # 🔍 DEBUG LOGGING
                    if label == self.selected_period:
                        print(f"\n📊 Debug (inside _build_additional_dataset) for {label}")
                        monthly = (
                            df_period.groupby("month")["amount"]
                            .sum()
                            .reset_index()
                            .sort_values(by="month", key=lambda x: pd.to_datetime(x))
                        )
                        for _, row in monthly.iterrows():
                            print(f"   📅 {row['month']}: {row['amount']:,.2f}")
                        print(f"   ➕ Total across all months for {label}: {monthly['amount'].sum():,.2f}")



                    annual_data.append(df_period)

                df = pd.concat(annual_data, ignore_index=True)


            grouped = df.groupby(group_col).agg(
                total_sales=("amount", "sum"),
                unique_customers=("customer", pd.Series.nunique)
            ).reset_index()

            grouped["sales_per_customer"] = grouped["total_sales"] / grouped["unique_customers"]
            grouped = grouped.sort_values(group_col)
            if group_col == "month":
                # Convert full month strings like "April 2023" to datetime
                grouped["month_dt"] = pd.to_datetime(grouped["month"], format="%B %Y", errors="coerce")
                grouped = grouped.sort_values("month_dt")
                labels = grouped["month"].astype(str).tolist()
            else:
                grouped = grouped.sort_values(group_col)
                labels = grouped[group_col].astype(str).tolist()


            labels = grouped[group_col].astype(str).tolist()
            values = grouped["sales_per_customer"].round(2).tolist()

            return {
                "labels": labels,
                "datasets": [{
                    "label": "Sales per Customer",
                    "data": values
                }]
            }

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
