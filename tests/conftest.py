import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import config
import database.models
from database.models import init_db


@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    """Point all database operations to an isolated temporary database for each test."""
    test_db_path = str(tmp_path / "test_database.sqlite")
    monkeypatch.setattr(config, "DB_PATH", test_db_path)
    monkeypatch.setattr(database.models, "DB_PATH", test_db_path)
    init_db()
    yield test_db_path
