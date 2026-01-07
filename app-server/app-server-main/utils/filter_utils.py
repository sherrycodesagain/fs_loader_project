import pandas as pd
from cache.memory_store import memory_store

def get_standard_updated_filters(df: pd.DataFrame, dataset_id: str, user_filters: dict) -> dict:
    updated = {}

    # Existing filters (dynamic)
    for column in user_filters:
        if column in df.columns:
            updated[column] = sorted(df[column].dropna().unique().tolist())

    # Standard time filters
    if "month" in df.columns:
        updated["dates"] = sorted(df["month"].dropna().unique().tolist())
    if "fiscal_quarter" in df.columns:
        updated["quarters"] = sorted(df["fiscal_quarter"].dropna().unique().tolist())

    filters_meta = memory_store[dataset_id].get("filters", {})
    valid_fys = memory_store[dataset_id].get("valid_fiscal_years", [])

    fiscal_years = [fy for fy in filters_meta.get("fiscal_year", []) if fy in valid_fys]
    ytd_labels = filters_meta.get("ytd", [])
    ltm_labels = filters_meta.get("ltm", [])

    all_year_labels = set(str(label).strip() for label in fiscal_years + ytd_labels + ltm_labels if label)
    updated["years"] = sorted(all_year_labels, key=lambda x: (x[:3], x))

    return updated
