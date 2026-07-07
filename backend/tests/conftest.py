import os
import pytest
from pathlib import Path

# Redirect database url to a dedicated test file before any app imports
test_db_path = Path(__file__).resolve().parents[1] / "data" / "app_test.db"
test_db_url = f"sqlite:///{test_db_path}"
os.environ["DATABASE_URL"] = test_db_url

# Test-suite defaults injected explicitly through Settings (must be set before
# any app imports so import-time singletons pick them up):
# - disable App Token auth globally; auth tests re-enable it by monkeypatching
#   app.core.auth.get_settings with Settings(verify_app_token=True)
# - disable route-level TTL caches; dedicated cache tests re-enable per instance
# - flush token usage rows synchronously (batch size 1)
os.environ["VERIFY_APP_TOKEN"] = "false"
os.environ["ROUTE_CACHE_ENABLED"] = "false"
os.environ["TOKEN_USAGE_FLUSH_N"] = "1"

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

