from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.chart_routes import chart_router
from routes.filter_routes import filter_router
from routes.drilldown_routes import router as drilldown_router
from routes.period_routes import period_router
from routes.saved_graphs_route import router as saved_graphs_router
from routes.export_data_routes import export_router
from services.loaders.dataframe_loader import DataFrameLoader
from services.loaders.fsaccount_loader import FSAccountLoader  
from config import EXCEL_PATH, DATASET_ID, TB_PATH, COA_PATH, FS_DATASET_ID  
from services.loaders.arap_loader import ARAPDataFrameLoader
from config import AR_PATH, AP_PATH, AR_DATASET_ID, AP_DATASET_ID

import services.charts

app = FastAPI(
    title="Financial Charting API",
    version="1.0.0",
    description="Handles Excel parsing, chart generation, and filter logic in memory."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    
)

# Register routers
app.include_router(chart_router, prefix="/api/charts")
app.include_router(filter_router, prefix="/api/filters")
app.include_router(period_router, prefix="/api/periods")
app.include_router(drilldown_router, prefix="/api")
app.include_router(saved_graphs_router)
app.include_router(export_router)

# On startup: load datasets into memory
@app.on_event("startup")
def load_dataset_on_start():
    print(" Bootstrapping datasets...")

    # Load base dataset
    try:
        loader = DataFrameLoader(excel_path=EXCEL_PATH, dataset_id=DATASET_ID)
        loader.load_and_store()
        print(f"✅ Base dataset loaded ({DATASET_ID})")
    except Exception as e:
        print(f"❌ Failed to load base dataset: {e}")

    #Load FS dataset
    try:
        fs_loader = FSAccountLoader(tb_path=TB_PATH, coa_path=COA_PATH, dataset_id=FS_DATASET_ID)
        fs_loader.load_and_store()
        print(f"✅ FS dataset loaded ({FS_DATASET_ID})")
    except Exception as e:
        print(f"❌ Failed to load FS dataset: {e}")
    
    try:
        ar_loader = ARAPDataFrameLoader(excel_path=AR_PATH, dataset_id=AR_DATASET_ID, data_type="AR")
        ar_loader.load_and_store()
        print(f"✅ AR dataset loaded ({AR_DATASET_ID})")
    except Exception as e:
        print(f"❌ Failed to load AR dataset: {e}")

    # Load AP dataset
    try:
        ap_loader = ARAPDataFrameLoader(excel_path=AP_PATH, dataset_id=AP_DATASET_ID, data_type="AP")
        ap_loader.load_and_store()
        print(f"✅ AP dataset loaded ({AP_DATASET_ID})")
    except Exception as e:
        print(f"❌ Failed to load AP dataset: {e}")
