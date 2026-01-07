from services.charts.base_chart import BaseChart
import pandas as pd
from cache.memory_store import memory_store
from config import COMPANY_NAME, CURRENCY, DENOMINATION, DEFAULT_FISCAL_YEAR_END, CURRENT_DATE_INPUT
from datetime import datetime
from services.chart_registry import register_chart
from utils.filter_resolution import PeriodResolver

@register_chart(
    "top_customers",
    category="sales",
    supports_periods=False,
    supports_top_n=True,
    supports_period_type=True
)
class TopCustomersChart(BaseChart):
    def get_chart_data(self):
        df = self.df

        # Apply date filtering based on selected_period and period_ranges
        if self.selected_period:
            period_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
            if period_range:
                start, end = period_range["start"], period_range["end"]
                df = df[(df["date"] >= start) & (df["date"] <= end)]

        # Apply other filters like customer, location, etc.
        df = self.apply_filters(df)

        # Filter further by month using PeriodResolver
        resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type=self.period_type,
            selected_months=self.filters.get("dates", []),
            selected_quarters=[],  # ❌ Not supported
            selected_years=[],     # ❌ Not supported
            memory_store={"active_time_filter_type": "dates"}
        )
        months_to_keep = resolver.resolve_months()
        df = df[df["month"].isin(months_to_keep)]

        top_n = self.extra.get("top_n", 10)

        grouped = df.groupby("customer")["amount"].sum().reset_index()
        grouped = grouped.sort_values(by="amount", ascending=False).head(top_n)

        labels = grouped["customer"].fillna("Unknown").tolist()
        sales = grouped["amount"].round(2).tolist()

        available_customers = df["customer"].nunique()
        current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()
        return {
            "labels": labels,
            "datasets": [{
                "label": f"Top {top_n} customers",
                "data": sales
            }],
            "currency": CURRENCY,
            "denomination": DENOMINATION,
            "company": COMPANY_NAME,
            "available_customer_count": available_customers,
            "updated_filters": self.get_updated_filters(df),
            "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,
              "current_date": current_date.isoformat()

        }

    def get_updated_filters(self, df: pd.DataFrame) -> dict:
        updated = {}

        # ✅ Filter only rows from selected fiscal year range
        if self.selected_period:
            period_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
            if period_range:
                start, end = period_range["start"], period_range["end"]
                df = df[(df["date"] >= start) & (df["date"] <= end)]

        # ✅ Dates (Months)
        updated["dates"] = sorted(df["month"].dropna().unique().tolist())

        # ✅ Other supported filters
        for key in ["customer", "currency", "location", "product"]:
            if key in df.columns:
                updated[key] = sorted(df[key].dropna().unique().tolist())

        # ✅ Only allow relevant tabs
        updated["allowed_filters"] = ["dates", "customer", "currency", "location", "product"]

        return updated
