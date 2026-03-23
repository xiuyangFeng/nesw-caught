from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEV_SCRIPT = ROOT_DIR / "scripts/dev.sh"


def test_dev_script_manages_market_worker_process() -> None:
    script = DEV_SCRIPT.read_text(encoding="utf-8")

    assert 'MARKET_WORKER_PID=""' in script
    assert 'terminate_process_tree "${MARKET_WORKER_PID}"' in script
    assert 'if ! kill -0 "${MARKET_WORKER_PID}" 2>/dev/null; then' in script
    assert 'wait "${MARKET_WORKER_PID}"' in script
    assert "python -m app.workers.market_quote_producer" in script


def test_dev_script_cleans_conflicting_ports_and_waits_for_backend() -> None:
    script = DEV_SCRIPT.read_text(encoding="utf-8")

    assert "kill_listeners_for_port()" in script
    assert 'kill_listeners_for_port 8000' in script
    assert 'kill_listeners_for_port 5174' in script
    assert "terminate_process_tree()" in script
    assert "wait_for_http()" in script
    assert 'wait_for_http "http://127.0.0.1:8000/api/stream/status"' in script
    assert "wait_for_process_start()" in script
    assert 'wait_for_process_start "${BACKEND_PID}" "backend"' in script
    assert "require_command()" in script
    assert "require_command lsof" in script
    assert "require_command pgrep" in script
    assert "require_command curl" in script
    assert 'local child_exit_code' in script
    assert 'child_exit_code=$?' in script
    assert 'return "${child_exit_code}"' in script
    assert 'wait "${BACKEND_PID}"' in script
    assert 'wait "${BACKEND_PID}" 2>/dev/null || true' not in script
