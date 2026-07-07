import threading
import time

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.llm_token_usage import LLMTokenUsage


class TokenUsageBuffer:
    """Batches token usage rows and bulk-inserts them into the database.

    Rows are flushed once ``flush_n`` entries accumulate or ``flush_secs``
    have elapsed since the last flush. Batch sizing comes from explicit
    constructor arguments, falling back to Settings (TOKEN_USAGE_FLUSH_N /
    TOKEN_USAGE_FLUSH_SECS); tests inject flush_n=1 for synchronous writes.
    """

    def __init__(self, flush_n: int | None = None, flush_secs: float | None = None):
        settings = get_settings()
        self._buf: list[dict] = []
        self._lock = threading.Lock()
        self._flush_n = flush_n if flush_n is not None else settings.token_usage_flush_n
        self._flush_secs = flush_secs if flush_secs is not None else settings.token_usage_flush_secs
        self._last = time.monotonic()

    @property
    def flush_interval_seconds(self) -> float:
        return self._flush_secs

    def add(self, **row) -> None:
        with self._lock:
            self._buf.append(row)
            if len(self._buf) >= self._flush_n or time.monotonic() - self._last > self._flush_secs:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buf:
            return
        rows = self._buf
        self._buf = []
        self._last = time.monotonic()

        try:
            with SessionLocal() as s:
                s.bulk_insert_mappings(LLMTokenUsage, rows)
                s.commit()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to batch flush token usage: %s", exc)


token_usage_buffer = TokenUsageBuffer()
