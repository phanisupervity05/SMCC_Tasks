#!/bin/bash
# =============================================================================
# Keycloak Management Script
# =============================================================================
# This script helps manage the Keycloak instance deployed on Google Cloud.
#
# Commands:
#   reset-all           - Clear entire Keycloak DB and redeploy fresh
#   reset-realm <name>  - Delete a specific realm (keeps admin and master)
#   list-realms         - List all realms in the Keycloak instance
#   deploy              - Deploy/redeploy Keycloak with current settings
#   status              - Check current Keycloak status
#   logs                - View Keycloak Cloud Run logs
#
# =============================================================================

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-fde-rnd}"
REGION="${GCP_REGION:-us-central1}"
KEYCLOAK_SERVICE="supervity-keycloak"
DB_INSTANCE="supervity-keycloak-db"
DB_NAME="keycloak"
DB_USER="keycloak"
DB_PASSWORD="${KC_DB_PASSWORD:-SupervityKeyDB2024!}"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="SupervityAdmin123$"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${KEYCLOAK_SERVICE}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

confirm() {
    echo ""
    read -p "$(echo -e ${YELLOW}$1 [y/N]: ${NC})" -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

get_keycloak_url() {
    gcloud run services describe $KEYCLOAK_SERVICE \
        --project=$PROJECT_ID \
        --region=$REGION \
        --format='value(status.url)' 2>/dev/null || echo ""
}

get_admin_token() {
    local kc_url=$(get_keycloak_url)
    if [ -z "$kc_url" ]; then
        print_error "Could not get Keycloak URL"
        return 1
    fi
    
    curl -s -X POST "${kc_url}/realms/master/protocol/openid-connect/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=password" \
        -d "client_id=admin-cli" \
        -d "username=${ADMIN_USERNAME}" \
        -d "password=${ADMIN_PASSWORD}" | jq -r '.access_token'
}

# =============================================================================
# Commands
# =============================================================================

cmd_status() {
    print_header "Keycloak Status"
    
    # Check Cloud Run service
    echo "Cloud Run Service:"
    gcloud run services describe $KEYCLOAK_SERVICE \
        --project=$PROJECT_ID \
        --region=$REGION \
        --format='table(status.url, status.conditions[0].status, spec.template.spec.containerConcurrency, spec.template.spec.containers[0].resources.limits.memory)' 2>/dev/null || echo "  Not deployed"
    
    echo ""
    
    # Check Cloud SQL
    echo "Cloud SQL Instance:"
    gcloud sql instances describe $DB_INSTANCE \
        --project=$PROJECT_ID \
        --format='table(name, state, settings.tier, ipAddresses[0].ipAddress)' 2>/dev/null || echo "  Not found"
    
    echo ""
    
    # Check Keycloak health
    local kc_url=$(get_keycloak_url)
    if [ -n "$kc_url" ]; then
        echo "Health Check:"
        local health=$(curl -s -o /dev/null -w "%{http_code}" "${kc_url}/health/ready" 2>/dev/null || echo "000")
        if [ "$health" == "200" ]; then
            print_success "Keycloak is healthy"
        else
            print_warning "Keycloak health check returned: $health"
        fi
    fi
}

cmd_list_realms() {
    print_header "List Realms"
    
    local kc_url=$(get_keycloak_url)
    if [ -z "$kc_url" ]; then
        print_error "Keycloak is not deployed"
        return 1
    fi
    
    local token=$(get_admin_token)
    if [ -z "$token" ] || [ "$token" == "null" ]; then
        print_error "Could not get admin token. Check admin credentials."
        return 1
    fi
    
    echo "Realms in Keycloak:"
    curl -s -X GET "${kc_url}/admin/realms" \
        -H "Authorization: Bearer ${token}" \
        -H "Content-Type: application/json" | jq -r '.[] | "  - \(.realm) (enabled: \(.enabled))"'
}

cmd_reset_realm() {
    local realm_name="$1"
    
    if [ -z "$realm_name" ]; then
        print_error "Usage: $0 reset-realm <realm-name>"
        exit 1
    fi
    
    if [ "$realm_name" == "master" ]; then
        print_error "Cannot delete the master realm"
        exit 1
    fi
    
    print_header "Reset Realm: $realm_name"
    
    if ! confirm "This will DELETE the realm '$realm_name' and all its users. Continue?"; then
        print_info "Cancelled"
        return 0
    fi
    
    local kc_url=$(get_keycloak_url)
    local token=$(get_admin_token)
    
    if [ -z "$token" ] || [ "$token" == "null" ]; then
        print_error "Could not get admin token"
        return 1
    fi
    
    echo "Deleting realm '$realm_name'..."
    local response=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
        "${kc_url}/admin/realms/${realm_name}" \
        -H "Authorization: Bearer ${token}")
    
    if [ "$response" == "204" ]; then
        print_success "Realm '$realm_name' deleted"
    elif [ "$response" == "404" ]; then
        print_warning "Realm '$realm_name' not found"
    else
        print_error "Failed to delete realm (HTTP $response)"
    fi
}

