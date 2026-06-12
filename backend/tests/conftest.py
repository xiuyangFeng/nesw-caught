import os
import pytest
from pathlib import Path

# Redirect database url to a dedicated test file before any app imports
test_db_path = Path(__file__).resolve().parents[1] / "data" / "app_test.db"
test_db_url = f"sqlite:///{test_db_path}"
os.environ["DATABASE_URL"] = test_db_url

from app.db.initializer import initialize_database


def clean_test_db() -> None:
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except OSError:
            pass


@pytest.fixture(scope="session", autouse=True)
def initialized_database() -> None:
    clean_test_db()
    initialize_database()
    yield
    clean_test_db()

