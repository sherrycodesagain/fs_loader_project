from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from cache.memory_store import get_dataset

period_router = APIRouter()

def enrich_period_ranges(dataset):
    period_ranges = dataset["period_ranges"]
    month_to_quarter = dataset.get("month_to_quarter", {})
    enriched = {}

    for period, meta in period_ranges.items():
        quarters = set()
        for month in meta.get("months", []):
            q = month_to_quarter.get(month)
            if q:
                quarters.add(q)
        enriched[period] = {**meta, "quarters": sorted(quarters)}

    return enriched


@period_router.get("/{dataset_id}")
def get_periods(dataset_id: str, chart_name: Optional[str] = Query(default=None)):
    dataset = get_dataset(dataset_id)
 
    if not dataset:
        print(f"❌ Dataset not found for ID: {dataset_id}") 
        raise HTTPException(status_code=404, detail="Dataset not found")

    response = {
        "available_periods": sorted(dataset["period_ranges"].keys()),
        "period_ranges": enrich_period_ranges(dataset)
    }

    if chart_name and "waterfall" in chart_name.lower():
        response["waterfall_periods"] = dataset.get("waterfall_periods", {})

    return response