PYTHON := conda run -n news-caught python
PIP := conda run -n news-caught python -m pip
NPM := npm --prefix frontend

.PHONY: setup backend frontend dev dev-split test test-backend build-frontend ingest-news market-worker pipeline-worker bench bench-save check-openapi quant-backfill

setup:
	$(PIP) install -r requirements.txt -e backend
	$(NPM) install

# --no-access-log：访问日志改由 RequestLoggingMiddleware 输出（带 request_id、
# 遵循 LOG_FORMAT/文件轮转配置），uvicorn 自带的控制台访问行会重复，关掉。
backend:
	conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000 --no-access-log

frontend:
	$(NPM) run dev

dev:
	./scripts/dev.sh

test:
	$(MAKE) test-backend
	$(MAKE) build-frontend

test-backend:
	conda run -n news-caught pytest backend/tests

build-frontend:
	$(NPM) run build

ingest-news:
	PYTHONPATH=backend conda run -n news-caught python -m app.workers.news_fetcher

market-worker:
	PYTHONPATH=backend conda run -n news-caught python -m app.workers.market_quote_producer

# 多进程形态：把爬正文 + LLM 这类重活挪出 web 进程。
# 实测（后台爬取活跃期间，/api/news/runtime 连续采样 60s）：
#   进程内：p50 3.7ms / p95 528.6ms / max 735.2ms
#   独立进程：p50 1.4ms / p95 2.8ms / max 20.0ms
# 收益几乎全在尾延迟——也就是"偶发点击卡一下"的那种体感。
# 注意：必须同时给 web 进程设 PIPELINE_WORKERS_ENABLED=false，否则两个进程各跑
# 一套 worker，而 in-flight 租约是进程内内存、不跨进程，会重复爬取 + 双倍 LLM。
# 独立入口启动时会自检并拒绝这种误配置。
pipeline-worker:
	PYTHONPATH=backend PIPELINE_WORKERS_ENABLED=false conda run -n news-caught python -m app.workers.pipeline_worker_main

# 前后端 + 独立 pipeline worker 一起拉起（单进程默认形态见 `make dev`）。
dev-split:
	NEWS_CAUGHT_SPLIT_PIPELINE=1 ./scripts/dev.sh

# 读路径性能基准。需要先有一个在跑的后端（见 backend/scripts/README-bench.md）。
# 优先用 ab/hey/wrk 等原生客户端：Python 压测客户端会被自身 GIL 卡住，
# 把服务端的优化整个掩盖掉（这个坑本仓库踩过，脚本里已内置警告）。
bench:
	PYTHONPATH=backend $(PYTHON) backend/scripts/bench_readpath.py

# 存一份基准快照，之后用 --baseline 做回归对比。
bench-save:
	PYTHONPATH=backend $(PYTHON) backend/scripts/bench_readpath.py --json bench-baseline.json

check-openapi:
	$(PYTHON) scripts/export_openapi.py --check

quant-backfill:
	PYTHONPATH=backend conda run -n news-caught python -m app.services.quant.market_data.backfill_main
