from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any
import pandas as pd
from cache.memory_store import memory_store
from utils.period_utils import safe_date

router = APIRouter()

class DrilldownRequest(BaseModel):
    chart_name: str
    dataset_id: str
    period_type: str
    label: str
    fiscal_year_end: str
    filters: Dict[str, Any] = {}

@router.post("/drilldown")
async def drilldown(request: Request):
    payload = await request.json()

    dataset_id = payload.get("dataset_id")
    label = payload.get("label")
    filters: Dict[str, Any] = payload.get("filters", {})

    if not dataset_id or dataset_id not in memory_store:
        raise HTTPException(status_code=400, detail=f"Dataset '{dataset_id}' not found")

    df = memory_store[dataset_id]["enriched_df"].copy()

    # Step 1: Apply static filters
    for key, values in filters.items():
        if values and isinstance(values, list) and key in df.columns:
            df[key] = df[key].astype(str).str.lower().str.strip()
            values = [str(v).lower().strip() for v in values]
            df = df[df[key].isin(values)]

    # # Step 2: Apply period filter
    period_ranges = memory_store[dataset_id].get("period_ranges", {})

    # if "period_label" in df.columns and label in df["period_label"].values:
    #     df = df[df["period_label"] == label]

    # elif "month" in df.columns and label in df["month"].values:
    #     df = df[df["month"] == label]

    # elif "fiscal_quarter" in df.columns and label in df["fiscal_quarter"].values:
    #     df = df[df["fiscal_quarter"] == label]
    matched = False

    # Check tag-based period columns
    for col in ["ytd", "ltm", "fiscal_year", "fiscal_quarter", "month"]:
        if col in df.columns and label in df[col].values:
            df = df[df[col] == label]
            matched = True
            print(f"✅ Matched label '{label}' in column '{col}'")
            break

    if not matched and label in period_ranges:
        # get the date bounds
        start = pd.to_datetime(period_ranges[label]["start"])
        end   = pd.to_datetime(period_ranges[label]["end"])
        months_to_keep = period_ranges[label].get("months", [])

        # DEBUG: log the full range and months list
        print(f"🔍 Period '{label}' → from {start.date()} to {end.date()}")
        print(f"🔍 Months defined for this period: {months_to_keep!r}")

        # DEBUG: what months exist in the raw dataframe?
        if "month" in df.columns:
            raw_months = sorted(df["month"].dropna().unique().tolist())
            print(f"📊 Raw months in df before filtering: {raw_months}")

        # apply the date filter
        before_rows = len(df)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        after_date_rows = len(df)
        print(f"⚖️ Rows before date‐filter: {before_rows}; after: {after_date_rows}")

        # if a months list is specified, filter further
        if months_to_keep:
            before_months_rows = len(df)
            df = df[df["month"].isin(months_to_keep)]
            after_months_rows = len(df)
            print(f"🏷️ Filtering to months {months_to_keep}: {before_months_rows} → {after_months_rows}")

    elif not matched:
        print(f"⚠️ No matching period found for label '{label}'; skipping date filtering")


    # Step 3: Apply dynamic drilldown filters
    known_keys = {"chart_name", "dataset_id", "period_type", "label", "fiscal_year_end", "filters"}
 
    for key, value in payload.items():
        if key not in known_keys and value:
            value = str(value).strip().lower()

            if key == "account":
                found = False
                for field in ["account_name", "fs_grouping", "top_level_grouping", "detailed_grouping"]:
                    if field in df.columns:
                        df[field] = df[field].astype(str).str.strip().str.lower()
                        exact = df[df[field] == value]
                        partial = df[df[field].str.contains(value, case=False, na=False)]
                        if not exact.empty or not partial.empty:
                            df = exact if not exact.empty else partial
                            found = True
                            break
                if not found:
                    print(f"❌ No match found for account '{value}'")
                    return []

            elif key in df.columns:
                df[key] = df[key].astype(str).str.strip().str.lower()
                exact = df[df[key] == value]
                partial = df[df[key].str.contains(value, case=False, na=False)]
                df = exact if not exact.empty else partial

    # Step 4: Debug (optional - log drill context)
    if "customer" in payload:
        print(f"🔍 Drilldown filter - customer: {payload['customer']}")
        print(f"👀 Customers in data: {df['customer'].unique().tolist()}")

    # Step 5: Return rows
    if df.empty:
        print(f"⚠️ No records found after filtering for: {payload}")
        return []
    
    unwanted = [
    "month", "IsOriginalRow", "ytd", "ltm",
    "quarter_ytd", "quarter_ltm", "company",
    "denomination", "dataset_id", "period_label", "fiscal_year", "fiscal_quarter"
    ]

    df = df.drop(columns=[c for c in unwanted if c in df.columns])

    def to_proper_case(s):
        return s.replace('_', ' ').title()

    df.columns = [to_proper_case(col) for col in df.columns]

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    
    amount_like_cols = df.select_dtypes(include=['float', 'int']).columns

    for col in amount_like_cols:
        df[col] = df[col].apply(lambda x: f"{x:,.2f}")

    return df.to_dict(orient="records")
