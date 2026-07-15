import os
from pathlib import Path

import pytest

# Redirect database url to a dedicated test file before any app imports.
# NEWS_CAUGHT_TEST_DB allows parallel test runs (e.g. multiple agents/worktrees)
# to use isolated database files without fighting over the same SQLite file.
_default_test_db = Path(__file__).resolve().parents[1] / "data" / "app_test.db"
test_db_path = Path(os.environ.get("NEWS_CAUGHT_TEST_DB", str(_default_test_db)))
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

from app.db.initializer import initialize_database  # noqa: E402 (after env setup)


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
    # Mirror the production lifespan shutdown: close the shared httpx clients so
    # pooled keep-alive connections don't surface as unclosed-socket
    # ResourceWarnings at interpreter exit.
    from app.services.http_pool import close_llm_client

    close_llm_client()
    clean_test_db()

