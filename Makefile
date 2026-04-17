.PHONY: install run docker-build docker-up docker-down clean db-init db-reset help

PYTHON := python3
VENV := venv
VENV_BIN := $(VENV)/bin

help:
	@echo "SecondHand Market - Available Commands"
	@echo "======================================"
	@echo "make install       - Install Python dependencies"
	@echo "make run           - Run development server locally (port 8000)"
	@echo "make run-port PORT=3000 - Run on specific port"
	@echo "make kill-port-8000 - Kill process using port 8000"
	@echo "make docker-build  - Build Docker images"
	@echo "make docker-up     - Start Docker containers"
	@echo "make docker-down   - Stop Docker containers"
	@echo "make clean         - Remove virtual environment and cache"
	@echo "make db-init       - Initialize database"
	@echo "make db-reset      - Reset database with seed data"
	@echo "make lint          - Run code linting"
	@echo "make test          - Run tests (when implemented)"
	@echo ""
	@echo "Need different port?"
	@echo "  make run-port PORT=3000"

# Python environment setup
install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt
	@echo "✓ Dependencies installed. Activate with: source $(VENV)/bin/activate"

run: install
	$(VENV_BIN)/python src/app.py

# Docker commands
docker-build:
	docker-compose build

docker-up:
	docker-compose up

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart: docker-down docker-up

# Database commands
db-init:
	$(VENV_BIN)/python -c "from src.app import create_app; app = create_app(); print('✓ Database initialized')"

db-reset:
	@rm -f instance/app.db
	@mkdir -p instance
	$(VENV_BIN)/python -c "from src.app import create_app; app = create_app(); print('✓ Database reset and ready')"

# Cleanup
clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	rm -rf .pytest_cache
	@echo "✓ Cleaned up"

# Development tools
lint:
	$(VENV_BIN)/flake8 src/ || true

test:
	@echo "Tests not yet implemented"

# Shortcuts
serve: run
start: docker-up
stop: docker-down

# Port management
run-port:
	@echo "Usage: make run-port PORT=3000"
	@echo "Example: make run-port PORT=3000"
	@PORT=$(PORT) $(VENV_BIN)/python src/app.py

kill-port-8000:
	@echo "Attempting to free port 8000..."
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "✓ Port 8000 already free"