cmd_reset_all() {
    print_header "Reset Entire Keycloak Database"
    
    echo -e "${RED}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                        ⚠️  WARNING ⚠️                           ║${NC}"
    echo -e "${RED}║                                                                ║${NC}"
    echo -e "${RED}║  This will:                                                    ║${NC}"
    echo -e "${RED}║  1. Stop the Keycloak service                                  ║${NC}"
    echo -e "${RED}║  2. DELETE the entire Keycloak database                        ║${NC}"
    echo -e "${RED}║  3. Recreate an empty database                                 ║${NC}"
    echo -e "${RED}║  4. Redeploy Keycloak with base realm + admin user             ║${NC}"
    echo -e "${RED}║                                                                ║${NC}"
    echo -e "${RED}║  ALL USERS AND DATA WILL BE LOST!                              ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if ! confirm "Are you absolutely sure you want to reset everything?"; then
        print_info "Cancelled"
        return 0
    fi
    
    read -p "Type 'RESET' to confirm: " confirmation
    if [ "$confirmation" != "RESET" ]; then
        print_info "Cancelled - confirmation not received"
        return 0
    fi
    
    # Step 1: Stop Cloud Run service
    print_info "Step 1: Stopping Keycloak service..."
    gcloud run services update-traffic $KEYCLOAK_SERVICE \
        --project=$PROJECT_ID \
        --region=$REGION \
        --to-revisions="" \
        --quiet 2>/dev/null || true
    
    # Step 2: Restart Cloud SQL to clear connections
    print_info "Step 2: Restarting Cloud SQL instance..."
    gcloud sql instances restart $DB_INSTANCE --project=$PROJECT_ID --quiet || true
    sleep 30
    
    # Step 3: Delete the database
    print_info "Step 3: Deleting Keycloak database..."
    gcloud sql databases delete $DB_NAME \
        --instance=$DB_INSTANCE \
        --project=$PROJECT_ID \
        --quiet 2>/dev/null || print_warning "Database may not exist"
    
    # Step 4: Recreate the database
    print_info "Step 4: Creating fresh database..."
    gcloud sql databases create $DB_NAME \
        --instance=$DB_INSTANCE \
        --project=$PROJECT_ID \
        --charset=UTF8 \
        --quiet
    
    # Step 5: Redeploy Keycloak
    print_info "Step 5: Redeploying Keycloak..."
    cmd_deploy
    
    print_success "Keycloak reset complete!"
    echo ""
    echo "Admin credentials:"
    echo "  Username: $ADMIN_USERNAME"
    echo "  Password: $ADMIN_PASSWORD"
}

