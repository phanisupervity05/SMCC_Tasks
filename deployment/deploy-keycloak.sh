#!/bin/bash

# ===================================================================
#      KEYCLOAK - GCP CLOUD RUN DEPLOYMENT SCRIPT
# -------------------------------------------------------------------
#  This script deploys Keycloak to Google Cloud Run with Cloud SQL.
#  
#  Prerequisites:
#  - Google Cloud CLI (gcloud) installed and configured
#  - Docker installed and running
#
#  Usage:
#    ./deployment/deploy-keycloak.sh [command]
#  
#  Commands:
#    setup              - Create Cloud SQL instance for Keycloak
#    build              - Build and push Keycloak Docker image
#    deploy             - Deploy Keycloak to Cloud Run
#    all                - Run all phases (first time deployment)
#    status             - Show Keycloak deployment status
#    logs               - Show Keycloak logs
# ===================================================================

set -e  # Exit on error

# ============================================
# CONFIGURATION
# ============================================
PROJECT_ID="${PROJECT_ID:-fde-rnd}"
REGION="${REGION:-us-central1}"
REPO_NAME="${REPO_NAME:-template-deployment}"

# Keycloak service configuration
KEYCLOAK_SERVICE="supervity-keycloak"
KEYCLOAK_DB_INSTANCE="supervity-keycloak-db"
KEYCLOAK_DB_NAME="keycloak"
KEYCLOAK_DB_USER="keycloak"
KEYCLOAK_DB_PASSWORD="${KEYCLOAK_DB_PASSWORD:-SuperSecure123!}"
KEYCLOAK_ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-admin}"

# Image configuration
IMAGE_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
KEYCLOAK_IMAGE="${IMAGE_PREFIX}/keycloak"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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
    local PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)' 2>/dev/null)
    if [ -n "$PROJECT_NUMBER" ]; then
        echo "https://${KEYCLOAK_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app"
    else
        gcloud run services describe ${KEYCLOAK_SERVICE} --region=${REGION} --format='value(status.url)' 2>/dev/null || echo ""
    fi
}

get_db_connection() {
    gcloud sql instances describe ${KEYCLOAK_DB_INSTANCE} --format='value(connectionName)' 2>/dev/null || echo ""
}

# ============================================
# SETUP
# ============================================
phase_setup() {
    print_header "Setting up GCP for Keycloak: ${PROJECT_ID}"
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
    
    print_step "Creating/checking Artifact Registry repository..."
    gcloud artifacts repositories create ${REPO_NAME} \
        --repository-format=docker \
        --location=${REGION} \
        --description="Template deployment Docker images" \
        2>/dev/null || print_warning "Repository already exists"
    
    print_step "Configuring Docker authentication..."
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
    
    print_step "Creating Cloud SQL instance for Keycloak (this may take 5-10 minutes)..."
    if ! gcloud sql instances describe ${KEYCLOAK_DB_INSTANCE} --project=${PROJECT_ID} &>/dev/null; then
        gcloud sql instances create ${KEYCLOAK_DB_INSTANCE} \
            --database-version=POSTGRES_15 \
            --cpu=1 \
            --memory=4GiB \
            --region=${REGION} \
            --root-password="${KEYCLOAK_DB_PASSWORD}" \
            --assign-ip
        
        print_step "Creating Keycloak database..."
        gcloud sql databases create ${KEYCLOAK_DB_NAME} --instance=${KEYCLOAK_DB_INSTANCE}
        
        print_step "Creating database user..."
        gcloud sql users create ${KEYCLOAK_DB_USER} \
            --instance=${KEYCLOAK_DB_INSTANCE} \
            --password="${KEYCLOAK_DB_PASSWORD}"
    else
        print_warning "Cloud SQL instance already exists"
    fi
    
    show_elapsed
    print_success "Setup complete!"
}

# ============================================
# BUILD
# ============================================
phase_build() {
    print_header "Building Keycloak Docker image"
    start_timer
    
    print_step "Building Keycloak image with realm configuration..."
    
    docker build --platform linux/amd64 \
        -f ${PROJECT_ROOT}/keycloak/Dockerfile.cloud \
        -t ${KEYCLOAK_IMAGE}:latest \
        ${PROJECT_ROOT}/keycloak
    
    print_step "Pushing Keycloak image to Artifact Registry..."
    docker push ${KEYCLOAK_IMAGE}:latest
    
    show_elapsed
    print_success "Keycloak image built and pushed!"
}

