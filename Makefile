PYTHON := conda run -n news-caught python
PIP := conda run -n news-caught python -m pip
NPM := npm --prefix frontend

.PHONY: setup backend frontend dev test test-backend build-frontend

setup:
	$(PIP) install -r requirements.txt -e backend
	$(NPM) install

backend:
	conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000

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
