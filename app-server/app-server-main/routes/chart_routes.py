from fastapi import APIRouter, Request
from services.chart_registry import CHART_REGISTRY
from services.chart_registry import find_chart
from fastapi import APIRouter, Request, HTTPException, Query
from services.chart_registry import find_chart

chart_router = APIRouter()

@chart_router.post("/chart-data")
async def chart_data(request: Request):
    body = await request.json()
    chart_name = body.get("chart_name", "").lower().replace(" ", "_")
    dataset_id = body.get("dataset_id")
    period_type = body.get("period_type")
    selected_period = body.get("selected_period")
    filters = body.get("filters", {})
    top_n = body.get("top_n")

    if not dataset_id or not chart_name:
        return {"error": "Missing chart_name or dataset_id"}, 400

    chart_meta = find_chart(chart_name)
    if not chart_meta:
        return {"error": f"Chart '{chart_name}' not implemented"}, 400

    try:
        chart_class = chart_meta["class"]
        supports_top_n = chart_meta.get("supports_top_n", False)

        # 🎯 Collect all unknown fields as kwargs
        known_keys = {"chart_name", "dataset_id", "period_type", "selected_period", "filters", "top_n"}
        kwargs = {k: v for k, v in body.items() if k not in known_keys}

        # Add top_n only if supported
        if supports_top_n and top_n is not None:
            kwargs["top_n"] = top_n

        # ✅ Pass all to the chart class
        chart = chart_class(
            dataset_id=dataset_id,
            period_type=period_type,
            selected_period=selected_period,
            filters=filters,
            **kwargs
        )
        return chart.get_chart_data()

    except Exception as e:
        print(f"❌ Error generating chart '{chart_name}':", e)
        return {"error": str(e)}, 500
    


@chart_router.post("/groupings")
async def get_groupings(request: Request):
    try:
        body = await request.json()
        chart_name = body.get("chart_name", "").lower().replace(" ", "_")
        grouping_type = body.get("grouping_type")
        dataset_id = body.get("dataset_id", "dataset_fs_account")

        if not chart_name or not grouping_type:
            raise HTTPException(status_code=400, detail="Missing chart_name or grouping_type")

        chart_meta = find_chart(chart_name)
        if not chart_meta:
            raise HTTPException(status_code=404, detail=f"Chart '{chart_name}' not found")

        chart_class = chart_meta["class"]
        chart = chart_class(
            dataset_id=dataset_id,
            period_type=None,
            selected_period=None,
            filters={}
        )

        return chart.get_groupings(grouping_type)

    except Exception as e:
        print("❌ Grouping API error:", e)
        raise HTTPException(status_code=500, detail="Failed to fetch groupings")