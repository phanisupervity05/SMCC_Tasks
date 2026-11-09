# Makefile
.PHONY: help up down logs-be logs-fe reset-db migrate-create migrate-up migrate-down migrate-history format lint test-be cloud-build cloud-push cloud-build-push cloud-deploy deploy deploy-setup deploy-build deploy-status deploy-backend deploy-frontend

# Configuration (override with environment variables)
GCP_PROJECT ?= fde-rnd
GCP_REGION ?= us-central1
ARTIFACT_REPO ?= template-deployment
KEYCLOAK_IMAGE ?= us-central1-docker.pkg.dev/$(GCP_PROJECT)/$(ARTIFACT_REPO)/keycloak
KEYCLOAK_VERSION ?= v2

help:
	@echo "╔════════════════════════════════════════════════════════════════════╗"
	@echo "║              AI COMMAND CENTER - MAKEFILE COMMANDS                 ║"
	@echo "╚════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Local Development Commands:"
	@echo "  up          : Start all services using docker-compose."
	@echo "  down        : Stop all services."
	@echo "  logs-be     : View real-time logs for the backend."
	@echo "  logs-fe     : View real-time logs for the frontend."
	@echo "  reset-db    : Clean and re-initialize the database with sample data."
	@echo "  format      : Automatically format all backend and frontend code."
	@echo "  lint        : Lint all backend and frontend code for issues."
	@echo "  test-be     : Run backend tests with pytest."
	@echo ""
	@echo "Database Migration Commands:"
	@echo "  migrate-create MSG='description' : Create a new migration with auto-generated changes."
	@echo "  migrate-up     : Apply all pending migrations to the database."
	@echo "  migrate-down   : Downgrade the database by one migration."
	@echo "  migrate-history: Show migration history."
	@echo ""
	@echo "Production Deployment Commands (Google Cloud Run):"
	@echo "  deploy         : Full deployment (setup + build + deploy) - first time"
	@echo "  deploy-setup   : Initial GCP setup (APIs, Cloud SQL, secrets)"
	@echo "  deploy-build   : Build and push Docker images"
	@echo "  deploy-backend : Rebuild and redeploy backend only"
	@echo "  deploy-frontend: Rebuild and redeploy frontend only"
	@echo "  deploy-status  : Show deployment status"
	@echo ""
	@echo "Keycloak Commands (shared instance):"
	@echo "  cloud-build   : Build Keycloak Docker image for Cloud Run."
	@echo "  cloud-push    : Push Keycloak image to Artifact Registry."

up:
	@echo "🚀 Starting all Supervity services..."
	docker-compose up --build -d

down:
	@echo "🛑 Stopping all Supervity services..."
	docker-compose down

logs-be:
	@echo "👀 Tailing backend logs..."
	docker-compose logs -f backend

logs-fe:
	@echo "👀 Tailing frontend logs..."
	docker-compose logs -f frontend

reset-db:
	@echo "🧹 Resetting the database..."
	docker-compose exec backend python scripts/reset_db.py
	@echo "🌱 Seeding database with initial data..."
	docker-compose exec backend python scripts/seed_db.py
	@echo "✅ Database reset complete!"

migrate-create:
	@if [ -z "$(MSG)" ]; then \
		echo "❌ Error: Please provide a message. Usage: make migrate-create MSG='your description'"; \
		exit 1; \
	fi
	@echo "🔄 Creating new migration: $(MSG)"
	docker-compose exec backend alembic revision --autogenerate -m "$(MSG)"
	@echo "✅ Migration created successfully!"

migrate-up:
	@echo "⬆️  Applying pending migrations..."
	docker-compose exec backend alembic upgrade head
	@echo "✅ All migrations applied!"

migrate-down:
	@echo "⬇️  Downgrading database by one migration..."
	docker-compose exec backend alembic downgrade -1
	@echo "✅ Database downgraded!"

