from services.charts.base_chart import BaseChart
import pandas as pd
from utils.chart_utils import pivot_and_group
from services.chart_registry import register_chart
from utils.filter_resolution import PeriodResolver
from cache.memory_store import memory_store

@register_chart(
    "sales_by_product",
    category="sales",
    supports_periods=True,
    supports_top_n=False,
    supports_period_type=True
)
class SalesByProductChart(BaseChart):
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

        # real_keys = self.filters.get("allowed_filters", [])
        # provided = [k for k in real_keys if k in self.filters]
        # print(f"🔍 [DEBUG] real filter keys          = {real_keys}")
        # print(f"🔍 [DEBUG] provided real filter keys = {provided}")
        # for k in provided:
        #     print(f"🔍 [DEBUG] filters['{k}'] length    = {len(self.filters.get(k, []))}")

        # # if ANY of the provided real filters is an empty list → no data
        # if any(len(self.filters.get(k, [])) == 0 for k in provided):
        #     print("🔍 [DEBUG] At least one real filter is empty → returning no data")
        #     return {"labels": [], "datasets": [], "updated_filters": {}}

        # print("🔍 [DEBUG] No empty real filters → continuing") 

        df = self.df
        df = self.apply_filters(df)
        df, group_col = self.apply_period_filter(df)
        #active_filter_type = self.memory_store.get("active_time_filter_type")

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

        if not self.selected_period_is_valid(
            selected_period=self.selected_period,
            df=df,
            months=resolver.selected_months,
            quarters=resolver.selected_quarters,
            years=resolver.selected_years
        ):
            return {
                "labels": [],
                "datasets": [],
                "updated_filters": {}
            }

        selected_range = memory_store[self.dataset_id]["period_ranges"].get(self.selected_period)
        if selected_range:
            start = selected_range["start"]
            end = selected_range["end"]
            df_selected = df[(df["date"] >= start) & (df["date"] <= end)]
            df_other = df[~((df["date"] >= start) & (df["date"] <= end))]
            df_selected = df_selected[df_selected["month"].isin(months_to_keep)]
            df = pd.concat([df_selected, df_other], ignore_index=True)

        available_periods = memory_store[self.dataset_id]["filters"].get(group_col, [])
        if self.period_type in ["Monthly", "Quarterly"] and self.selected_period:
            all_periods = [p for p in available_periods if self.selected_period in p]
        elif self.period_type == "Annual":
            all_periods = sorted([
                p for p in available_periods if p.startswith("F") or p.startswith("YTD") or p.startswith("LTM")
            ])
        else:
            all_periods = available_periods

        pivot, periods = pivot_and_group(
            df,
            group_col=group_col,
            index_col="product",
            value_col="amount",
            all_periods=all_periods
        )

        datasets = [
            {"label": product, "data": [float(pivot.loc[product, p]) for p in periods]}
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
            else:
                filtered_periods = available_periods

            if period_type == "Annual":
                period_ranges = memory_store[self.dataset_id]["period_ranges"]

            pivot, periods = pivot_and_group(
                df,
                group_col=group_col,
                index_col="product",
                value_col="amount",
                all_periods=filtered_periods
            )

            datasets = [
                {"label": product, "data": [float(pivot.loc[product, p]) for p in periods]}
                for product in pivot.index
            ]

            return {"labels": periods, "datasets": datasets}

        except Exception as e:
            print(f"⚠️ Error in _build_additional_dataset({period_type}):", e)
            return {"labels": [], "datasets": []}


    def get_updated_filters(self, df: pd.DataFrame) -> dict:
        # start with any non-time filters from BaseChart
        updated = super().get_updated_filters(df)

        # build a “master” resolver to figure out months_to_keep
        master_resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type=self.period_type,
            selected_months=self.filters.get("dates", []),
            selected_quarters=self.filters.get("quarters", []),
            selected_years=self.filters.get("years", []),
            memory_store={"active_time_filter_type": self.active_time_filter_type}
        )
        months_to_keep = master_resolver.resolve_months()

        # ─────── Dates dropdown ───────
        # always show exactly those months in scope
        updated["dates"] = sorted(
            months_to_keep,
            key=lambda x: pd.to_datetime(x)
        )

        # ─────── Quarters dropdown ───────
        raw_quarters = memory_store[self.dataset_id]["filters"].get("fiscal_quarter", [])
        # force a Quarterly resolver so we filter by months_to_keep → quarters
        q_resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type="Quarterly",
            selected_months=self.filters.get("dates", []),
            selected_quarters=self.filters.get("quarters", []),
            selected_years=self.filters.get("years", []),
            memory_store={"active_time_filter_type": self.active_time_filter_type}
        )
        updated["quarters"] = q_resolver.resolve_label_periods(raw_quarters)

        # ─────── Years dropdown ───────
        # gather the raw labels (FY, YTD, LTM) from memory_store
        filters_meta = memory_store[self.dataset_id]["filters"]
        valid_fys = memory_store[self.dataset_id].get("valid_fiscal_years", [])
        raw_years = (
            [fy for fy in filters_meta.get("fiscal_year", []) if fy in valid_fys]
            + filters_meta.get("ytd", [])
            + filters_meta.get("ltm", [])
        )
        raw_years = list({str(y).strip() for y in raw_years if str(y).strip()})
        # force a Yearly resolver so we filter by months_to_keep → years/YTD/LTM
        y_resolver = PeriodResolver(
            df=df,
            selected_period=self.selected_period,
            period_type="Yearly",
            selected_months=self.filters.get("dates", []),
            selected_quarters=self.filters.get("quarters", []),
            selected_years=self.filters.get("years", []),
            memory_store={"active_time_filter_type": self.active_time_filter_type}
        )
        updated["years"] = sorted(raw_years)

        return updated
