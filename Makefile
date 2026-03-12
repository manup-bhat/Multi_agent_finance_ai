# India Multi-Agent Financial Prediction Engine
# Run make <target> from WSL2 Ubuntu terminal

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help setup install docker-up docker-down validate-phase0 clean

help:
	@echo "India Multi-Agent Financial Engine — Build Commands"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  make setup           Create venv + install all deps"
	@echo "  make install         Install/update Python packages"
	@echo "  make docker-up       Start all 5 Docker services"
	@echo "  make docker-down     Stop all Docker services"
	@echo "  make docker-logs     Tail logs from all services"
	@echo "  make validate-phase0 Run Phase 0 validation gate"
	@echo "  make test            Run all tests"
	@echo "  make clean           Remove venv + caches"
	@echo "  make shell           Activate venv in current shell"

# ── Setup ─────────────────────────────────────────────────────────────────────
setup:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(MAKE) install
	@echo "✅ Setup complete. Run: source $(VENV)/bin/activate"

install:
	$(PIP) install -r requirements.txt
	@echo "✅ All packages installed."

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up:
	docker compose up -d
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 10
	docker compose ps
	@echo ""
	@echo "  🐘 PostgreSQL:  localhost:5432"
	@echo "  📦 Qdrant:      http://localhost:6333"
	@echo "  🔍 Phoenix:     http://localhost:6006"
	@echo "  📊 MLflow:      http://localhost:5000"
	@echo "  🚀 App:         http://localhost:8000"

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-status:
	docker compose ps

# ── Validation ────────────────────────────────────────────────────────────────
validate-phase0:
	$(PYTHON) scripts/validate_phase0.py

# ── Development ───────────────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest tests/ -v

run-api:
	$(PYTHON) -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	$(PYTHON) -m streamlit run ui/app.py

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleaned."

shell:
	@echo "Run: source $(VENV)/bin/activate"