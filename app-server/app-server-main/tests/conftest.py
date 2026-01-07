# tests/conftest.py
import pytest
from services.loaders.fsaccount_loader import FSAccountLoader
from config import FS_DATASET_ID
import os

@pytest.fixture(scope="session", autouse=True)
def load_fs_data():
    tb_path = os.path.join("tests", "TB11.xlsx")
    coa_path = os.path.join("tests", "Chart Of Accounts.xlsx")

    loader = FSAccountLoader(tb_path, coa_path, dataset_id=FS_DATASET_ID)
    loader.load_and_store()
