from services.charts.base_chart import BaseChart
import pandas as pd
from cache.memory_store import memory_store
from config import COMPANY_NAME, CURRENCY, DENOMINATION, DEFAULT_FISCAL_YEAR_END, CURRENT_DATE_INPUT
from datetime import datetime
from services.chart_registry import register_chart
from utils.filter_resolution import PeriodResolver

@register_chart(
    "top_products",
    category="sales",
    supports_periods=False,
    supports_top_n=True,
    supports_period_type=True
)
class TopProductsChart(BaseChart):
    def get_chart_data(self):
        df = self.df

        # ✅ Apply fiscal period date filtering
        if self.selected_period:
            period_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
            if period_range:
                start, end = period_range["start"], period_range["end"]
                df = df[(df["date"] >= start) & (df["date"] <= end)]

        # ✅ Apply generic filters
        df = self.apply_filters(df)

        # ✅ Filter by resolved months (YTD/LTM)
        resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type=self.period_type,
            selected_months=self.filters.get("dates", []),
            selected_quarters=[],
            selected_years=[],
            memory_store={"active_time_filter_type": "dates"}
        )
        months_to_keep = resolver.resolve_months()
        df = df[df["month"].isin(months_to_keep)]

        # ✅ Group and rank products
        grouped = df.groupby("product")["amount"].sum().reset_index()
        grouped = grouped.sort_values(by="amount", ascending=False)

        top_n = self.extra.get("top_n", 10)
        actual_n = min(top_n, len(grouped))
        grouped = grouped.head(actual_n)

        labels = grouped["product"].fillna("Unknown").tolist()
        sales = grouped["amount"].round(2).tolist()


        available_products = df["product"].nunique()
        current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()

        return {
            "labels": labels,
            "datasets": [{
                "label": f"Top {actual_n} products",
                "data": sales
            }],
            "currency": CURRENCY,
            "denomination": DENOMINATION,
            "company": COMPANY_NAME,
            "available_product_count": available_products,
            "updated_filters": self.get_updated_filters(df),
            "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,
             "current_date": current_date.isoformat()
        }

    def get_updated_filters(self, df: pd.DataFrame) -> dict:
        updated = {}

        # Filter only from selected period range
        if self.selected_period:
            period_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
            if period_range:
                start, end = period_range["start"], period_range["end"]
                df = df[(df["date"] >= start) & (df["date"] <= end)]

        updated["dates"] = sorted(df["month"].dropna().unique().tolist())

        # Add filters for the chart
        for key in ["product", "currency", "location", "customer"]:
            if key in df.columns:
                updated[key] = sorted(df[key].dropna().unique().tolist())

        updated["allowed_filters"] = ["dates", "product", "currency", "location", "customer"]

        return updated

@register_chart(
    "top_products_by_average_selling_price",
    category="sales",
    supports_periods=False,
    supports_top_n=True,
    supports_period_type=True
)
class TopProductsByAverageChart(BaseChart):
    def get_chart_data(self):
        df = self.df

        # Apply filters
        if self.selected_period:
            period_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
            if period_range:
                start, end = period_range["start"], period_range["end"]
                df = df[(df["date"] >= start) & (df["date"] <= end)]

        df = self.apply_filters(df)

        resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type=self.period_type,
            selected_months=self.filters.get("dates", []),
            selected_quarters=[],
            selected_years=[],
            memory_store={"active_time_filter_type": "dates"}
        )
        months_to_keep = resolver.resolve_months()
        df = df[df["month"].isin(months_to_keep)]

        # Group by average price
        grouped = df.groupby("product")["price"].mean().reset_index()
        grouped = grouped.sort_values(by="price", ascending=False)

        top_n = self.extra.get("top_n", 10)
        actual_n = min(top_n, len(grouped))
        grouped = grouped.head(actual_n)

        labels = grouped["product"].fillna("Unknown").tolist()
        averages = grouped["price"].round(2).tolist()

        available_products = df["product"].nunique()
        current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()


        return {
            "labels": labels,
            "datasets": [{
                "label": f"Top {actual_n} products by average sale",
                "data": averages
            }],
            "currency": CURRENCY,
            "denomination": DENOMINATION,
            "company": COMPANY_NAME,
            "available_product_count": available_products,
            "updated_filters": self.get_updated_filters(df),
            "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,
            "current_date": current_date.isoformat()
        }

@register_chart(
    "top_products_by_volume",
    category="sales",
    supports_periods=False,
    supports_top_n=True,
    supports_period_type=True
)
class TopProductsByVolumeChart(BaseChart):
    def get_chart_data(self):
        df = self.df

        if self.selected_period:
            period_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
            if period_range:
                start, end = period_range["start"], period_range["end"]
                df = df[(df["date"] >= start) & (df["date"] <= end)]

        df = self.apply_filters(df)

        resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type=self.period_type,
            selected_months=self.filters.get("dates", []),
            selected_quarters=[],
            selected_years=[],
            memory_store={"active_time_filter_type": "dates"}
        )
        months_to_keep = resolver.resolve_months()
        df = df[df["month"].isin(months_to_keep)]

        # Group by total quantity (true volume)
        if "quantity" not in df.columns:
            raise ValueError("Missing 'quantity' column in dataset for volume-based chart.")

        grouped = df.groupby("product")["quantity"].sum().reset_index(name="volume")
        grouped = grouped.sort_values(by="volume", ascending=False)

        top_n = self.extra.get("top_n", 10)
        actual_n = min(top_n, len(grouped))
        grouped = grouped.head(actual_n)

        labels = grouped["product"].fillna("Unknown").tolist()
        counts = grouped["volume"].round(2).tolist()


        current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()
        available_products = df["product"].nunique()

        return {
            "labels": labels,
            "datasets": [{
                "label": f"Top {actual_n} products by volume",
                "data": counts
            }],
            "currency": CURRENCY,
            "denomination": DENOMINATION,
            "company": COMPANY_NAME,
            "available_product_count": available_products,
            "updated_filters": self.get_updated_filters(df),
            "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,
            "current_date": current_date.isoformat()
        }
