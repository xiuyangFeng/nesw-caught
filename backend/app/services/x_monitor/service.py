from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.x_account_repository import XAccountRepository
from app.repositories.x_post_repository import XPostRepository
from app.repositories.x_signal_repository import XSignalRepository
from app.repositories.x_source_health_repository import XSourceHealthRepository
from app.schemas.x_monitor import (
    XPostSummaryView,
    XRadarMacroClusterView,
    XRadarResponse,
    XRadarSignalView,
)
from app.services.twitterapi_io_client import TwitterApiIoClient
from app.services.x_radar_signal_builder import XRadarSignalBuilder

from .accounts import XAccountManager
from .normalize import _ensure_enabled
from .pipeline import XFetchPipeline
from .summaries import XAccountsExportSummary, XAccountsImportSummary, XRefreshSummary


class XMonitorService:
    """Aggregating facade over account administration, the fetch pipeline, and read views.

    Keeps the constructor signature and public surface stable for routes,
    the health endpoint, and background callers.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.accounts = XAccountRepository(session)
        self.posts = XPostRepository(session)
        self.signals = XSignalRepository(session)
        self.health_repo = XSourceHealthRepository(session)
        self.provider = TwitterApiIoClient()
        self.signal_builder = XRadarSignalBuilder(
            self.signals,
            rules_file=getattr(self.settings, "x_radar_rules_file", None),
        )
        self.account_manager = XAccountManager(session, self.settings, self.accounts)
        self.pipeline = XFetchPipeline(
            session,
            self.settings,
            accounts=self.accounts,
            posts=self.posts,
            health_repo=self.health_repo,
            provider=self.provider,
            signal_builder=self.signal_builder,
        )

    def ensure_enabled(self) -> None:
        _ensure_enabled(self.settings)

    # -- account administration ------------------------------------------------

    def list_accounts(self) -> list:
        return self.account_manager.list_accounts()

    def sync_accounts_from_file(self) -> list:
        return self.account_manager.sync_accounts_from_file()

    def create_account(self, payload) -> object:
        return self.account_manager.create_account(payload)

    def update_account(self, handle: str, payload) -> object:
        return self.account_manager.update_account(handle, payload)

    def delete_account(self, handle: str) -> None:
        self.account_manager.delete_account(handle)

    def import_accounts_from_file(self) -> XAccountsImportSummary:
        return self.account_manager.import_accounts_from_file()

    def export_accounts_to_file(self) -> XAccountsExportSummary:
        return self.account_manager.export_accounts_to_file()

    # -- fetch pipeline ----------------------------------------------------------

    def refresh(self) -> XRefreshSummary:
        return self.pipeline.refresh()

    def search_posts(self, query: str, limit: int) -> list[XPostSummaryView]:
        return self.pipeline.search_posts(query, limit)

    def provider_health(self) -> tuple[bool, str]:
        return self.pipeline.provider_health()

    # -- read views ---------------------------------------------------------------

    def list_posts(
        self,
        *,
        account_handle: str | None = None,
        symbol: str | None = None,
        market: str | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> list[XPostSummaryView]:
        rows = self.posts.list_posts(
            account_handle=account_handle,
            symbol=symbol,
            market=market,
            query=query,
            limit=limit,
        )
        return [XPostSummaryView.from_post(post, account, symbols) for post, account, symbols in rows]

    def get_radar(self, limit: int = 50) -> XRadarResponse:
        return XRadarResponse(
            priority_signals=[
                XRadarSignalView.from_signal(signal)
                for signal in self.signals.list_priority_signals(limit=limit)
            ],
            macro_clusters=[
                XRadarMacroClusterView.model_validate(row)
                for row in self.signals.list_macro_clusters(limit=limit)
            ],
            evidence_stream=[
                XPostSummaryView.from_post(post, account, symbols)
                for post, account, symbols in self.signals.list_evidence_posts(limit=limit)
            ],
        )
