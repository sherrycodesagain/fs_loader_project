from fastapi import APIRouter, Request
from services.filter_service import get_combined_filter_options
from cache.memory_store import memory_store 
from services.chart_registry import find_chart
from utils.chart_utils import normalize_chart_key
from utils.cache_utils import generate_cache_key, get_or_set_cache  
import json
from hashlib import sha256


filter_router = APIRouter()

@filter_router.post("/")
async def get_filter_options(request: Request):

    body = await request.json()
    dataset_id = body.get("dataset_id")
    period_type = body.get("period_type")
    selected_period = body.get("selected_period")
    raw_chart_name = body.get("chart_name")
    chart_type = body.get("chart_type", "").lower()
    
    chart_name = normalize_chart_key(raw_chart_name)
    print(f"🚀 Incoming filter request: chart={chart_name}, dataset={dataset_id}, period={selected_period}, type={period_type}")


    if not dataset_id or not chart_name:
        return {"error": "Missing dataset_id or chart_name"}
    
    chart_meta = find_chart(chart_name)
    supports_period_type = chart_meta.get("supports_period_type", False)
    supports_periods = chart_meta.get("supports_periods", False)

    is_ar_aging_bar_chart = (
        chart_name == "ar_by_aging_group" and
        chart_type in ["pie", "stackedbar"]
    )
    
    if supports_period_type and not selected_period and not is_ar_aging_bar_chart:
        return {"error": "Missing selected_period for chart that supports year filtering"}

    if supports_periods and not period_type:
        return {"error": "Missing period_type for chart that supports period aggregation"}

    try:
        data = memory_store.get(dataset_id)
        if not data:
            return {"error": f"Dataset not found for ID: {dataset_id}"}

        df = data["enriched_df"]

        filters = body.get("filters", {}) 
        filter_hash = sha256(json.dumps(filters or {}, sort_keys=True).encode()).hexdigest()
        cache_key = generate_cache_key("filters", dataset_id, chart_name, period_type, selected_period, filter_hash)

        return get_or_set_cache(dataset_id, cache_key, lambda: get_combined_filter_options(
            df, period_type, selected_period, chart_name, dataset_id, filters
        ))

    except Exception as e:
        return {"error": f"Failed to load filter options: {str(e)}"}

