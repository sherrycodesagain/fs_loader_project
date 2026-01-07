from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from io import BytesIO
import pandas as pd
from cache.memory_store import memory_store

export_router = APIRouter()

@export_router.post("/api/export/full")
async def export_full_dataset(request: Request):
    try:
        body = await request.json()
        filters = body.get("filters", {})
        dataset_id = body.get("dataset_id")

        if not dataset_id:
            print("❌ Missing dataset_id")
            return JSONResponse(status_code=400, content={"error": "Missing dataset_id"})

        if dataset_id not in memory_store:
            print(f"❌ Dataset not found in memory_store: {dataset_id}")
            return JSONResponse(status_code=404, content={"error": f"Dataset '{dataset_id}' not found."})

        df = memory_store[dataset_id]["enriched_df"].copy()
        print(f"📊 Original dataframe shape: {df.shape}")

        # Apply filters
        for key, values in filters.items():
            if key in df.columns and values:
                print(f"🧪 Applying filter on '{key}' with values: {values}")
                df = df[df[key].isin(values)]

        print(f"✅ Dataframe after filtering: {df.shape}")

        if df.empty:
            print("⚠️ Filtered dataframe is empty")
            return JSONResponse(status_code=204, content={"error": "No matching data found."})
        
        unwanted = [
            "month", "IsOriginalRow", "ytd", "ltm",
            "quarter_ytd", "quarter_ltm", "company",
            "denomination", "dataset_id", "period_label",
            "fiscal_year", "fiscal_quarter"
        ]
        df.drop(columns=[c for c in unwanted if c in df.columns], inplace=True)

        # ------------------ 3️⃣  PROPER-CASE HEADERS ------------------
        def to_proper_case(s: str) -> str:
            return s.replace("_", " ").title()

        df.columns = [to_proper_case(col) for col in df.columns]

        # ------------------ 4️⃣  DATE → YYYY-MM-DD ------------------
        if "Date" in df.columns:                      # ← header already proper-cased
            df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

        # ------------------ 5️⃣  AMOUNT FORMATTING ------------------
        amount_like_cols = df.select_dtypes(include=["float", "int"]).columns
        df[amount_like_cols] = df[amount_like_cols].applymap(lambda x: f"{x:,.2f}")

        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Full Data")
        output.seek(0)

        print("✅ Excel file generated in memory")

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=full_data_export.xlsx"}
        )

    except Exception as e:
        print(f"🔥 Exception occurred: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
