from dotenv import load_dotenv
import os
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
CURRENT_DATE_INPUT = os.getenv("CURRENT_DATE_INPUT")
DEFAULT_FISCAL_YEAR_END = os.getenv("DEFAULT_FISCAL_YEAR_END")
COMPANY_NAME = os.getenv("COMPANY_NAME")
CURRENCY = os.getenv("CURRENCY")
DENOMINATION = os.getenv("DENOMINATION")

EXCEL_PATH = os.path.abspath("data-sets/Sales Ledger.xlsx")
DATASET_ID = "dataset_sales_ledger"

TB_PATH = os.path.abspath("data-sets/TB11.xlsx")
COA_PATH = os.path.abspath("data-sets/Chart of Accounts.xlsx")
FS_DATASET_ID = "dataset_fs_account"

AR_PATH = os.path.abspath("data-sets/AR.xlsx")
AP_PATH = os.path.abspath("data-sets/AP.xlsx")
AR_DATASET_ID = "dataset_ar_account"
AP_DATASET_ID = "dataset_ap_account"

CATEGORY_DEFAULT_FILTERS = {
    "financials": ["dates", "quarters", "years"],
    "sales": ["customer", "currency", "location", "product", "dates", "quarters", "years"],
    "accounts_receivable": ["customer", "currency", "aging_group"],
    "accounts_payable": ["Vendor", "Currency", "Aging Group"]
}

CATEGORY_PERIOD_FILTERS = {
    "Annual": ["fiscal_year", "ytd", "ltm"],
    "Quarterly": ["fiscal_quarter", "quarter_ytd", "quarter_ltm"],
    "Monthly": ["month"]
}

mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[DB_NAME]
saved_graphs_collection = mongo_db[COLLECTION_NAME]