cmd_deploy() {
    print_header "Deploy Keycloak"
    
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local KC_DOCKERFILE="${SCRIPT_DIR}/Dockerfile.cloud"
    
    # Get Cloud SQL instance IP
    print_info "Getting Cloud SQL instance details..."
    DB_HOST=$(gcloud sql instances describe $DB_INSTANCE \
        --project=$PROJECT_ID \
        --format='value(ipAddresses[0].ipAddress)' 2>/dev/null)
    
    if [ -z "$DB_HOST" ]; then
        print_error "Could not get Cloud SQL IP. Make sure the instance exists."
        exit 1
    fi
    print_info "Database host: $DB_HOST"
    
    # Build the Docker image
    print_info "Building Keycloak Docker image..."
    docker build -t ${IMAGE_NAME}:latest -f ${KC_DOCKERFILE} ${SCRIPT_DIR}
    
    # Push to GCR
    print_info "Pushing image to Container Registry..."
    docker push ${IMAGE_NAME}:latest
    
    # Deploy to Cloud Run
    print_info "Deploying to Cloud Run (min 1 instance)..."
    gcloud run deploy $KEYCLOAK_SERVICE \
        --project=$PROJECT_ID \
        --region=$REGION \
        --image=${IMAGE_NAME}:latest \
        --platform=managed \
        --allow-unauthenticated \
        --no-invoker-iam-check \
        --port=8080 \
        --cpu=1 \
        --memory=1Gi \
        --min-instances=1 \
        --max-instances=5 \
        --timeout=240s \
        --set-env-vars="KEYCLOAK_ADMIN=${ADMIN_USERNAME}" \
        --set-env-vars="KEYCLOAK_ADMIN_PASSWORD=${ADMIN_PASSWORD}" \
        --set-env-vars="KC_DB=postgres" \
        --set-env-vars="KC_DB_URL=jdbc:postgresql://${DB_HOST}:5432/${DB_NAME}" \
        --set-env-vars="KC_DB_USERNAME=${DB_USER}" \
        --set-env-vars="KC_DB_PASSWORD=${DB_PASSWORD}" \
        --set-env-vars="KC_PROXY=edge" \
        --set-env-vars="KC_HOSTNAME_STRICT=false" \
        --set-env-vars="KC_HTTP_ENABLED=true" \
        --set-env-vars="KC_HEALTH_ENABLED=true" \
        --set-env-vars="KC_METRICS_ENABLED=true" \
        --quiet
    
    # Get the URL
    local kc_url=$(get_keycloak_url)
    
    print_success "Keycloak deployed successfully!"
    echo ""
    echo "Keycloak URL: $kc_url"
    echo ""
    echo "Admin Console: ${kc_url}/admin"
    echo "  Username: $ADMIN_USERNAME"
    echo "  Password: $ADMIN_PASSWORD"
    echo ""
    
    # Wait for health
    print_info "Waiting for Keycloak to be ready..."
    for i in {1..30}; do
        local health=$(curl -s -o /dev/null -w "%{http_code}" "${kc_url}/health/ready" 2>/dev/null || echo "000")
        if [ "$health" == "200" ]; then
            print_success "Keycloak is ready!"
            return 0
        fi
        echo -n "."
        sleep 5
    done
    print_warning "Keycloak may still be starting up. Check logs with: $0 logs"
}

cmd_logs() {
    print_header "Keycloak Logs"
    
    gcloud run logs read $KEYCLOAK_SERVICE \
        --project=$PROJECT_ID \
        --region=$REGION \
        --limit=100
}

cmd_help() {
    echo "Keycloak Management Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  status           Show current Keycloak status"
    echo "  list-realms      List all realms in Keycloak"
    echo "  reset-realm <n>  Delete a specific realm (by name)"
    echo "  reset-all        ⚠️  Reset entire DB and redeploy fresh"
    echo "  deploy           Deploy/redeploy Keycloak with min 1 instance"
    echo "  logs             View Cloud Run logs"
    echo "  help             Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  GCP_PROJECT_ID   GCP project (default: fde-rnd)"
    echo "  GCP_REGION       GCP region (default: us-central1)"
    echo "  KC_DB_PASSWORD   Database password"
    echo ""
    echo "Default Admin Credentials:"
    echo "  Username: $ADMIN_USERNAME"
    echo "  Password: $ADMIN_PASSWORD"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

case "${1:-help}" in
    status)
        cmd_status
        ;;
    list-realms)
        cmd_list_realms
        ;;
    reset-realm)
        cmd_reset_realm "$2"
        ;;
    reset-all)
        cmd_reset_all
        ;;
    deploy)
        cmd_deploy
        ;;
    logs)
        cmd_logs
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        print_error "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac

