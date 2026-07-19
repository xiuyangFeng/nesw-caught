PYTHON := conda run -n news-caught python
PIP := conda run -n news-caught python -m pip
NPM := npm --prefix frontend

.PHONY: setup backend frontend dev test test-backend build-frontend ingest-news market-worker check-openapi

setup:
	$(PIP) install -r requirements.txt -e backend
	$(NPM) install

backend:
	conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

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

check-openapi:
	$(PYTHON) scripts/export_openapi.py --check
