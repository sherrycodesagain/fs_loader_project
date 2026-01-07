from services.charts.base_chart import BaseChart
import pandas as pd
from services.chart_registry import register_chart
from config import COMPANY_NAME, CURRENCY, DENOMINATION, DEFAULT_FISCAL_YEAR_END, CURRENT_DATE_INPUT
from datetime import datetime


from cache.memory_store import memory_store

@register_chart(
    "top_ar_balances_by_customer",
    category="accounts_receivable",
    supports_periods=False,
    supports_period_type=True,
    supports_top_n=True
)
class ARByCustomerChart(BaseChart):
    def get_chart_data(self):
        df = self.df
        print(f"📊 Starting ARByCustomerChart for period: {self.selected_period}")

        #  Filter for AR only
        df = df[df.get("data_type") == "AR"]

        #  Apply global filters (e.g. customer, currency)
        df = self.apply_filters(df)
        print("📅 Unique Fiscal Years in dataset:", df["fiscal_year"].unique())
        print("🧪 Selected Period:", self.selected_period)

 
        #  Filter by customer if provided via self.extra (for drilldown)
        selected_customer = self.extra.get("customer")
        if selected_customer:
            df = df[df["customer"] == selected_customer]
 
        #  Enforce selected_period
        if not self.selected_period:
            raise ValueError("Missing required 'selected_period' for ARByCustomerChart")

        if self.selected_period.startswith("F"):
            df = df[df["fiscal_year"] == self.selected_period]
        elif self.selected_period.startswith("YTD"):
            df = df[df["ytd"] == self.selected_period]
        elif self.selected_period.startswith("LTM"):
            df = df[df["ltm"] == self.selected_period]

        if "date" in df.columns and not df.empty:
            latest_date = df["date"].max()
            df = df[df["date"] == latest_date]
          
        # 🐞 DEBUG: Show pivoted table of AR by customer and aging group
        debug_pivot = df.pivot_table(
            index="customer",
            columns="aging_group",
            values="amount",
            aggfunc="sum",
            fill_value=0
        ).round(2)

        debug_pivot["Total"] = debug_pivot.sum(axis=1)
        debug_pivot = debug_pivot.sort_values("Total", ascending=False)

        print("\n🧾 AR Aging Summary (latest month in period):")
        print(debug_pivot.to_string())

        if df.empty or "customer" not in df.columns or "aging_group" not in df.columns:
            print("⚠️ No data after period/customer/aging_group filters.")
            return {
                **self.build_response(labels=[], datasets=[]),
                "available_customer_count": 0,
                "updated_filters": {}
            }

        df_for_filters = df.copy()
        available_customers = df_for_filters["customer"].nunique()
    

        top_n = self.extra.get("top_n", 10)
        top_customers = (
            df.groupby("customer")["amount"]
            .sum()
            .nlargest(top_n)
            .index
        )

        df = df[df["customer"].isin(top_customers)]

        grouped = (
            df.groupby(["customer", "aging_group"])["amount"]
            .sum()
            .unstack(fill_value=0)
        )
        print(
            df[df["customer"] == "Astral Antiques"]
            [["date", "currency", "aging_group", "amount"]]
            .sort_values(by=["currency", "aging_group"])
            .to_string(index=False)
        )
        grouped["__total"] = grouped.sum(axis=1)
        grouped = grouped.sort_values("__total", ascending=False).drop(columns="__total")


        datasets = [
            {
                "label": aging_group.capitalize(),
                "data": [round(grouped.at[customer, aging_group], 2) for customer in grouped.index],
                "stack": "AR"
            }
            for aging_group in grouped.columns
        ]

        updated_filters = self.get_updated_filters(df_for_filters, limit_to_keys={"customer": df["customer"].unique().tolist()})
        current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()

        return {
            "labels": grouped.index.tolist(),
            "datasets": datasets,
            "currency": CURRENCY,
            "denomination": DENOMINATION,
            "company": COMPANY_NAME,
            "available_customer_count": available_customers,
            "updated_filters": updated_filters,
            "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,
             "current_date": current_date.isoformat()
        }
