from pathlib import Path


def test_dev_script_manages_market_worker_process() -> None:
    script = Path("/Users/xiuyang/Desktop/news-caught/scripts/dev.sh").read_text(encoding="utf-8")

    assert 'MARKET_WORKER_PID=""' in script
    assert 'if [[ -n "${MARKET_WORKER_PID}" ]] && kill -0 "${MARKET_WORKER_PID}" 2>/dev/null; then' in script
    assert 'kill "${MARKET_WORKER_PID}" 2>/dev/null || true' in script
    assert "python -m app.workers.market_quote_producer" in script
