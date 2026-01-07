from services.charts.base_chart import BaseChart
import pandas as pd
from cache.memory_store import memory_store
from utils.chart_utils import pivot_and_group
from utils.filter_resolution import PeriodResolver
from services.chart_registry import register_chart

@register_chart(
    "sales_volume_and_average_price_by_product",
    category="sales",
    supports_periods=True,
    supports_top_n=False,
    supports_period_type=True
)
class ComboSalesVolumeAvgPriceChart(BaseChart):
    @staticmethod
    def selected_period_is_valid(selected_period, df, months, quarters, years):
        if selected_period in years:
            return True
        if selected_period in df["ltm"].unique():
            return True
        if selected_period in df["ytd"].unique():
            return True
        if months:
            months_years = set(df[df["month"].isin(months)]["fiscal_year"].unique())
            if selected_period in months_years:
                return True
        if quarters:
            quarters_years = set(df[df["fiscal_quarter"].isin(quarters)]["fiscal_year"].unique())
            if selected_period in quarters_years:
                return True
        return False

    def get_chart_data(self):
        print("\n🚀 [Chart] Starting ComboSalesVolumeAvgPriceChart.get_chart_data")
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
            memory_store={"active_time_filter_type": getattr(self, "active_time_filter_type", None)}
        )
        months_to_keep = resolver.resolve_months()

        if not self.selected_period_is_valid(
            selected_period=self.selected_period,
            df=df,
            months=resolver.selected_months,
            quarters=resolver.selected_quarters,
            years=resolver.selected_years
        ):
            return {"labels": [], "datasets": [], "updated_filters": {}}

        selected_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
        if selected_range:
            start, end = pd.to_datetime(selected_range["start"]), pd.to_datetime(selected_range["end"])
            df_selected = df[(df["date"] >= start) & (df["date"] <= end)]
            df_selected = df_selected[df_selected["month"].isin(months_to_keep)]
            df_other = df[~((df["date"] >= start) & (df["date"] <= end))]
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

        # Group by period and product, compute sum and average safely
        grouped = df.groupby([group_col, "product"]).agg({
            "amount": "sum",
            "quantity": "sum"
        }).reset_index()
        grouped["average_price"] = grouped["amount"] / grouped["quantity"].replace(0, pd.NA)

        # Pivot both metrics
        pivot_volume, periods = pivot_and_group(grouped, group_col, "product", "quantity", all_periods=all_periods)
        pivot_price, _ = pivot_and_group(grouped, group_col, "product", "average_price", all_periods=all_periods, sort_periods=False)

        # Datasets
        volume_datasets = [
            {
                "label": f"{str(product)} Volume",
                "data": [float(round(pivot_volume.loc[product, p], 2)) for p in periods],
                "type": "bar"
            }
            for product in pivot_volume.index
        ]

        price_datasets = [
            {
                "label": f"{str(product)} Avg Price",
                "data": [float(round(pivot_price.loc[product, p], 2)) for p in periods],
                "type": "line",
                "yAxisID": "y1"
            }
            for product in pivot_price.index
        ]

        updated_filters = self.get_updated_filters(df)

        return {
            **self.build_response(labels=periods, datasets=volume_datasets + price_datasets),
            "updated_filters": updated_filters,
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
                memory_store={"active_time_filter_type": getattr(self, "active_time_filter_type", None)}
            )

            months_to_keep = resolver.resolve_months()
            if period_type == "Annual":
                period_ranges = memory_store[self.dataset_id]["period_ranges"]
                annual_data = []

                for label in available_periods:
                    if not (label.startswith("F") or label.startswith("YTD") or label.startswith("LTM")):
                        continue

                    date_range = period_ranges.get(label)
                    if not date_range:
                        continue

                    start = date_range["start"]
                    end = date_range["end"]

                    df_period = df[(df["date"] >= start) & (df["date"] <= end)]

                    # Optional: filter by months_to_keep if you want month scoping
                    if self.selected_period and self.selected_period == label:
                        df_period = df_period[df_period["month"].isin(months_to_keep)]


                    df_period = df_period.copy()
                    df_period[group_col] = label  # overwrite period col to ensure correct pivot

                    annual_data.append(df_period)

                df = pd.concat(annual_data, ignore_index=True)
                filtered_periods = sorted(df[group_col].dropna().unique().tolist())

            else:
                df = df[df["month"].isin(months_to_keep)]

            if period_type in ["Monthly", "Quarterly"] and self.selected_period:
                filtered_periods = [p for p in available_periods if self.selected_period in p]
            elif period_type == "Annual":
                filtered_periods = sorted([
                    p for p in available_periods if p.startswith("F") or p.startswith("YTD") or p.startswith("LTM")
                ])
            else:
                filtered_periods = available_periods

            grouped = df.groupby([group_col, "product"]).agg({
                "amount": "sum",
                "quantity": "sum"
            }).reset_index()
            grouped["average_price"] = grouped["amount"] / grouped["quantity"].replace(0, pd.NA)

            pivot_volume, periods = pivot_and_group(grouped, group_col, "product", "quantity", all_periods=filtered_periods)
            pivot_price, _ = pivot_and_group(grouped, group_col, "product", "average_price", all_periods=filtered_periods, sort_periods=False)

            volume_datasets = [
                {
                    "label": f"{str(product)} Volume",
                    "data": [float(round(pivot_volume.loc[product, p], 2)) for p in periods],
                    "type": "bar"
                }
                for product in pivot_volume.index
            ]

            price_datasets = [
                {
                    "label": f"{str(product)} Avg Price",
                    "data": [float(round(pivot_price.loc[product, p], 2)) for p in periods],
                    "type": "line",
                    "yAxisID": "y1"
                }
                for product in pivot_price.index
            ]

            return {"labels": periods, "datasets": volume_datasets + price_datasets}

        except Exception as e:
            print(f"⚠️ Error in _build_additional_dataset({period_type}):", e)
            return {"labels": [], "datasets": []}
