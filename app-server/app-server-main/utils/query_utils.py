import hashlib
import pandas as pd
from cache.memory_store import (
    get_dataframe,
    get_chart_cache,
    set_chart_cache,
    memory_store
)


def hash_chart_request(chart_name, filters, period_type, selected_period):
    key_data = f"{chart_name}|{period_type}|{selected_period}|"
    key_data += "|".join([
        f"{k}:{','.join(sorted(v))}" for k, v in sorted(filters.items())
    ])
    return hashlib.md5(key_data.encode()).hexdigest()


def generate_chart(chart_name, dataset_id, filters, period_type, selected_period):
    cache_key = hash_chart_request(chart_name, filters, period_type, selected_period)
    cached_chart = get_chart_cache(dataset_id).get(cache_key)
    if cached_chart:
        print("✅ Using cached chart")
        return cached_chart

    df = get_dataframe(dataset_id)
    if df is None:
        raise ValueError("Dataset not found in memory")

    # Step 1: Apply filters
    for field, selected_values in filters.items():
        if selected_values:
            df = df[df[field].isin(selected_values)]

    # Step 2: Filter by selected period
    df = df[df['Period'] == selected_period]

    # Step 3: Dispatch chart logic based on chart name
    chart_func = chart_dispatcher.get(chart_name)
    if not chart_func:
        raise ValueError(f"Chart logic not implemented for: {chart_name}")

    chart_json = chart_func(df)
    set_chart_cache(dataset_id, cache_key, chart_json)
    return chart_json


# ---------------- Chart Logic Implementations ----------------

def chart_sales_by_product(df):
    summary = (
        df.groupby("Account Name")
        .agg({"Amount": "sum"})
        .sort_values("Amount", ascending=False)
        .reset_index()
    )

    return {
        "labels": summary["Account Name"].tolist(),
        "datasets": [
            {
                "label": "Sales",
                "data": summary["Amount"].tolist(),
                "backgroundColor": "#4CAF50",
            }
        ]
    }

# Add more chart implementations as needed

chart_dispatcher = {
    "Sales by product": chart_sales_by_product,
    # "Top Customers": chart_top_customers,
    # "Sales by Location": chart_sales_by_location,
    # ...
}

def apply_chart_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    for col, rule in filters.items():
        if col not in df.columns:
            continue
        if isinstance(rule, list):
            df = df[df[col].isin(rule)]
        elif isinstance(rule, dict):
            if "include" in rule:
                df = df[df[col].isin(rule["include"])]
            if "exclude" in rule:
                df = df[~df[col].isin(rule["exclude"])]
    return df

def apply_period_filter(df: pd.DataFrame, period_type: str, selected_period: str) -> pd.DataFrame:
    if period_type == "Monthly":
        return df[df["Month"] == selected_period]
    elif period_type == "Quarterly":
        if selected_period.startswith("YTD"):
            return df[df["Quarter_YTD"] == selected_period]
        elif selected_period.startswith("LTM"):
            return df[df["Quarter_LTM"] == selected_period]
        else:
            return df[df["Fiscal Quarter"] == selected_period]
    elif period_type == "Annual":
        return df[df["Fiscal Year"] == selected_period]
    return df
