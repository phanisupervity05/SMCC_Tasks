#!/bin/bash

# ===================================================================
#      AI COMMAND CENTER - GCP CLOUD RUN DEPLOYMENT SCRIPT
# -------------------------------------------------------------------
#  This script deploys all services to Google Cloud Run.
#  
#  Prerequisites:
#  - Google Cloud CLI (gcloud) installed and configured
#  - Docker installed and running
#  - Copy prod.env.example to prod.env and fill in your values
#
#  Usage:
#    ./deployment/deploy.sh [command]
#  
#  Commands:
#    setup              - Initial GCP setup (APIs, Artifact Registry, Cloud SQL)
#    build              - Build and push all Docker images
#    deploy             - Deploy all services to Cloud Run
#    all                - Run all phases (first time deployment)
#    status             - Show deployment status
#    migrate            - Run database migrations
#    redeploy           - Rebuild and redeploy ALL services
#    redeploy-backend   - Rebuild and redeploy Backend only
#    redeploy-frontend  - Rebuild and redeploy Frontend only
#    logs [service]     - Show logs (default: backend)
#    secrets            - Create/update secrets in Secret Manager
# ===================================================================

set -e  # Exit on error

# ============================================
# LOAD CONFIGURATION FROM prod.env
# ============================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/prod.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: prod.env not found!"
    echo "   Please copy prod.env.example to prod.env and fill in your values."
    echo "   cp ${SCRIPT_DIR}/prod.env.example ${SCRIPT_DIR}/prod.env"
    exit 1
fi

# Load environment variables
set -a
source "$ENV_FILE"
set +a

echo "📋 Loaded configuration from: $ENV_FILE"

# ============================================
# DERIVED CONFIGURATION
# ============================================
IMAGE_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
BACKEND_IMAGE="${IMAGE_PREFIX}/backend"
FRONTEND_IMAGE="${IMAGE_PREFIX}/frontend"

# Get project root directory
get_project_root() {
    cd "$SCRIPT_DIR/.."
    pwd
}

# Get git commit hash (7 chars)
get_git_tag() {
    cd "$(get_project_root)"
    git rev-parse --short=7 HEAD 2>/dev/null || echo "unknown"
}

# ============================================
# COLORS FOR OUTPUT
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

print_step() {
    echo -e "\n${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}
print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

print_header() {
    echo -e "\n${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC} ${BOLD}${CYAN}$1${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}"
}

# Timer functions
START_TIME=""
start_timer() {
    START_TIME=$(date +%s)
}

show_elapsed() {
    local END_TIME=$(date +%s)
    local ELAPSED=$((END_TIME - START_TIME))
    local MINUTES=$((ELAPSED / 60))
    local SECONDS=$((ELAPSED % 60))
    echo -e "${CYAN}⏱️  Completed in ${MINUTES}m ${SECONDS}s${NC}"
}

# ============================================
# HELPER FUNCTIONS
# ============================================
get_service_url() {
    local service=$1
    # Get project number for correct URL format
    local PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)' 2>/dev/null)
    if [ -n "$PROJECT_NUMBER" ]; then
        # Use the new URL format: https://SERVICE-PROJECT_NUMBER.REGION.run.app
        echo "https://${service}-${PROJECT_NUMBER}.${REGION}.run.app"
    else
        # Fallback to describe method
        gcloud run services describe ${service} --region=${REGION} --format='value(status.url)' 2>/dev/null || echo ""
    fi
}

get_db_connection() {
    gcloud sql instances describe ${DB_INSTANCE_NAME} --format='value(connectionName)' 2>/dev/null || echo ""
}

get_db_ip() {
    gcloud sql instances describe ${DB_INSTANCE_NAME} --format='value(ipAddresses[0].ipAddress)' 2>/dev/null || echo ""
}