migrate-history:
	@echo "📋 Migration history:"
	docker-compose exec backend alembic history --verbose 

format:
	@echo "🎨 Formatting backend Python code..."
	black .
	isort .
	@echo "🎨 Formatting frontend TypeScript/React code..."
	@npm --prefix frontend run format
	@echo "✅ Formatting complete!"

lint:
	@echo "🔍 Linting backend Python code..."
	flake8 .
	@echo "🔍 Linting frontend TypeScript/React code..."
	@npm --prefix frontend run lint
	@echo "✅ Linting complete!"

test-be:
	@echo "🧪 Running backend tests..."
	docker-compose exec backend pytest
	@echo "✅ Backend tests complete!"

# ============================================================
# Cloud Deployment Commands (Keycloak on Google Cloud Run)
# ============================================================

cloud-build:
	@echo "🔨 Building Keycloak image for Cloud Run (AMD64)..."
	docker buildx build --platform=linux/amd64 -f keycloak/Dockerfile.cloud -t $(KEYCLOAK_IMAGE):$(KEYCLOAK_VERSION) ./keycloak
	@echo "✅ Image built: $(KEYCLOAK_IMAGE):$(KEYCLOAK_VERSION)"

cloud-push:
	@echo "🚀 Pushing Keycloak image to Artifact Registry..."
	docker push $(KEYCLOAK_IMAGE):$(KEYCLOAK_VERSION)
	@echo "✅ Image pushed successfully!"

cloud-build-push:
	@echo "🔨 Building and pushing Keycloak image for Cloud Run..."
	docker buildx build --platform=linux/amd64 -f keycloak/Dockerfile.cloud -t $(KEYCLOAK_IMAGE):$(KEYCLOAK_VERSION) ./keycloak --push
	@echo "✅ Image built and pushed: $(KEYCLOAK_IMAGE):$(KEYCLOAK_VERSION)"

cloud-deploy:
	@echo "☁️  Deploying Keycloak to Cloud Run..."
	@echo "⚠️  Make sure you have:"
	@echo "    1. Created a Cloud SQL PostgreSQL instance"
	@echo "    2. Created a 'keycloak' database in the instance"
	@echo "    3. Set up the Cloud SQL connection"
	@echo ""
	@echo "Run this command manually with your settings:"
	@echo ""
	@echo "gcloud run deploy supervity-auth \\"
	@echo "  --image=$(KEYCLOAK_IMAGE):$(KEYCLOAK_VERSION) \\"
	@echo "  --platform=managed \\"
	@echo "  --region=$(GCP_REGION) \\"
	@echo "  --allow-unauthenticated \\"
	@echo "  --port=8080 \\"
	@echo "  --memory=1Gi \\"
	@echo "  --cpu=1 \\"
	@echo "  --min-instances=0 \\"
	@echo "  --max-instances=2 \\"
	@echo "  --set-env-vars='KC_DB=postgres,KC_DB_USERNAME=postgres,KC_PROXY=edge,KEYCLOAK_ADMIN=admin,KEYCLOAK_ADMIN_PASSWORD=admin' \\"
	@echo "  --add-cloudsql-instances=YOUR_CONNECTION_NAME"

# ============================================================
# Production Deployment Commands (Full Stack)
# ============================================================

deploy:
	@echo "🚀 Running full production deployment..."
	./deployment/deploy.sh all

deploy-setup:
	@echo "⚙️  Setting up GCP resources..."
	./deployment/deploy.sh setup

deploy-build:
	@echo "🔨 Building Docker images..."
	./deployment/deploy.sh build

deploy-backend:
	@echo "🔄 Redeploying backend..."
	./deployment/deploy.sh redeploy-backend

deploy-frontend:
	@echo "🔄 Redeploying frontend..."
	./deployment/deploy.sh redeploy-frontend

deploy-status:
	@echo "📊 Checking deployment status..."
	./deployment/deploy.sh status