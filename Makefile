# Claude PM Framework - Python Build System
# Replaces npm scripts with Python-native tooling

.PHONY: help install install-dev install-prod install-ai test lint format type-check
.PHONY: health-check health-monitor health-status health-reports health-alerts
.PHONY: clean clean-cache clean-build build package release docs serve-docs
.PHONY: pre-commit setup-dev setup-venv activate check-deps security-check

# Default target
help: ## Show this help message
	@echo "Claude PM Framework - Python Build System"
	@echo "===========================================" 
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Environment:"
	@echo "  Python: $$(python --version 2>/dev/null || echo 'Not found')"
	@echo "  Pip: $$(pip --version 2>/dev/null || echo 'Not found')"
	@echo "  Virtual Env: $$(echo $$VIRTUAL_ENV | sed 's|.*/||' || echo 'None')"

# Environment and dependency management
setup-venv: ## Create and setup Python virtual environment
	@echo "Setting up Python virtual environment..."
	python -m venv .venv
	@echo "Virtual environment created at .venv/"
	@echo "Activate with: source .venv/bin/activate"

activate: ## Show command to activate virtual environment  
	@echo "To activate the virtual environment, run:"
	@echo "  source .venv/bin/activate"

install: ## Install base dependencies
	@echo "Installing base dependencies..."
	pip install --upgrade pip setuptools wheel
	pip install -r requirements/base.txt

install-dev: ## Install development dependencies
	@echo "Installing development dependencies..."
	pip install --upgrade pip setuptools wheel
	pip install -r requirements/dev.txt
	pre-commit install

install-prod: ## Install production dependencies
	@echo "Installing production dependencies..."
	pip install --upgrade pip setuptools wheel  
	pip install -r requirements/production.txt

install-ai: ## Install AI/ML dependencies
	@echo "Installing AI/ML dependencies..."
	pip install --upgrade pip setuptools wheel
	pip install -r requirements/ai.txt

install-all: ## Install all dependencies (dev + prod + ai)
	@echo "Installing all dependencies..."
	pip install --upgrade pip setuptools wheel
	pip install -r requirements/dev.txt
	pip install -r requirements/production.txt
	pip install -r requirements/ai.txt
	pre-commit install

check-deps: ## Check for dependency issues
	@echo "Checking dependencies..."
	pip check
	@echo "Dependencies OK"

# Development and code quality
setup-dev: install-dev ## Setup complete development environment
	@echo "Setting up development environment..."
	pre-commit install --install-hooks
	@echo "Development environment ready!"

format: ## Format code with black and isort
	@echo "Formatting code..."
	black claude_pm/ tests/ scripts/
	isort claude_pm/ tests/ scripts/
	@echo "Code formatting complete"

lint: ## Run linting checks
	@echo "Running linting checks..."
	flake8 claude_pm/ tests/ scripts/
	@echo "Linting complete"

type-check: ## Run type checking with mypy
	@echo "Running type checks..."
	mypy claude_pm/
	@echo "Type checking complete"

pre-commit: ## Run all pre-commit hooks
	@echo "Running pre-commit hooks..."
	pre-commit run --all-files

check: format lint type-check ## Run all code quality checks
	@echo "All code quality checks passed!"

# Testing
test: ## Run tests with pytest
	@echo "Running tests..."
	pytest

test-unit: ## Run unit tests only
	@echo "Running unit tests..."
	pytest -m "unit"

test-integration: ## Run integration tests only
	@echo "Running integration tests..."
	pytest -m "integration"

test-cov: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	pytest --cov=claude_pm --cov-report=html --cov-report=term

test-mem0ai: ## Run mem0AI integration tests
	@echo "Running mem0AI integration tests..."
	pytest -m "mem0ai" -v

# Health monitoring commands (replaces npm scripts)
health-check: ## Run single health check
	@echo "Running health check..."
	python scripts/automated_health_monitor.py once

health-monitor: ## Start continuous health monitoring  
	@echo "Starting continuous health monitoring..."
	python scripts/automated_health_monitor.py monitor

health-status: ## Show monitor status and latest health summary
	@echo "Health monitor status:"
	python scripts/automated_health_monitor.py status

health-reports: ## List available health reports
	@echo "Available health reports:"
	python scripts/automated_health_monitor.py reports

health-alerts: ## Show recent health alerts
	@echo "Recent health alerts:"
	python scripts/automated_health_monitor.py alerts

health-verbose: ## Run verbose health check
	@echo "Running verbose health check..."
	python scripts/automated_health_monitor.py once --verbose

# Service management
service-start: ## Start Claude PM services
	@echo "Starting Claude PM services..."
	python -m claude_pm.scripts.service_manager start

service-stop: ## Stop Claude PM services
	@echo "Stopping Claude PM services..."
	python -m claude_pm.scripts.service_manager stop

service-restart: ## Restart Claude PM services
	@echo "Restarting Claude PM services..."
	python -m claude_pm.scripts.service_manager restart

service-status: ## Show service status
	@echo "Service status:"
	python -m claude_pm.scripts.service_manager status

# Build and packaging
clean: clean-cache clean-build ## Clean all build artifacts

clean-cache: ## Clean Python cache files
	@echo "Cleaning Python cache files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf coverage_html_report/

clean-build: ## Clean build artifacts
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/

build: clean ## Build package for distribution
	@echo "Building package..."
	python -m build

package: build ## Create distribution packages
	@echo "Package built successfully"
	@echo "Files in dist/:"
	@ls -la dist/

install-local: build ## Install package locally in development mode
	@echo "Installing package locally..."
	pip install -e .

# Documentation
docs: ## Build documentation
	@echo "Building documentation..."
	mkdocs build

docs-serve: ## Serve documentation locally
	@echo "Serving documentation at http://localhost:8000"
	mkdocs serve

docs-deploy: ## Deploy documentation (if configured)
	@echo "Deploying documentation..."
	mkdocs gh-deploy

# Security and validation
security-check: ## Run security vulnerability scan
	@echo "Running security checks..."
	pip-audit
	@echo "Security scan complete"

validate: ## Validate project configuration
	@echo "Validating project configuration..."
	python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"
	@echo "Configuration valid"

# Release management
version: ## Show current version
	@echo "Current version:"
	@python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"

release-patch: ## Create patch release
	@echo "Creating patch release..."
	python scripts/release.py patch

release-minor: ## Create minor release  
	@echo "Creating minor release..."
	python scripts/release.py minor

release-major: ## Create major release
	@echo "Creating major release..."
	python scripts/release.py major

# Utility targets
info: ## Show project information
	@echo "Claude PM Framework Information"
	@echo "==============================="
	@echo "Version: $$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || echo 'Unknown')"
	@echo "Python: $$(python --version)"
	@echo "Virtual Env: $$(echo $$VIRTUAL_ENV | sed 's|.*/||' || echo 'None')"
	@echo "Working Dir: $$(pwd)"
	@echo ""
	@echo "Package Info:"
	@python -c "import claude_pm; print(f'Claude PM: {claude_pm.__version__}')" 2>/dev/null || echo "Package not installed"

list-scripts: ## List available Python scripts
	@echo "Available Python scripts:"
	@find scripts/ -name "*.py" -type f | sort

# Development workflow shortcuts
dev: install-dev format lint test ## Complete development workflow
	@echo "Development workflow complete!"

ci: format lint type-check test ## CI/CD pipeline checks
	@echo "CI checks passed!"

quick-test: ## Quick test run (fastest tests only)
	@echo "Running quick tests..."
	pytest -x -q --tb=short

# Integration with existing Node.js scripts (backwards compatibility)
npm-health-check: health-check ## Backwards compatibility with npm run health-check

npm-monitor: health-monitor ## Backwards compatibility with npm run monitor:health

npm-status: health-status ## Backwards compatibility with npm run monitor:status

