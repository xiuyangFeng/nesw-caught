#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""
PIPELINE_PID=""

# 后台重活 worker（BackgroundQueueWorker / TakeawayWorker / X 健康探针）的进程归属。
#   NEWS_CAUGHT_SPLIT_PIPELINE=0（默认）：单机单进程，全部随 uvicorn lifespan 启停。
#   NEWS_CAUGHT_SPLIT_PIPELINE=1        ：多进程，重活跑在独立的
#                                         `python -m app.workers.pipeline_worker_main`。
# 多进程模式下必须把 PIPELINE_WORKERS_ENABLED=false 同时传给两个进程：租约是进程内
# 内存，两个进程同时跑 queue worker 会重复爬正文 + 重复调 LLM（独立入口会直接拒绝启动）。
SPLIT_PIPELINE="${NEWS_CAUGHT_SPLIT_PIPELINE:-0}"

require_command() {
  local command_name="$1"

  if command -v "${command_name}" >/dev/null 2>&1; then
    return
  fi

  echo "[news-caught] required command not found: ${command_name}" >&2
  exit 127
}

terminate_process_tree() {
  local pid="$1"
  local children

  if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
    return
  fi

  children="$(pgrep -P "${pid}" 2>/dev/null || true)"
  for child in ${children}; do
    terminate_process_tree "${child}"
  done

  kill "${pid}" 2>/dev/null || true
  sleep 0.2
  if kill -0 "${pid}" 2>/dev/null; then
    kill -9 "${pid}" 2>/dev/null || true
  fi
}

kill_listeners_for_port() {
  local port="$1"
  local pids

  pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    return
  fi

  echo "[news-caught] stopping existing listeners on port ${port}: ${pids}"
  kill ${pids} 2>/dev/null || true
  sleep 1

  pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    echo "[news-caught] force stopping listeners on port ${port}: ${pids}"
    kill -9 ${pids} 2>/dev/null || true
  fi
}

wait_for_process_start() {
  local pid="$1"
  local name="$2"
  local child_exit_code=0

  for _ in {1..10}; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      echo "[news-caught] ${name} exited during startup" >&2
      wait "${pid}" || child_exit_code=$?
      return "${child_exit_code}"
    fi
    sleep 0.2
  done
}

wait_for_http() {
  local url="$1"
  local retries="${2:-150}"
  local delay="${3:-0.2}"
  local attempt=1

  while [[ "${attempt}" -le "${retries}" ]]; do
    if curl --silent --fail "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${delay}"
    attempt=$((attempt + 1))
  done

  echo "[news-caught] timed out waiting for ${url}" >&2
  return 1
}

cleanup() {
  local exit_code=$?

  terminate_process_tree "${BACKEND_PID}"
  terminate_process_tree "${PIPELINE_PID}"
  terminate_process_tree "${FRONTEND_PID}"

  wait 2>/dev/null || true
  exit "${exit_code}"
}

trap cleanup INT TERM EXIT

cd "${ROOT_DIR}"

require_command lsof
require_command pgrep
require_command curl

kill_listeners_for_port 8000
kill_listeners_for_port 5174

echo "[news-caught] starting backend on http://127.0.0.1:8000"
# 自选股行情 producer 默认随后端 lifespan 一起启停（MARKET_QUOTE_PRODUCER_ENABLED=true），
# 不再需要单独拉起 app.workers.market_quote_producer 进程。
if [[ "${SPLIT_PIPELINE}" == "1" ]]; then
  echo "[news-caught] pipeline workers mode: OUT-OF-PROCESS"
  export PIPELINE_WORKERS_ENABLED=false
else
  echo "[news-caught] pipeline workers mode: IN-PROCESS (set NEWS_CAUGHT_SPLIT_PIPELINE=1 to split)"
fi
conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
wait_for_process_start "${BACKEND_PID}" "backend"
wait_for_http "http://127.0.0.1:8000/api/health" 400 0.2

if [[ "${SPLIT_PIPELINE}" == "1" ]]; then
  echo "[news-caught] starting standalone pipeline worker process"
  # 刻意在 ROOT_DIR 下运行并用 PYTHONPATH 指向 backend（而不是 cd backend）：
  # Settings 的 env_file=".env" 是相对当前工作目录解析的，两个进程必须站在同一个
  # 目录，否则 worker 进程会读不到 .env，出现「web 有配置、worker 没有」的诡异分裂。
  # --reload 只对 web 进程有意义；worker 进程改代码后需要重启本脚本。
  PYTHONPATH="${ROOT_DIR}/backend" conda run -n news-caught python -m app.workers.pipeline_worker_main &
  PIPELINE_PID=$!
  wait_for_process_start "${PIPELINE_PID}" "pipeline worker"
fi

echo "[news-caught] starting frontend on http://127.0.0.1:5174"
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174 &
FRONTEND_PID=$!
wait_for_process_start "${FRONTEND_PID}" "frontend"

while true; do
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    wait "${BACKEND_PID}"
    exit $?
  fi

  if ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    wait "${FRONTEND_PID}"
    exit $?
  fi

  if [[ -n "${PIPELINE_PID}" ]] && ! kill -0 "${PIPELINE_PID}" 2>/dev/null; then
    wait "${PIPELINE_PID}"
    exit $?
  fi

  sleep 1
done