# ============================================
# PHASE: SETUP
# ============================================
phase_setup() {
    print_header "Setting up GCP project: ${PROJECT_ID}"
    start_timer
    
    gcloud config set project ${PROJECT_ID}
    
    print_step "Enabling required APIs..."
    gcloud services enable \
        run.googleapis.com \
        sqladmin.googleapis.com \
        artifactregistry.googleapis.com \
        compute.googleapis.com \
        cloudbuild.googleapis.com \
        secretmanager.googleapis.com
    
    print_step "Creating Artifact Registry repository..."
    gcloud artifacts repositories create ${REPO_NAME} \
        --repository-format=docker \
        --location=${REGION} \
        --description="AI Command Center Docker images" \
        2>/dev/null || print_warning "Repository already exists"
    
    print_step "Configuring Docker authentication..."
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
    
    print_step "Creating Cloud SQL instance (this may take 5-10 minutes)..."
    if ! gcloud sql instances describe ${DB_INSTANCE_NAME} --project=${PROJECT_ID} &>/dev/null; then
        gcloud sql instances create ${DB_INSTANCE_NAME} \
            --database-version=POSTGRES_15 \
            --cpu=1 \
            --memory=4GiB \
            --region=${REGION} \
            --root-password="${DB_PASSWORD}" \
            --no-assign-ip=false
        
        print_step "Creating database..."
        gcloud sql databases create ${DB_NAME} --instance=${DB_INSTANCE_NAME}
        
        print_step "Enabling SSL for secure connections..."
        gcloud sql instances patch ${DB_INSTANCE_NAME} \
            --require-ssl \
            --quiet
        
        print_info "Database secured - Cloud Run uses Cloud SQL connector (no public network access)"
    else
        print_warning "Cloud SQL instance already exists"
    fi
    
    # Create secrets
    setup_secrets
    
    DB_CONNECTION_NAME=$(get_db_connection)
    
    show_elapsed
    print_success "Setup complete!"
    echo ""
    echo "Database Connection: ${DB_CONNECTION_NAME}"
    echo "Database IP: $(get_db_ip)"
}

# ============================================
# SECRETS MANAGEMENT
# ============================================
setup_secrets() {
    print_step "Setting up Secret Manager secrets..."
    
    local DB_CONNECTION_NAME=$(get_db_connection)
    # Use Cloud SQL connector format (Unix socket) for secure connection
    local DB_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
    
    # Create or update DATABASE_URL secret
    if gcloud secrets describe ${SECRET_DB_URL} --project=${PROJECT_ID} &>/dev/null; then
        echo -n "${DB_URL}" | gcloud secrets versions add ${SECRET_DB_URL} --data-file=-
    else
        echo -n "${DB_URL}" | gcloud secrets create ${SECRET_DB_URL} --data-file=-
    fi
    print_success "Secret ${SECRET_DB_URL} configured"
    
    # Create or update KEYCLOAK_CLIENT_SECRET
    if gcloud secrets describe ${SECRET_KEYCLOAK_CLIENT_SECRET} --project=${PROJECT_ID} &>/dev/null; then
        echo -n "${KEYCLOAK_CLIENT_SECRET}" | gcloud secrets versions add ${SECRET_KEYCLOAK_CLIENT_SECRET} --data-file=-
    else
        echo -n "${KEYCLOAK_CLIENT_SECRET}" | gcloud secrets create ${SECRET_KEYCLOAK_CLIENT_SECRET} --data-file=-
    fi
    print_success "Secret ${SECRET_KEYCLOAK_CLIENT_SECRET} configured"
    
    # Create or update NEXTAUTH_SECRET
    if gcloud secrets describe ${SECRET_NEXTAUTH_SECRET} --project=${PROJECT_ID} &>/dev/null; then
        echo -n "${NEXTAUTH_SECRET}" | gcloud secrets versions add ${SECRET_NEXTAUTH_SECRET} --data-file=-
    else
        echo -n "${NEXTAUTH_SECRET}" | gcloud secrets create ${SECRET_NEXTAUTH_SECRET} --data-file=-
    fi
    print_success "Secret ${SECRET_NEXTAUTH_SECRET} configured"
    
    # Grant Cloud Run access to secrets
    print_step "Granting Cloud Run access to secrets..."
    local SA="${PROJECT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
    local COMPUTE_SA="$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
    
    for secret in ${SECRET_DB_URL} ${SECRET_KEYCLOAK_CLIENT_SECRET} ${SECRET_NEXTAUTH_SECRET}; do
        gcloud secrets add-iam-policy-binding ${secret} \
            --member="serviceAccount:${COMPUTE_SA}" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
    done
}

