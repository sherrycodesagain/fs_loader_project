from cache.memory_store import memory_store
from utils.query_utils import apply_chart_filters, apply_period_filter
import pandas as pd
from services.chart_registry import find_chart
from services.filter_resolver import FilterResolver

def get_filtered_df(dataset_id: str, filters: dict, period_type: str, selected_period: str, chart_name: str) -> pd.DataFrame:
    data = memory_store.get(dataset_id)
    if not data:
        raise ValueError(f"No dataset found for dataset_id: {dataset_id}")

    df = data["enriched_df"].copy()

    # from services.chart_registry import find_chart
    # from services.filter_resolver import FilterResolver

    chart_meta = find_chart(chart_name)
    allowed = FilterResolver(chart_meta).resolve() 

    filters_mapped = {}
    for key in allowed:
        values = filters.get(f"{key}s") 
        if values:
            filters_mapped[key] = values

    df = apply_chart_filters(df, filters_mapped)
    df = apply_period_filter(df, period_type, selected_period)
    return df

def get_combined_filter_options(df: pd.DataFrame, period_type: str, selected_period: str, chart_name: str, dataset_id: str, filters=None) -> dict:
    chart_meta = find_chart(chart_name)

    if not chart_meta:
        raise ValueError(f"Chart {chart_name} not found")
    
    filters = filters or {}
    
    allowed = FilterResolver(chart_meta).resolve()

    filters_mapped = {}
    for key in allowed:
        if key in ["dates", "quarters", "years"]:
            continue  # Skip time filters
        values = filters.get(key)
        if values:
            filters_mapped[key] = values

    df = apply_chart_filters(df, filters_mapped)
    df_period = _period_filter(df, period_type, selected_period)

    def uniq(source_df, col):
        return sorted(source_df[col].dropna().unique().tolist()) if col in source_df.columns else []

    response = {}

    for key in allowed:
        if key == "dates":
            response["dates"] = sorted(df_period["month"].dropna().unique().tolist())
        elif key == "quarters":
            if selected_period.startswith("YTD"):
                quarters = df["quarter_ytd"].dropna().unique().tolist()
                response["quarters"] = sorted([q for q in quarters if str(q).strip()])
            elif selected_period.startswith("LTM"):
                quarters = df["quarter_ltm"].dropna().unique().tolist()
                response["quarters"] = sorted([q for q in quarters if str(q).strip()])
            elif selected_period.startswith("F"):
                fiscal_quarters = df[df["fiscal_year"] == selected_period]["fiscal_quarter"].dropna().unique().tolist()
                response["quarters"] = sorted([q for q in fiscal_quarters if str(q).strip()])


        elif key == "years":
            valid_fys = memory_store.get(dataset_id, {}).get("valid_fiscal_years", [])
            ytds = [y for y in df["ytd"].dropna().unique().tolist() if y.strip()]
            ltms = [l for l in df["ltm"].dropna().unique().tolist() if l.strip()]
            combined = set(valid_fys + ytds + ltms)
            response["years"] = sorted(combined)

        else:
            if key in df_period.columns:
                response[key] = sorted(df_period[key].dropna().unique().tolist())


    response["allowed_filters"] = allowed
    return response


def _period_filter(df, period_type, selected_period):
    if not selected_period:
        return df

    if period_type == "Monthly":
        return df[
            df["ytd"].eq(selected_period) |
            df["ltm"].eq(selected_period) |
            df["fiscal_year"].eq(selected_period)
        ]

    if period_type == "Quarterly":
        return df[
            df["quarter_ytd"].str.contains(selected_period, na=False) |
            df["quarter_ltm"].str.contains(selected_period, na=False) |
            df["fiscal_quarter"].str.contains(selected_period, na=False)
        ]
    if period_type == "Annual":
        return df[
            (df["fiscal_year"] == selected_period) |
            (df["ytd"] == selected_period) |
            (df["ltm"] == selected_period)
        ]

    return df[
        (df["fiscal_year"] == selected_period) |
        (df["ytd"] == selected_period) |
        (df["ltm"] == selected_period)
    ]