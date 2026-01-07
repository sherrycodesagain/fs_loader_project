# fangtooth-app-server (FastAPI Backend)

This is the **backend service** for the Excel Taskpane Add-in, built with **FastAPI**, **Pandas**, and **MongoDB**.  
It provides chart data aggregation, filtering, period resolution, and other core APIs for the frontend dashboard.

---

##  Tech Stack

- **FastAPI** — Lightweight async backend framework
- **Pandas** — Data wrangling and in-memory chart generation
- **MongoDB** — Source-of-truth for ledger data (via pymongo)
- **Uvicorn** — ASGI server

---

##  Setup Instructions

### 1. Clone the Repository

### 2. Create a Virtual Environment

```bash
python -m venv venv
# Activate:
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

##  Environment Variables

Create a `.env` file in the root (`app-server/`) directory:

```ini
MONGO_URI=mongodb+srv://your-user:your-password@cluster.mongodb.net
DB_NAME=sales_dashboard
COLLECTION_NAME=sales_ledger
CURRENT_DATE_INPUT=2023-12-31
DEFAULT_FISCAL_YEAR_END=2023-03-31
CURRENCY=CAD
DENOMINATION=$
```

---

##  Run the FastAPI Server

```bash
python -m uvicorn main:app --reload --port 8001
```

Server will run on `http://localhost:8001` by default.

---

## Project Structure

```bash
fangtooth-app-server/
├── main.py                      # FastAPI entrypoint
├── config.py                    # Loads and exposes .env settings
├── routes/                      # API route modules (charts, filters, periods)
├── services/
│   ├── charts/                  # Chart-specific logic (sales, AR, FS, etc.)
│   ├── loaders/                 # Dataset loaders (Excel → DataFrame)
│   └── chart_registry.py        # Central registry of chart classes
├── cache/                       # In-memory cache utils (used for dev)
├── utils/                       # General utilities (filters, dates, queries)
├── tests/                       # (Optional) Test files
├── .env                         # Secrets and runtime config (not committed)
├── .gitignore                   # Ignores venv, cache, data-sets, etc.
├── README.md
└── requirements.txt
```

---

---

##  Versioning

This repo follows [Semantic Versioning](https://semver.org/) going forward (e.g., `v1.0.0`, `v1.1.0`, `v2.0.0`).

---

##  API Endpoints

| Method | Endpoint              | Purpose                |
|--------|-----------------------|------------------------|
| POST   | `/api/charts/chart-data` | Fetch chart datasets   |
| POST   | `/api/filters`        | Get filter options     |
| GET    | `/api/periods/{dataset_id}` | Get valid time periods |

---


---

###  Required Local Folder: `data-sets/`

The `data-sets/` folder contains the source Excel files for loading financial and sales data. This folder is **not committed to the repository** for privacy reasons.

Please make sure to **manually place the following files inside a `data-sets/` folder at the root of the project**:

```
data-sets/
├── Sales Ledger.xlsx
├── TB11.xlsx
├── Chart of Accounts.xlsx
├── AR.xlsx
├── AP.xlsx
```

These files are referenced in `config.py` and are required for the data ingestion and processing scripts to function properly.