# ============================================
# BUILD FUNCTIONS
# ============================================
build_backend() {
    print_step "Building Backend..."
    local PROJECT_ROOT=$(get_project_root)
    local GIT_TAG=$(get_git_tag)
    
    echo "  Git commit: ${GIT_TAG}"
    
    docker build --platform linux/amd64 \
        -t ${BACKEND_IMAGE}:latest \
        -t ${BACKEND_IMAGE}:${GIT_TAG} \
        ${PROJECT_ROOT}
    
    docker push ${BACKEND_IMAGE}:latest
    docker push ${BACKEND_IMAGE}:${GIT_TAG}
    
    print_success "Backend built and pushed (tag: ${GIT_TAG})"
}

build_frontend() {
    print_step "Building Frontend..."
    local PROJECT_ROOT=$(get_project_root)
    local BACKEND_URL=$(get_service_url ${BACKEND_SERVICE})
    local FRONTEND_URL=$(get_service_url ${FRONTEND_SERVICE})
    local GIT_TAG=$(get_git_tag)
    
    if [ -z "$BACKEND_URL" ]; then
        print_error "Backend not deployed yet. Deploy backend first!"
        exit 1
    fi
    
    # Construct the NextAuth URL - use placeholder if frontend not deployed yet
    if [ -z "$FRONTEND_URL" ]; then
        FRONTEND_URL="https://${FRONTEND_SERVICE}-placeholder.${REGION}.run.app"
    fi
    local NEXTAUTH_URL_BUILD="${FRONTEND_URL}${BASE_PATH}"
    
    echo "  Git commit: ${GIT_TAG}"
    echo "  Backend API URL: ${BACKEND_URL}"
    echo "  Keycloak URL: ${KEYCLOAK_SERVER_URL}"
    echo "  NextAuth URL (build): ${NEXTAUTH_URL_BUILD}"
    
    docker build --platform linux/amd64 --no-cache \
        --build-arg NEXT_PUBLIC_API_URL=${BACKEND_URL} \
        --build-arg NEXT_PUBLIC_KEYCLOAK_URL=${KEYCLOAK_SERVER_URL} \
        --build-arg NEXT_PUBLIC_BASE_PATH="${BASE_PATH:-}" \
        --build-arg KEYCLOAK_SERVER_URL=${KEYCLOAK_SERVER_URL} \
        --build-arg KEYCLOAK_REALM=${KEYCLOAK_REALM} \
        --build-arg KEYCLOAK_CLIENT_ID=${KEYCLOAK_CLIENT_ID} \
        --build-arg KEYCLOAK_CLIENT_SECRET=${KEYCLOAK_CLIENT_SECRET} \
        --build-arg KEYCLOAK_AUDIENCE=${KEYCLOAK_AUDIENCE} \
        --build-arg NEXTAUTH_URL=${NEXTAUTH_URL_BUILD} \
        --build-arg NEXTAUTH_SECRET=${NEXTAUTH_SECRET} \
        -t ${FRONTEND_IMAGE}:latest \
        -t ${FRONTEND_IMAGE}:${GIT_TAG} \
        ${PROJECT_ROOT}/frontend
    
    docker push ${FRONTEND_IMAGE}:latest
    docker push ${FRONTEND_IMAGE}:${GIT_TAG}
    
    print_success "Frontend built and pushed (tag: ${GIT_TAG})"
}

