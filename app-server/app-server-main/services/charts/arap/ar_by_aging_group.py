from services.charts.base_chart import BaseChart
import pandas as pd
from services.chart_registry import register_chart
from config import COMPANY_NAME, CURRENCY, DENOMINATION, DEFAULT_FISCAL_YEAR_END, CURRENT_DATE_INPUT
from datetime import datetime

from cache.memory_store import memory_store


@register_chart(
    "ar_by_aging_group",
    category="accounts_receivable",
    supports_periods=False,
    supports_period_type=True,
    supports_top_n=False
)

class ARByAgingGroupChart(BaseChart):
    def get_chart_data(self):
        df = self.df
        df = df[df.get("data_type") == "AR"]
        df = self.apply_filters(df)

        print("🔍 Received filters:", self.filters)

        if df.empty or "aging_group" not in df.columns:
            print("⚠️ DataFrame empty or missing aging_group column")
            return self.build_response(labels=[], datasets=[])

        chart_type = self.extra.get("chart_type", "").lower()
        selected_period = self.selected_period
        print(f"📊 Chart Type: {chart_type}")
        print(f"📆 Selected Period: {selected_period}")
        
        if chart_type == "pie" and selected_period:
            if selected_period.startswith("F"):
                df = df[df["fiscal_year"] == selected_period]
            elif selected_period.startswith("LTM"):
                df = df[df["ltm"] == selected_period]

        if chart_type == "pie":
            if df.empty:
                print("⚠️ No matching data found for pie chart")
                return self.build_response(labels=[], datasets=[])

            grouped = df.groupby("aging_group")["amount"].sum()
            labels = [str(label).capitalize() for label in grouped.index.tolist()]
            values = [round(val, 2) for val in grouped.values]

            print("✅ Pie chart output:", list(zip(labels, values)))

            datasets = [{
                "label": "Aging Group Breakdown",
                "data": values
            }]
            updated_filters = self.get_updated_filters(df)
            current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()
            return {
                **self.build_response(labels=labels, datasets=datasets),
                "updated_filters": updated_filters,
                "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,
                "current_date": current_date.isoformat()
            }

        else:
            # Bar / stacked bar across periods
            print("📊 Rendering bar/stacked chart")

            period_ranges = memory_store.get(self.dataset_id, {}).get("period_ranges", {})
            all_periods = sorted(period_ranges.keys())

            period_data = []
            for period in all_periods:
                if period.startswith("F"):
                    temp = df[df["fiscal_year"] == period]
                elif period.startswith("LTM"):
                    temp = df[df["ltm"] == period]
                    if not temp.empty and "date" in temp.columns:
                        latest_date = temp["date"].max()
                        temp = temp[temp["date"] == latest_date]

                else:
                    continue  # unknown label format

                grouped = temp.groupby("aging_group")["amount"].sum()
                grouped.name = period
                period_data.append(grouped)

            if not period_data:
                print("⚠️ No data found across all periods.")
                return self.build_response(labels=[], datasets=[])

            combined = pd.DataFrame(period_data).fillna(0).round(2)

            print("📈 Grouped shape:", combined.shape)

            datasets = [
                {
                    "label": str(ag).capitalize(),
                    "data": combined[ag].tolist(),
                    "stack": "AR Aging"
                }
                for ag in combined.columns
            ]

            updated_filters = self.get_updated_filters(df)
            current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()
            return {
                **self.build_response(labels=combined.index.tolist(), datasets=datasets),
                "updated_filters": updated_filters,
                "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,
                "current_date": current_date.isoformat()
            }
