#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

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
conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
wait_for_process_start "${BACKEND_PID}" "backend"
wait_for_http "http://127.0.0.1:8000/api/health" 400 0.2

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

  sleep 1
done
