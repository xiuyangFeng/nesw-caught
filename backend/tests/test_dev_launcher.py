from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEV_SCRIPT = ROOT_DIR / "scripts/dev.sh"


def test_dev_script_no_longer_manages_a_separate_market_worker_process() -> None:
    # 自选股行情 producer 默认随后端进程的 lifespan 一起启停（见
    # app/main.py），dev launcher 不应再单独拉起/探活/清理一个
    # market_quote_producer 子进程。
    script = DEV_SCRIPT.read_text(encoding="utf-8")

    assert "MARKET_WORKER_PID" not in script
    assert "python -m app.workers.market_quote_producer" not in script


def test_dev_script_cleans_conflicting_ports_and_waits_for_backend() -> None:
    script = DEV_SCRIPT.read_text(encoding="utf-8")

    assert "kill_listeners_for_port()" in script
    assert 'kill_listeners_for_port 8000' in script
    assert 'kill_listeners_for_port 5174' in script
    assert "terminate_process_tree()" in script
    assert "wait_for_http()" in script
    assert 'wait_for_http "http://127.0.0.1:8000/api/health"' in script
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
