from __future__ import annotations

from datetime import datetime


def _update_avg_latency(health, latency_ms: float) -> None:
    """Fold one fetch latency into the running weighted average.

    Assumes health.total_fetches has already been incremented for this fetch.
    """
    if health.avg_latency_ms is None:
        health.avg_latency_ms = latency_ms
    else:
        health.avg_latency_ms = ((health.avg_latency_ms * (health.total_fetches - 1)) + latency_ms) / health.total_fetches


def _record_fetch_success(health, *, finished_at: datetime, latency_ms: float) -> None:
    health.total_fetches += 1
    health.last_success_at = finished_at
    health.consecutive_failures = 0
    health.last_error = None
    _update_avg_latency(health, latency_ms)


def _record_fetch_failure(health, *, finished_at: datetime, latency_ms: float, error: str) -> None:
    health.total_fetches += 1
    health.total_failures += 1
    health.consecutive_failures += 1
    health.last_failure_at = finished_at
    health.last_error = error
    _update_avg_latency(health, latency_ms)
