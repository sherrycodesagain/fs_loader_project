import pandas as pd
import re

def _safe_period_sort(periods: list[str]) -> list[str]:
    """
    Tries to sort periods like:
    - Months: 'April 2023'
    - Quarters: 'Q1 F2022'
    - Fiscal Years: 'F2023'
    - YTD/LTM: 'YTD F2023', 'LTM Dec 2023'
    """

    def parse_key(p):
        try:
            # Try parsing as month
            return pd.to_datetime(p, format="%B %Y")
        except:
            pass

        q_match = re.match(r"Q([1-4]) F(\d{4})", str(p))
        if q_match:
            q = int(q_match.group(1))
            year = int(q_match.group(2))
            return pd.Timestamp(year=year, month=(q - 1) * 3 + 1, day=1)

        fy_match = re.match(r"F(\d{4})", str(p))
        if fy_match:
            return pd.Timestamp(year=int(fy_match.group(1)), month=1, day=1)

        ytd_match = re.match(r"YTD F(\d{4})", str(p))
        if ytd_match:
            return pd.Timestamp(year=int(ytd_match.group(1)), month=1, day=1)

        ltm_match = re.match(r"LTM (\w+ \d{4})", str(p))
        if ltm_match:
            try:
                return pd.to_datetime(ltm_match.group(1))
            except:
                pass

        return pd.Timestamp.max  # fallback

    return sorted(periods, key=parse_key)


def pivot_and_group(
    df: pd.DataFrame,
    group_col: str,
    index_col: str,
    value_col: str,
    agg_func: str = "sum",
    sort_periods: bool = True,
    drop_zero_columns: bool = True,  
    all_periods: list[str] = None,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Groups and pivots the DataFrame with full label preservation and optional smart sorting.
    """

    grouped = df.groupby([group_col, index_col])[value_col].agg(agg_func).reset_index()
    pivot = grouped.pivot(index=index_col, columns=group_col, values=value_col).fillna(0)

    # Ensure all columns are present (even if fully zero)
    if all_periods:
        pivot = pivot.reindex(columns=all_periods, fill_value=0)

    # Optional zero-column drop (e.g. for Top-N chart optimization)
    if drop_zero_columns:
        pivot = pivot.loc[:, (pivot != 0).any(axis=0)]

    periods = pivot.columns.tolist()

    if sort_periods:
        periods = _safe_period_sort(periods)
        pivot = pivot.reindex(columns=periods)

    return pivot, periods

def normalize_chart_key(name: str) -> str:
    if not name:
        return ""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)  
    return name.strip("_")