# ============================================
# DEPLOY FUNCTIONS
# ============================================
deploy_backend() {
    print_step "Deploying Backend to Cloud Run..."
    
    local DB_CONNECTION_NAME=$(get_db_connection)
    
    if [ -z "$DB_CONNECTION_NAME" ]; then
        print_error "Could not find Cloud SQL instance. Run './deployment/deploy.sh setup' first."
        exit 1
    fi
    
    # Get Frontend URL for CORS
    local FRONTEND_URL=$(get_service_url ${FRONTEND_SERVICE})
    local CORS_ORIGINS="${FRONTEND_URL:-*}"
    
    # Deploy with Cloud SQL connector (secure connection via Unix socket)
    # APP_ENV=production triggers multi-worker mode and skips migrations (run via Job)
    # GCS_BUCKET and GCS_PREFIX configure cloud storage for file uploads
    local GCS_ENV=""
    if [ -n "${GCS_BUCKET}" ]; then
        GCS_ENV=",STORAGE_BACKEND=gcs,GCS_BUCKET=${GCS_BUCKET},GCS_PREFIX=${GCS_PREFIX:-}"
    fi
    
    gcloud run deploy ${BACKEND_SERVICE} \
        --image ${BACKEND_IMAGE}:latest \
        --region ${REGION} \
        --port 8000 \
        --memory ${BACKEND_MEMORY} \
        --cpu ${BACKEND_CPU} \
        --timeout ${BACKEND_TIMEOUT} \
        --min-instances ${BACKEND_MIN_INSTANCES} \
        --max-instances ${BACKEND_MAX_INSTANCES} \
        --add-cloudsql-instances=${DB_CONNECTION_NAME} \
        --set-env-vars="APP_ENV=production,BASE_PATH=${BASE_PATH},KEYCLOAK_SERVER_URL=${KEYCLOAK_SERVER_URL},KEYCLOAK_REALM=${KEYCLOAK_REALM},KEYCLOAK_CLIENT_ID=${KEYCLOAK_CLIENT_ID},KEYCLOAK_AUDIENCE=${KEYCLOAK_AUDIENCE},LOG_LEVEL=${LOG_LEVEL},SUPERVITY_AUTH_DEBUG=${SUPERVITY_AUTH_DEBUG},FRONTEND_URL=${CORS_ORIGINS}${GCS_ENV}" \
        --set-secrets="DATABASE_URL=${SECRET_DB_URL}:latest,KEYCLOAK_CLIENT_SECRET=${SECRET_KEYCLOAK_CLIENT_SECRET}:latest" \
        --allow-unauthenticated \
        --session-affinity \
        --quiet
    
    local URL=$(get_service_url ${BACKEND_SERVICE})
    print_success "Backend deployed: ${URL}"
}

deploy_frontend() {
    print_step "Deploying Frontend to Cloud Run..."
    
    local FRONTEND_URL=$(get_service_url ${FRONTEND_SERVICE})
    local BACKEND_URL=$(get_service_url ${BACKEND_SERVICE})
    local NEXTAUTH_URL="${FRONTEND_URL}${BASE_PATH}"
    
    gcloud run deploy ${FRONTEND_SERVICE} \
        --image ${FRONTEND_IMAGE}:latest \
        --region ${REGION} \
        --port 3000 \
        --memory ${FRONTEND_MEMORY} \
        --cpu ${FRONTEND_CPU} \
        --min-instances ${FRONTEND_MIN_INSTANCES} \
        --max-instances ${FRONTEND_MAX_INSTANCES} \
        --set-env-vars="NEXT_PUBLIC_API_URL=${BACKEND_URL},NEXT_PUBLIC_KEYCLOAK_URL=${KEYCLOAK_SERVER_URL},NEXT_PUBLIC_BASE_PATH=${BASE_PATH:-},KEYCLOAK_SERVER_URL=${KEYCLOAK_SERVER_URL},KEYCLOAK_REALM=${KEYCLOAK_REALM},KEYCLOAK_CLIENT_ID=${KEYCLOAK_CLIENT_ID},KEYCLOAK_AUDIENCE=${KEYCLOAK_AUDIENCE},NEXTAUTH_URL=${NEXTAUTH_URL}" \
        --set-secrets="KEYCLOAK_CLIENT_SECRET=${SECRET_KEYCLOAK_CLIENT_SECRET}:latest,NEXTAUTH_SECRET=${SECRET_NEXTAUTH_SECRET}:latest" \
        --allow-unauthenticated \
        --quiet
    
    local URL=$(get_service_url ${FRONTEND_SERVICE})
    print_success "Frontend deployed: ${URL}"
}

