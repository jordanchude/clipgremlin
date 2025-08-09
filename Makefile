# ClipGremlin Makefile

.PHONY: help build run test lint clean deploy local-dev

# Default target
help:
	@echo "ClipGremlin - Available commands:"
	@echo ""
	@echo "  build       Build Docker image"
	@echo "  run         Run with docker-compose"
	@echo "  test        Run tests"
	@echo "  lint        Run linting"
	@echo "  clean       Clean up containers and images"
	@echo "  deploy      Deploy to AWS"
	@echo "  local-dev   Set up local development environment"
	@echo ""

# Build Docker image
build:
	@echo "🐳 Building ClipGremlin Docker image..."
	docker build -t clipgremlin:latest .

# Run web application
run:
	@echo "🌐 Starting ClipGremlin web application..."
	docker-compose up --build web db

# Run single bot instance
run-bot:
	@echo "🤖 Starting single ClipGremlin bot..."
	docker-compose --profile single-bot up --build bot

# Run everything (web + bot)
run-all:
	@echo "🚀 Starting full ClipGremlin stack..."
	docker-compose --profile single-bot up --build

# Run in background
run-bg:
	@echo "🚀 Starting ClipGremlin web in background..."
	docker-compose up --build -d web db

# Stop background services
stop:
	@echo "⏹️ Stopping ClipGremlin..."
	docker-compose down

# Run tests
test:
	@echo "🧪 Running tests..."
	python -m pytest tests/ -v --cov=. --cov-report=html

# Run linting
lint:
	@echo "🔍 Running linting..."
	flake8 . --max-line-length=120 --exclude=.git,__pycache__,venv
	mypy . --ignore-missing-imports
	bandit -r . -x tests/

# Format code
format:
	@echo "🎨 Formatting code..."
	black . --line-length=120
	isort . --profile=black

# Clean up Docker resources
clean:
	@echo "🧹 Cleaning up Docker resources..."
	docker-compose down --rmi all --volumes --remove-orphans
	docker system prune -f

# Deploy to AWS
deploy:
	@echo "☁️ Deploying to AWS..."
	./deploy.sh

# Set up local development environment
local-dev:
	@echo "🛠️ Setting up local development environment..."
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "📝 Created .env file from template"; \
		echo "⚠️ Please edit .env with your credentials"; \
	else \
		echo "✅ .env file already exists"; \
	fi
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "🎉 Local development environment ready!"

# Install development dependencies
dev-deps:
	@echo "📦 Installing development dependencies..."
	pip install pytest pytest-cov flake8 mypy black isort bandit

# Check logs
logs:
	@echo "📋 Showing ClipGremlin logs..."
	docker-compose logs -f clipgremlin

# Health check
health:
	@echo "🏥 Checking ClipGremlin health..."
	curl -s http://localhost:8080/health | python -m json.tool

# Show status
status:
	@echo "📊 Checking ClipGremlin status..."
	curl -s http://localhost:8080/status | python -m json.tool

# Show metrics
metrics:
	@echo "📈 Showing ClipGremlin metrics..."
	curl -s http://localhost:8080/metrics