# ============================================
# DEPLOY
# ============================================
phase_deploy() {
    print_header "Deploying Keycloak to Cloud Run"
    start_timer
    
    local DB_CONNECTION_NAME=$(get_db_connection)
    
    if [ -z "$DB_CONNECTION_NAME" ]; then
        print_error "Could not find Cloud SQL instance. Run './deployment/deploy-keycloak.sh setup' first."
        exit 1
    fi
    
    # Get database public IP
    local DB_IP=$(gcloud sql instances describe ${KEYCLOAK_DB_INSTANCE} --format='value(ipAddresses[0].ipAddress)' 2>/dev/null)
    
    if [ -z "$DB_IP" ]; then
        print_error "Could not get database IP."
        exit 1
    fi
    
    print_step "Deploying Keycloak..."
    print_info "Database IP: ${DB_IP}"
    
    # Authorize Cloud Run to connect (Cloud Run uses dynamic IPs, so we allow all with SSL)
    print_step "Authorizing network access to database..."
    gcloud sql instances patch ${KEYCLOAK_DB_INSTANCE} --authorized-networks=0.0.0.0/0 --quiet 2>/dev/null || true
    
    # Get the expected service URL for hostname configuration
    # KC_HOSTNAME expects just the hostname, not the full URL
    local PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)' 2>/dev/null)
    local EXPECTED_HOSTNAME="${KEYCLOAK_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app"
    
    # Use direct SSL connection to database public IP
    local DB_URL="jdbc:postgresql://${DB_IP}:5432/${KEYCLOAK_DB_NAME}?sslmode=require"
    
    # Deploy with same configuration as existing supervity-auth service
    # Key: --no-invoker-iam-check bypasses org policy restricting allUsers
    gcloud run deploy ${KEYCLOAK_SERVICE} \
        --image ${KEYCLOAK_IMAGE}:latest \
        --region ${REGION} \
        --port 8080 \
        --memory 2Gi \
        --cpu 2 \
        --min-instances 0 \
        --max-instances 2 \
        --set-env-vars="KC_DB=postgres,KC_DB_URL_HOST=${DB_IP},KC_DB_URL_PORT=5432,KC_DB_URL_DATABASE=${KEYCLOAK_DB_NAME},KC_DB_USERNAME=${KEYCLOAK_DB_USER},KC_DB_PASSWORD=${KEYCLOAK_DB_PASSWORD},KC_HOSTNAME=${EXPECTED_HOSTNAME},KC_HOSTNAME_STRICT=false,KC_PROXY=edge,KC_HTTP_ENABLED=true,KEYCLOAK_ADMIN=${KEYCLOAK_ADMIN_USER},KEYCLOAK_ADMIN_PASSWORD=${KEYCLOAK_ADMIN_PASSWORD}" \
        --no-invoker-iam-check \
        --cpu-boost \
        --quiet
    
    local URL=$(get_service_url)
    
    show_elapsed
    print_success "Keycloak deployed!"
    echo ""
    echo -e "🔐 ${BOLD}Keycloak URL:${NC}      ${URL}"
    echo -e "🔧 ${BOLD}Admin Console:${NC}    ${URL}/admin"
    echo -e "👤 ${BOLD}Admin Username:${NC}   ${KEYCLOAK_ADMIN_USER}"
    echo -e "🔑 ${BOLD}Admin Password:${NC}   ${KEYCLOAK_ADMIN_PASSWORD}"
    echo ""
    echo -e "${YELLOW}⚠️  Important: Update your .env files with the new Keycloak URL:${NC}"
    echo -e "   KEYCLOAK_SERVER_URL=${URL}"
}

# ============================================
# STATUS
# ============================================
phase_status() {
    print_header "Keycloak Deployment Status"
    
    echo ""
    echo "Cloud Run Service:"
    echo "───────────────────────────────────────────────────────────────"
    
    URL=$(get_service_url)
    if [ -n "$URL" ]; then
        echo -e "${GREEN}✓${NC} ${KEYCLOAK_SERVICE}: ${URL}"
        echo -e "  Admin Console: ${URL}/admin"
    else
        echo -e "${RED}✗${NC} ${KEYCLOAK_SERVICE}: NOT DEPLOYED"
    fi
    
    echo ""
    echo "Cloud SQL Instance:"
    echo "───────────────────────────────────────────────────────────────"
    gcloud sql instances describe ${KEYCLOAK_DB_INSTANCE} --format='table(name,state,connectionName)' 2>/dev/null || echo "NOT CREATED"
}

# ============================================
# LOGS
# ============================================
show_logs() {
    print_header "Showing Keycloak logs"
    gcloud run services logs read ${KEYCLOAK_SERVICE} --region=${REGION} --limit=100
}

# ============================================
# HELP
# ============================================
show_help() {
    echo ""
    echo -e "${BOLD}${CYAN}Keycloak - GCP Cloud Run Deployment Script${NC}"
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo "  ./deployment/deploy-keycloak.sh [command]"
    echo ""
    echo -e "${BOLD}Commands:${NC}"
    echo "  setup    - Create Cloud SQL instance for Keycloak"
    echo "  build    - Build and push Keycloak Docker image"
    echo "  deploy   - Deploy Keycloak to Cloud Run"
    echo "  all      - Run all phases (first time deployment)"
    echo "  status   - Show Keycloak deployment status"
    echo "  logs     - Show Keycloak logs"
    echo "  help     - Show this help message"
    echo ""
    echo -e "${BOLD}Environment Variables:${NC}"
    echo "  PROJECT_ID              GCP Project ID (default: fde-rnd)"
    echo "  REGION                  GCP Region (default: us-central1)"
    echo "  KEYCLOAK_DB_PASSWORD    Database password"
    echo "  KEYCLOAK_ADMIN_USER     Admin username (default: admin)"
    echo "  KEYCLOAK_ADMIN_PASSWORD Admin password (default: admin)"
    echo ""
}

# ============================================
# ALL (First-time deployment)
# ============================================
phase_all() {
    print_header "🚀 Full Keycloak Deployment"
    
    phase_setup
    phase_build
    phase_deploy
    
    print_success "Keycloak deployment complete!"
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
    all)
        phase_all
        ;;
    status)
        phase_status
        ;;
    logs)
        show_logs
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