# ============================================
# DATABASE MIGRATION
# ============================================
run_migrations() {
    print_header "Running Database Migrations"
    start_timer
    
    local DB_CONNECTION_NAME=$(get_db_connection)
    
    if [ -z "$DB_CONNECTION_NAME" ]; then
        print_error "Could not find Cloud SQL instance."
        exit 1
    fi
    
    print_step "Creating migration job..."
    
    # Use Cloud SQL connector (Unix socket) for secure connection
    local DB_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
    
    if gcloud run jobs describe migrate-db --region=${REGION} &>/dev/null; then
        gcloud run jobs update migrate-db \
            --image ${BACKEND_IMAGE}:latest \
            --region ${REGION} \
            --set-cloudsql-instances=${DB_CONNECTION_NAME} \
            --set-env-vars="DATABASE_URL=${DB_URL}" \
            --command "alembic" \
            --args "upgrade,head" \
            --memory 1Gi \
            --task-timeout 300 \
            --quiet
    else
        gcloud run jobs create migrate-db \
            --image ${BACKEND_IMAGE}:latest \
            --region ${REGION} \
            --set-cloudsql-instances=${DB_CONNECTION_NAME} \
            --set-env-vars="DATABASE_URL=${DB_URL}" \
            --command "alembic" \
            --args "upgrade,head" \
            --memory 1Gi \
            --task-timeout 300
    fi
    
    print_step "Executing migrations..."
    gcloud run jobs execute migrate-db --region ${REGION} --wait
    
    show_elapsed
    print_success "Migrations complete!"
}

# ============================================
# PHASE: BUILD ALL
# ============================================
phase_build() {
    print_header "Building all Docker images"
    start_timer
    
    build_backend
    
    local BACKEND_URL=$(get_service_url ${BACKEND_SERVICE})
    if [ -n "$BACKEND_URL" ]; then
        build_frontend
    else
        print_warning "Skipping frontend build - Backend not deployed yet"
    fi
    
    show_elapsed
    print_success "All images built and pushed!"
}

# ============================================
# PHASE: DEPLOY ALL
# ============================================
phase_deploy() {
    print_header "Deploying services to Cloud Run"
    start_timer
    
    deploy_backend
    run_migrations
    build_frontend
    deploy_frontend
    
    # Update Keycloak redirect URIs reminder
    print_warning "Remember to update Keycloak redirect URIs!"
    local FRONTEND_URL=$(get_service_url ${FRONTEND_SERVICE})
    echo "  Add these to super-client-dnh-dev-0001 in Keycloak Admin:"
    echo "  Valid Redirect URIs: ${FRONTEND_URL}/*"
    echo "  Web Origins: ${FRONTEND_URL}"
    
    show_elapsed
    phase_status_summary
}

# ============================================
# REDEPLOY COMMANDS
# ============================================
redeploy_all() {
    print_header "🔄 REDEPLOYING ALL SERVICES"
    start_timer
    
    build_backend
    deploy_backend
    run_migrations
    build_frontend
    deploy_frontend
    
    show_elapsed
    phase_status_summary
}

redeploy_backend() {
    print_header "🔄 REDEPLOYING BACKEND"
    start_timer
    
    build_backend
    deploy_backend
    run_migrations
    
    show_elapsed
    echo ""
    echo -e "🔧 Backend: $(get_service_url ${BACKEND_SERVICE})"
}

