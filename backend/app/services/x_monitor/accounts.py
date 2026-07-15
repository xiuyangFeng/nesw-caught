from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.repositories.x_account_repository import XAccountRepository

from .errors import XAccountAlreadyExistsError, XAccountNotFoundError, XMonitorError
from .normalize import _normalize_account_row, _normalize_handle
from .summaries import XAccountsExportSummary, XAccountsImportSummary


class XAccountManager:
    """Tracked-account administration: CRUD plus JSON file import/export/sync."""

    def __init__(self, session: Session, settings, accounts: XAccountRepository) -> None:
        self.session = session
        self.settings = settings
        self.accounts = accounts

    def list_accounts(self) -> list:
        return self.accounts.list_all()

    def _get_required(self, handle: str):
        instance = self.accounts.get_by_handle(handle)
        if instance is None:
            raise XAccountNotFoundError(f"x account not found: {handle}")
        return instance

    def create_account(self, payload) -> object:
        handle = _normalize_handle(payload.handle)
        if self.accounts.get_by_handle(handle) is not None:
            raise XAccountAlreadyExistsError(f"x account already exists: {handle}")
        account = self.accounts.create(
            {
                "handle": handle,
                "display_name": payload.display_name.strip(),
                "market_focus": payload.market_focus,
                "is_active": payload.is_active,
                "priority": payload.priority,
                "tier": payload.tier,
                "source": "manual",
                "notes": payload.notes,
            }
        )
        self.session.commit()
        return account

    def update_account(self, handle: str, payload) -> object:
        instance = self._get_required(handle)
        account = self.accounts.update(
            instance,
            {
                "display_name": payload.display_name,
                "market_focus": payload.market_focus,
                "is_active": payload.is_active,
                "priority": payload.priority,
                "tier": payload.tier,
                "notes": payload.notes,
            },
        )
        self.session.commit()
        return account

    def delete_account(self, handle: str) -> None:
        instance = self._get_required(handle)
        self.accounts.delete(instance)
        self.session.commit()

    def _read_account_entries(self, accounts_file: str) -> list[object]:
        with open(accounts_file, encoding="utf-8") as handle:
            payload = json.load(handle)
        raw_accounts = payload.get("accounts", [])
        if not isinstance(raw_accounts, list):
            raise XMonitorError("x monitor accounts file must contain an accounts array")
        return raw_accounts

    def sync_accounts_from_file(self) -> list:
        accounts_file = self.settings.x_monitor_accounts_file
        if not accounts_file:
            return self.accounts.list_all()

        normalized = [
            row
            for row in (_normalize_account_row(item) for item in self._read_account_entries(accounts_file))
            if row is not None
        ]
        return self.accounts.upsert_many(normalized)

    def import_accounts_from_file(self) -> XAccountsImportSummary:
        accounts_file = self.settings.x_monitor_accounts_file
        if not accounts_file:
            raise XMonitorError("x monitor accounts file is not configured")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for item in self._read_account_entries(accounts_file):
            payload_row = _normalize_account_row(item)
            if payload_row is None:
                skipped_count += 1
                continue
            existing = self.accounts.get_by_handle(str(payload_row["handle"]))
            if existing is None:
                self.accounts.create(payload_row)
                created_count += 1
            else:
                self.accounts.update(existing, payload_row)
                updated_count += 1

        self.session.commit()
        return XAccountsImportSummary(
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
        )

    def export_accounts_to_file(self) -> XAccountsExportSummary:
        accounts_file = self.settings.x_monitor_accounts_file
        if not accounts_file:
            raise XMonitorError("x monitor accounts file is not configured")

        payload = {
            "accounts": [
                {
                    "handle": account.handle,
                    "display_name": account.display_name,
                    "market_focus": account.market_focus,
                    "is_active": account.is_active,
                    "priority": account.priority,
                    "tier": account.tier,
                    "source": account.source,
                    "notes": account.notes,
                }
                for account in self.accounts.list_all()
            ]
        }
        with open(accounts_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return XAccountsExportSummary(exported_count=len(payload["accounts"]))
