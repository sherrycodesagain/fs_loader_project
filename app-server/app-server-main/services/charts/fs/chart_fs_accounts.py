from fastapi import APIRouter, HTTPException, Request
from cache.memory_store import get_dataset
from config import CURRENCY, DENOMINATION, COMPANY_NAME
import pandas as pd

fs_chart_router = APIRouter()

GROUPING_FIELDS = [
    "top_level_grouping",
    "fs_grouping",
    "detailed_grouping",
    "account_name"
]

@fs_chart_router.post("/fs-chart-data")
async def get_fs_chart_data(request: Request):
    try:
        body = await request.json()
        dataset_id = body.get("dataset_id")
        accounts = set(body.get("accounts", []))
        period_type = body.get("period_type", "Monthly")
        selected_period = body.get("selected_period")
        filters = body.get("filters", {})

        if not dataset_id or not accounts:
            raise HTTPException(status_code=400, detail="Missing dataset_id or accounts")

        dataset = get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        df = dataset["enriched_df"].copy()

        # Identify matching rows for any grouping type
        filtered_frames = []
        for field in GROUPING_FIELDS:
            if field in df.columns:
                match_df = df[df[field].isin(accounts)].copy()
                if not match_df.empty:
                    match_df["group_key"] = match_df[field]
                    filtered_frames.append(match_df)

        if not filtered_frames:
            raise HTTPException(status_code=400, detail="No matching accounts found for any grouping")

        df = pd.concat(filtered_frames, ignore_index=True)

        # Apply optional filters
        for field, values in filters.items():
            if field in df.columns and values:
                df = df[df[field].isin(values)]

        # Determine which rows fall into the selected period
        if period_type == "Monthly":
            if selected_period.startswith("F"):
                df = df[df["fiscal_year"] == selected_period]
            elif selected_period.startswith("YTD"):
                df = df[df["ytd"] == selected_period]
            elif selected_period.startswith("LTM"):
                df = df[df["ltm"] == selected_period]
            period_col = "month"

        elif period_type == "Quarterly":
            if selected_period.startswith("YTD"):
                df = df[df["quarter_ytd"].str.endswith(selected_period)]
                period_col = "quarter_ytd"
            elif selected_period.startswith("LTM"):
                df = df[df["quarter_ltm"].str.endswith(selected_period)]
                period_col = "quarter_ltm"
            else:
                df = df[df["fiscal_quarter"].str.endswith(selected_period)]
                period_col = "fiscal_quarter"

        elif period_type == "Annual":

            df = df[
                df["period_label"].astype(str).str.startswith("F") |
                df["period_label"].astype(str).str.startswith("YTD") |
                df["period_label"].astype(str).str.startswith("LTM")
            ]
            period_col = "period_label"


        else:
            raise HTTPException(status_code=400, detail="Invalid period_type")

        # Split IS vs BS for correct aggregation
        is_df = df[df["type"] == "IS"]
        bs_df = df[df["type"] == "BS"]

        is_grouped = (
            is_df.groupby(["group_key", period_col])["ending_balance"]
            .sum()
            .reset_index()
        )

        bs_grouped = (
            bs_df.sort_values("date")
            .groupby(["group_key", period_col])
            .last().reset_index()[["group_key", period_col, "ending_balance"]]
        )

        final_df = pd.concat([is_grouped, bs_grouped], ignore_index=True)

        pivot_df = final_df.pivot(index="group_key", columns=period_col, values="ending_balance").fillna(0)
        pivot_df = pivot_df.loc[:, (pivot_df != 0).any(axis=0)]

        try:
            sorted_cols = sorted(pivot_df.columns.tolist(), key=lambda d: pd.to_datetime(d, errors="coerce"))
        except:
            sorted_cols = list(pivot_df.columns)

        pivot_df = pivot_df[sorted_cols]

        datasets = [
            {
                "label": label,
                "data": [round(pivot_df.loc[label, p], 2) for p in sorted_cols]
            }
            for label in pivot_df.index
        ]

        return {
            "labels": sorted_cols,
            "datasets": datasets,
            "currency": CURRENCY,
            "denomination": DENOMINATION,
            "company": COMPANY_NAME
        }

    except Exception as e:
        print("❌ FS Chart API error:", e)
        raise HTTPException(status_code=500, detail="Failed to generate FS chart data")
    

@fs_chart_router.post("/fs-groupings")
def get_fs_groupings(grouping_type: str):
    try:
        dataset = get_dataset("dataset_fs_account")
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        df = dataset["enriched_df"]

        if grouping_type not in df.columns:
            raise HTTPException(status_code=400, detail="Invalid grouping_type")

        df = df[[grouping_type, "type"]].dropna().drop_duplicates()

        grouped = (
            df.groupby("type")[grouping_type]
            .apply(lambda x: sorted(x.dropna().unique()))
            .to_dict()
        )

        return {
            "grouping_type": grouping_type,
            "values": grouped
        }

    except Exception as e:
        print("❌ FS Grouping API error:", e)
        raise HTTPException(status_code=500, detail="Failed to fetch FS groupings")