redeploy_frontend() {
    print_header "🔄 REDEPLOYING FRONTEND"
    start_timer
    
    build_frontend
    deploy_frontend
    
    show_elapsed
    echo ""
    echo -e "🌐 Frontend: $(get_service_url ${FRONTEND_SERVICE})"
}

# ============================================
# STATUS
# ============================================
phase_status() {
    print_header "Deployment Status"
    
    echo ""
    echo "Cloud Run Services:"
    echo "───────────────────────────────────────────────────────────────"
    
    for service in ${BACKEND_SERVICE} ${FRONTEND_SERVICE}; do
        URL=$(get_service_url ${service})
        if [ -n "$URL" ]; then
            echo -e "${GREEN}✓${NC} ${service}: ${URL}"
        else
            echo -e "${RED}✗${NC} ${service}: NOT DEPLOYED"
        fi
    done
    
    echo ""
    echo "Cloud SQL Instance:"
    echo "───────────────────────────────────────────────────────────────"
    gcloud sql instances describe ${DB_INSTANCE_NAME} --format='table(name,state,connectionName)' 2>/dev/null || echo "NOT CREATED"
    
    echo ""
    echo "Keycloak (Shared):"
    echo "───────────────────────────────────────────────────────────────"
    echo -e "${GREEN}✓${NC} ${KEYCLOAK_SERVER_URL}"
    
    echo ""
    echo "Artifact Registry Images:"
    echo "───────────────────────────────────────────────────────────────"
    gcloud artifacts docker images list ${IMAGE_PREFIX} --format='table(package,tags,createTime)' --sort-by=~createTime --limit=10 2>/dev/null || echo "No images found"
}

phase_status_summary() {
    local FRONTEND_URL=$(get_service_url ${FRONTEND_SERVICE})
    local BACKEND_URL=$(get_service_url ${BACKEND_SERVICE})
    
    echo ""
    echo -e "${MAGENTA}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}🎉 DEPLOYMENT COMPLETE!${NC}"
    echo -e "${MAGENTA}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "🌐 ${BOLD}Frontend:${NC}  ${FRONTEND_URL}${BASE_PATH}"
    echo -e "🔧 ${BOLD}Backend:${NC}   ${BACKEND_URL}"
    echo -e "🔐 ${BOLD}Keycloak:${NC}  ${KEYCLOAK_SERVER_URL}"
    echo ""
    echo -e "${BOLD}Test Credentials:${NC}"
    echo "   👤 Username: super_admin"
    echo "   🔑 Password: password"
    echo ""
}

# ============================================
# STORAGE CLEANUP
# ============================================
cleanup_storage() {
    print_header "🗑️  Cleaning Cloud Storage"
    start_timer
    
    if [ -z "${GCS_BUCKET}" ]; then
        print_warning "GCS_BUCKET not configured, skipping storage cleanup"
        return 0
    fi
    
    local GCS_PATH="gs://${GCS_BUCKET}/${GCS_PREFIX:-}"
    
    print_step "Deleting files from ${GCS_PATH}..."
    
    # List files first
    local file_count=$(gsutil ls -r "${GCS_PATH}**" 2>/dev/null | wc -l || echo "0")
    
    if [ "$file_count" -gt 0 ]; then
        gsutil -m rm -r "${GCS_PATH}**" 2>/dev/null || true
        print_success "Deleted ${file_count} files from GCS"
    else
        print_info "No files to delete in ${GCS_PATH}"
    fi
    
    show_elapsed
}

