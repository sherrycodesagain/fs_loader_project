from fastapi import APIRouter, Request, HTTPException
from datetime import datetime
from config import saved_graphs_collection
from pymongo.errors import PyMongoError
import re

router = APIRouter()

def get_unique_name(base_name, existing_names):
    if base_name not in existing_names:
        return base_name
    count = 1
    while f"{base_name} ({count})" in existing_names:
        count += 1
    return f"{base_name} ({count})"

@router.post("/api/save-graph")
async def save_graph(request: Request):
    try:
        payload = await request.json()
        base_name = payload.get("name", "").strip()
        if not base_name:
            raise HTTPException(status_code=400, detail="Graph name is required")

        existing_names = saved_graphs_collection.find(
            {"name": {"$regex": f"^{re.escape(base_name)}( \(\d+\))?$", "$options": "i"}},
            {"name": 1}
        ).distinct("name")

        unique_name = get_unique_name(base_name, existing_names)

        graph_data = {
            "name": unique_name,
            "created_at": datetime.utcnow(),
            "chart_config": payload.get("chart_config", {}),
            "filters": payload.get("filters", {}),
            "notes": payload.get("notes", []),
            "custom_colors": payload.get("custom_colors", {}),
            "chart_data": payload.get("chart_data", {})
        }

        saved_graphs_collection.insert_one(graph_data)
        return {"message": "Graph saved successfully", "name": unique_name}
    except PyMongoError as e:
        print(f"❌ MongoDB error while saving: {e}")
        raise HTTPException(status_code=500, detail="Failed to save graph")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/api/load-saved-graphs")
def load_saved_graphs():
    try:
        graphs = list(saved_graphs_collection.find({}, {"_id": 0}))
        return graphs
    except Exception as e:
        print(f"❌ Error loading graphs: {e}")
        raise HTTPException(status_code=500, detail="Failed to load graphs")

@router.post("/api/delete-saved-graph")
async def delete_saved_graph(request: Request):
    try:
        payload = await request.json()
        name = payload.get("name", "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Graph name is required")

        result = saved_graphs_collection.delete_one({"name": name})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Graph not found")

        return {"message": "Graph deleted successfully"}
    except Exception as e:
        print(f"❌ Error deleting graph: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete graph")
