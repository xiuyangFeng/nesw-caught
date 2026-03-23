#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""
MARKET_WORKER_PID=""

cleanup() {
  local exit_code=$?

  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi

  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi

  if [[ -n "${MARKET_WORKER_PID}" ]] && kill -0 "${MARKET_WORKER_PID}" 2>/dev/null; then
    kill "${MARKET_WORKER_PID}" 2>/dev/null || true
  fi

  wait 2>/dev/null || true
  exit "${exit_code}"
}

trap cleanup INT TERM EXIT

cd "${ROOT_DIR}"

echo "[news-caught] starting backend on http://127.0.0.1:8000"
conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "[news-caught] starting frontend on http://127.0.0.1:5174"
npm --prefix frontend run dev -- --host 0.0.0.0 --port 5174 &
FRONTEND_PID=$!

echo "[news-caught] starting market worker"
PYTHONPATH=backend conda run -n news-caught python -m app.workers.market_quote_producer &
MARKET_WORKER_PID=$!

while true; do
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    wait "${BACKEND_PID}" 2>/dev/null || true
    break
  fi

  if ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    wait "${FRONTEND_PID}" 2>/dev/null || true
    break
  fi

  if ! kill -0 "${MARKET_WORKER_PID}" 2>/dev/null; then
    wait "${MARKET_WORKER_PID}" 2>/dev/null || true
    break
  fi

  sleep 1
done
