"""X/Twitter account monitor service package.

Public surface is re-exported here so existing callers of
``from app.services.x_monitor import ...`` keep working unchanged. See
``service.py`` for the aggregating facade, ``pipeline.py`` for the fetch
pipeline, ``accounts.py`` for tracked-account administration, and
``normalize.py``/``health.py`` for the shared parsing and source-health
helpers.
"""

from __future__ import annotations

# Re-exported so downstream modules (and tests) that reference these names via
# ``app.services.x_monitor.<name>`` keep resolving to the same objects.
from app.services.twitterapi_io_client import TwitterApiIoClient, TwitterApiIoError

from .accounts import XAccountManager
from .constants import PROVIDER_NAME, VALID_MARKETS, VALID_SENTIMENTS, VALID_TIERS
from .errors import (
    XAccountAlreadyExistsError,
    XAccountNotFoundError,
    XMonitorDisabledError,
    XMonitorError,
)
from .health import _record_fetch_failure, _record_fetch_success, _update_avg_latency
from .normalize import (
    _dedupe_hash,
    _ensure_enabled,
    _extract_author_handle,
    _extract_author_name,
    _extract_post_id,
    _extract_symbols,
    _infer_market,
    _normalize_account_row,
    _normalize_content,
    _normalize_datetime,
    _normalize_handle,
    _parse_datetime,
    _posted_hour_bucket,
    _tweet_summary_view,
    _utc_now,
)
from .pipeline import XFetchPipeline
from .service import XMonitorService
from .summaries import XAccountsExportSummary, XAccountsImportSummary, XRefreshSummary

__all__ = [
    "PROVIDER_NAME",
    "VALID_MARKETS",
    "VALID_SENTIMENTS",
    "VALID_TIERS",
    "TwitterApiIoClient",
    "TwitterApiIoError",
    "XAccountAlreadyExistsError",
    "XAccountManager",
    "XAccountNotFoundError",
    "XAccountsExportSummary",
    "XAccountsImportSummary",
    "XFetchPipeline",
    "XMonitorDisabledError",
    "XMonitorError",
    "XMonitorService",
    "XRefreshSummary",
]