# ============================================
# DATABASE CLEANUP & RESET
# ============================================
cleanup_db() {
    print_header "🗑️  Cleaning Database"
    start_timer
    
    local DB_CONNECTION_NAME=$(get_db_connection)
    
    if [ -z "$DB_CONNECTION_NAME" ]; then
        print_error "Could not find Cloud SQL instance."
        exit 1
    fi
    
    print_step "Creating cleanup job..."
    
    # Use Cloud SQL connector (Unix socket) for secure connection
    local DB_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
    
    # Create or update cleanup job using scripts/cleanup_db.py
    if gcloud run jobs describe cleanup-db --region=${REGION} &>/dev/null; then
        gcloud run jobs update cleanup-db \
            --image ${BACKEND_IMAGE}:latest \
            --region ${REGION} \
            --set-cloudsql-instances=${DB_CONNECTION_NAME} \
            --set-env-vars="DATABASE_URL=${DB_URL}" \
            --command "python" \
            --args "scripts/cleanup_db.py" \
            --memory 512Mi \
            --task-timeout 60 \
            --quiet
    else
        gcloud run jobs create cleanup-db \
            --image ${BACKEND_IMAGE}:latest \
            --region ${REGION} \
            --set-cloudsql-instances=${DB_CONNECTION_NAME} \
            --set-env-vars="DATABASE_URL=${DB_URL}" \
            --command "python" \
            --args "scripts/cleanup_db.py" \
            --memory 512Mi \
            --task-timeout 60
    fi
    
    print_step "Executing database cleanup..."
    gcloud run jobs execute cleanup-db --region ${REGION} --wait
    
    show_elapsed
    print_success "Database cleaned! All tables dropped."
}

cleanup_all() {
    print_header "🗑️  Full Cleanup (Database + Storage)"
    
    print_warning "This will DELETE ALL DATA in the database AND cloud storage!"
    echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
    sleep 5
    
    cleanup_db
    cleanup_storage
    
    print_success "Full cleanup complete!"
}

reset_db() {
    print_header "🔄 Resetting Database (Clean + Redeploy)"
    start_timer
    
    print_warning "This will DELETE ALL DATA in the database AND cloud storage!"
    echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
    sleep 5
    
    # Step 1: Clean the database (drops all tables)
    cleanup_db
    
    # Step 2: Clean cloud storage
    cleanup_storage
    
    # Step 3: Redeploy backend - it will auto-detect empty DB and run migrations
    print_step "Redeploying backend (will auto-run migrations on empty DB)..."
    local BACKEND_URL=$(get_service_url ${BACKEND_SERVICE})
    
    gcloud run services update ${BACKEND_SERVICE} \
        --region ${REGION} \
        --update-env-vars="DB_RESET_TIMESTAMP=$(date +%s)" \
        --quiet
    
    # Wait for the new revision to start
    print_step "Waiting for new revision to start..."
    sleep 15
    
    # Test the backend
    local max_retries=10
    local retry=0
    while [ $retry -lt $max_retries ]; do
        local health_status=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_URL}/api/health" 2>/dev/null || echo "000")
        
        if [ "$health_status" = "200" ]; then
            print_success "Backend is healthy and migrations completed!"
            break
        fi
        
        retry=$((retry + 1))
        echo "  Waiting for backend... (attempt $retry/$max_retries)"
        sleep 5
    done
    
    if [ $retry -eq $max_retries ]; then
        print_warning "Backend health check timed out. Check logs:"
        echo "  ./deployment/deploy.sh logs"
    fi
    
    show_elapsed
    print_success "Database reset complete!"
}

seed_db() {
    print_header "🌱 Seeding Database"
    start_timer
    
    local DB_CONNECTION_NAME=$(get_db_connection)
    
    if [ -z "$DB_CONNECTION_NAME" ]; then
        print_error "Could not find Cloud SQL instance."
        exit 1
    fi
    
    print_step "Creating seed job..."
    
    local DB_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
    
    # Create or update seed job
    if gcloud run jobs describe seed-db --region=${REGION} &>/dev/null; then
        gcloud run jobs update seed-db \
            --image ${BACKEND_IMAGE}:latest \
            --region ${REGION} \
            --set-cloudsql-instances=${DB_CONNECTION_NAME} \
            --set-env-vars="DATABASE_URL=${DB_URL}" \
            --command "python" \
            --args "scripts/seed_db.py" \
            --memory 512Mi \
            --task-timeout 120 \
            --quiet
    else
        gcloud run jobs create seed-db \
            --image ${BACKEND_IMAGE}:latest \
            --region ${REGION} \
            --set-cloudsql-instances=${DB_CONNECTION_NAME} \
            --set-env-vars="DATABASE_URL=${DB_URL}" \
            --command "python" \
            --args "scripts/seed_db.py" \
            --memory 512Mi \
            --task-timeout 120
    fi
    
    print_step "Executing database seeding..."
    gcloud run jobs execute seed-db --region ${REGION} --wait
    
    show_elapsed
    print_success "Database seeded!"
}

