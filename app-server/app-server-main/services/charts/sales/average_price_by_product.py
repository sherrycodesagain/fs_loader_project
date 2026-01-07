from services.charts.base_chart import BaseChart
import pandas as pd
from utils.chart_utils import pivot_and_group
from services.chart_registry import register_chart
from utils.filter_resolution import PeriodResolver
from cache.memory_store import memory_store

@register_chart(
    "average_price_by_product",
    category="sales",
    supports_periods=True,
    supports_top_n=False,
    supports_period_type=True
)
class AveragePriceByProductChart(BaseChart):
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
        print("\n🚀 [Chart] Starting AveragePriceByProductChart.get_chart_data")

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
            df_other = df[~((df["date"] >= start) & (df["date"] <= end))]
            df_selected = df_selected[df_selected["month"].isin(months_to_keep)]
            df = pd.concat([df_selected, df_other], ignore_index=True)

        df = df[df["quantity"] > 0]
        df["average_price"] = df["amount"] / df["quantity"]

        available_periods = memory_store[self.dataset_id]["filters"].get(group_col, [])
        if self.period_type in ["Monthly", "Quarterly"] and self.selected_period:
            all_periods = [p for p in available_periods if self.selected_period in p]
        elif self.period_type == "Yearly":
            all_periods = sorted([p for p in available_periods if p.startswith("F") or p.startswith("YTD") or p.startswith("LTM")])
        else:
            all_periods = available_periods

        pivot, periods = pivot_and_group(
            df,
            group_col=group_col,
            index_col="product",
            value_col="average_price",
            all_periods=all_periods,
            agg_func="mean"
        )

        datasets = [
            {"label": product, "data": [float(round(pivot.loc[product, p], 2)) for p in periods]
}
            for product in pivot.index
        ]

        updated_filters = self.get_updated_filters(df)

        return {
            **self.build_response(labels=periods, datasets=datasets),
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
            df = df[df["quantity"] > 0]
            df["average_price"] = df["amount"] / df["quantity"]

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

            pivot, periods = pivot_and_group(
                df,
                group_col=group_col,
                index_col="product",
                value_col="average_price",
                all_periods=filtered_periods,
                agg_func="mean"
            )
            datasets = [
                {
                    "label": str(product),  # ⬅️ Force product label to string
                    "data": [float(round(pivot.loc[product, p], 2)) for p in periods]
                }
                for product in pivot.index
            ]


            return {"labels": periods, "datasets": datasets}

        except Exception as e:
            print(f"⚠️ Error in _build_additional_dataset({period_type}):", e)
            return {"labels": [], "datasets": []}

    def get_updated_filters(self, df: pd.DataFrame) -> dict:
        updated = super().get_updated_filters(df)
        updated["dates"] = sorted(str(x) for x in df["month"].dropna().unique().tolist())
        updated["quarters"] = sorted(str(x) for x in df["fiscal_quarter"].dropna().unique().tolist())

        filters_meta = memory_store[self.dataset_id]["filters"]
        valid_fys = memory_store[self.dataset_id].get("valid_fiscal_years", [])

        fiscal_years = [str(fy) for fy in filters_meta.get("fiscal_year", []) if fy in valid_fys]
        ytd_labels = [str(label) for label in filters_meta.get("ytd", [])]
        ltm_labels = [str(label) for label in filters_meta.get("ltm", [])]

        all_year_labels = set(fiscal_years + ytd_labels + ltm_labels)
        updated["years"] = sorted(all_year_labels, key=lambda x: (x[:3], x))
        return updated