# Docker support (if needed)
docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t claude-pm-framework:latest .

docker-run: ## Run Docker container
	@echo "Running Docker container..."
	docker run -it --rm claude-pm-framework:latest

# Development database setup (if needed)
db-setup: ## Setup development database
	@echo "Setting up development database..."
	# Add database setup commands here

db-migrate: ## Run database migrations
	@echo "Running database migrations..."
	# Add migration commands here

# Environment file management
env-example: ## Create example environment file
	@echo "Creating .env.example..."
	@cat > .env.example << 'EOF'
# Claude PM Framework Environment Variables
# Copy to .env and customize for your environment

# Core settings
CLAUDE_PM_LOG_LEVEL=INFO
CLAUDE_PM_DEBUG=false
CLAUDE_PM_ENABLE_ALERTING=true

# mem0AI integration
CLAUDE_PM_MEM0AI_HOST=localhost
CLAUDE_PM_MEM0AI_PORT=8002
CLAUDE_PM_MEM0AI_TIMEOUT=30

# OpenAI API (for mem0AI)
OPENAI_API_KEY=your_openai_api_key_here

# Monitoring
CLAUDE_PM_HEALTH_CHECK_INTERVAL=30
CLAUDE_PM_ALERT_THRESHOLD=60

# Paths
CLAUDE_PM_BASE_PATH=/Users/$$USER/Projects
CLAUDE_PM_CLAUDE_PM_PATH=/Users/$$USER/Projects/Claude-PM
CLAUDE_PM_MANAGED_PATH=/Users/$$USER/Projects/managed
EOF
	@echo ".env.example created"

# Quick setup for new developers
quickstart: setup-venv ## Quick setup for new developers
	@echo ""
	@echo "Quick setup complete! Next steps:"
	@echo "1. Activate virtual environment: source .venv/bin/activate"
	@echo "2. Install dependencies: make install-dev"
	@echo "3. Copy environment file: cp .env.example .env"
	@echo "4. Edit .env with your settings"
	@echo "5. Run tests: make test"
	@echo "6. Start health monitoring: make health-check"

# Performance monitoring
profile: ## Run performance profiling
	@echo "Running performance profiling..."
	python -m cProfile -o profile.stats scripts/automated_health_monitor.py once
	@echo "Profile saved to profile.stats"

benchmark: ## Run benchmarks
	@echo "Running benchmarks..."
	python -m pytest benchmarks/ -v

# Maintenance tasks  
update-deps: ## Update all dependencies
	@echo "Updating dependencies..."
	pip install --upgrade pip setuptools wheel
	pip install --upgrade -r requirements/base.txt
	pip install --upgrade -r requirements/dev.txt

check-outdated: ## Check for outdated packages
	@echo "Checking for outdated packages..."
	pip list --outdated

# GitHub integration
create-pr: ## Helper to create pull request
	@echo "Creating pull request..."
	@echo "Make sure to:"
	@echo "1. Commit your changes"
	@echo "2. Push to your branch" 
	@echo "3. Run: gh pr create --title 'Your PR Title' --body 'PR Description'"

# Migration helpers
migrate-from-npm: ## Help migrate from npm to Python build system
	@echo "Migration from npm to Python build system:"
	@echo "=========================================="
	@echo ""
	@echo "Old npm command -> New make command:"
	@echo "npm run health-check -> make health-check"
	@echo "npm run monitor:health -> make health-monitor"
	@echo "npm run monitor:status -> make health-status"
	@echo "npm run monitor:reports -> make health-reports"
	@echo "npm run monitor:alerts -> make health-alerts"
	@echo "npm test -> make test"
	@echo "npm run lint -> make lint"
	@echo "npm run format -> make format"
	@echo "npm run build -> make build"
	@echo ""
	@echo "New Python-specific commands:"
	@echo "make setup-dev -> Complete development setup"
	@echo "make install-ai -> Install AI dependencies"
	@echo "make type-check -> Run type checking"
	@echo "make service-start -> Start services"