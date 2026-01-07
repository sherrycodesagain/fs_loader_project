import pandas as pd
from utils.chart_utils import pivot_and_group
from utils.filter_resolution import PeriodResolver
from cache.memory_store import memory_store


def is_selected_period_valid(df, selected_period, months, quarters, years):
    if selected_period in years:
        return True
    if months:
        if selected_period in df[df["month"].isin(months)]["fiscal_year"].unique():
            return True
    if quarters:
        if selected_period in df[df["fiscal_quarter"].isin(quarters)]["fiscal_year"].unique():
            return True
    return False


def filter_by_selected_range(df, dataset_id, selected_period, months_to_keep):
    selected_range = memory_store[dataset_id]["period_ranges"].get(selected_period)
    if selected_range:
        start, end = selected_range["start"], selected_range["end"]
        df_selected = df[(df["date"] >= start) & (df["date"] <= end)]
        df_selected = df_selected[df_selected["month"].isin(months_to_keep)]
        df_other = df[~((df["date"] >= start) & (df["date"] <= end))]
        return pd.concat([df_selected, df_other], ignore_index=True)
    return df


def resolve_available_periods(period_type, selected_period, group_col, dataset_id):
    available_periods = memory_store[dataset_id]["filters"].get(group_col, [])

    if period_type in ["Monthly", "Quarterly"] and selected_period:
        return [p for p in available_periods if selected_period in p]
    elif period_type == "Yearly":
        return sorted([p for p in available_periods if p.startswith("F") or p.startswith("YTD") or p.startswith("LTM")])
    return available_periods


def build_additional_dataset(chart_class, dataset_id, period_type, selected_period, filters):
    try:
        chart_instance = chart_class(
            dataset_id=dataset_id,
            period_type=period_type,
            selected_period=selected_period,
            filters=filters
        )

        df = chart_instance.df
        df = chart_instance.apply_filters(df)
        df, group_col = chart_instance.apply_period_filter(df)

        available_periods = memory_store[dataset_id]["filters"].get(group_col, [])

        resolver = PeriodResolver(
            df=df,
            period_type=period_type,
            selected_period=selected_period,
            selected_months=filters.get("dates", []),
            selected_quarters=filters.get("quarters", []),
            selected_years=filters.get("years", []),
            memory_store={"active_time_filter_type": getattr(chart_instance, "active_time_filter_type", None)}
        )

        months_to_keep = resolver.resolve_months()

        if period_type == "Annual":
            df_selected = df[df["fiscal_year"] == selected_period]
            df_selected = df_selected[df_selected["month"].isin(months_to_keep)]
            df_other = df[df["fiscal_year"] != selected_period]
            df = pd.concat([df_selected, df_other], ignore_index=True)
        else:
            df = df[df["month"].isin(months_to_keep)]

        filtered_periods = resolve_available_periods(period_type, selected_period, group_col, dataset_id)

        pivot, periods = pivot_and_group(
            df,
            group_col=group_col,
            index_col="product",
            value_col="amount" if "amount" in df.columns else "quantity",
            all_periods=filtered_periods
        )

        datasets = [
            {"label": product, "data": [float(pivot.loc[product, p]) for p in periods]}
            for product in pivot.index
        ]

        return {"labels": periods, "datasets": datasets}

    except Exception as e:
        print(f"⚠️ Error in build_additional_dataset({period_type}):", e)
        return {"labels": [], "datasets": []}