# ============================================
# LOGS
# ============================================
show_logs() {
    local service=${1:-${BACKEND_SERVICE}}
    print_header "Showing logs for ${service}"
    gcloud run services logs read ${service} --region=${REGION} --limit=100
}

# ============================================
# HELP
# ============================================
show_help() {
    echo ""
    echo -e "${BOLD}${CYAN}AI Command Center - GCP Cloud Run Deployment Script${NC}"
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo "  ./deployment/deploy.sh [command]"
    echo ""
    echo -e "${BOLD}Initial Deployment Commands:${NC}"
    echo "  setup              Initial GCP setup (APIs, Artifact Registry, Cloud SQL)"
    echo "  build              Build and push all Docker images"
    echo "  deploy             Deploy all services to Cloud Run"
    echo "  all                Run all phases (first time deployment)"
    echo ""
    echo -e "${BOLD}Quick Redeploy Commands (after code changes):${NC}"
    echo "  redeploy           Rebuild and redeploy ALL services"
    echo "  redeploy-backend   Rebuild and redeploy Backend only"
    echo "  redeploy-frontend  Rebuild and redeploy Frontend only"
    echo ""
    echo -e "${BOLD}Database & Storage Commands:${NC}"
    echo "  migrate            Run database migrations (Alembic)"
    echo "  cleanup-db         Drop all tables (WARNING: destroys all data)"
    echo "  cleanup-storage    Delete all files from GCS"
    echo "  cleanup-all        Clean both DB and GCS storage"
    echo "  reset-db           Clean DB + storage + run migrations + verify"
    echo "  seed-db            Run seed script (scripts/seed_db.py)"
    echo ""
    echo -e "${BOLD}Utility Commands:${NC}"
    echo "  status             Show deployment status"
    echo "  secrets            Create/update secrets in Secret Manager"
    echo "  logs [service]     Show logs (default: backend)"
    echo "  help               Show this help message"
    echo ""
    echo -e "${BOLD}Configuration:${NC}"
    echo "  Edit deployment/prod.env to change settings"
    echo ""
    echo -e "${BOLD}Example First-Time Deployment:${NC}"
    echo "  1. cp deployment/prod.env.example deployment/prod.env"
    echo "  2. Edit deployment/prod.env with your values"
    echo "  3. ./deployment/deploy.sh all"
    echo ""
}

# ============================================
# MAIN
# ============================================
case "${1:-help}" in
    setup)
        phase_setup
        ;;
    build)
        phase_build
        ;;
    deploy)
        phase_deploy
        ;;
    status)
        phase_status
        ;;
    all)
        phase_setup
        phase_build
        phase_deploy
        ;;
    redeploy)
        redeploy_all
        ;;
    redeploy-backend)
        redeploy_backend
        ;;
    redeploy-frontend)
        redeploy_frontend
        ;;
    migrate)
        run_migrations
        ;;
    cleanup-db)
        cleanup_db
        ;;
    cleanup-storage)
        cleanup_storage
        ;;
    cleanup-all)
        cleanup_all
        ;;
    reset-db)
        reset_db
        ;;
    seed-db)
        seed_db
        ;;
    secrets)
        setup_secrets
        ;;
    logs)
        show_logs ${2}
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
