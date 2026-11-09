#!/bin/bash

# ============================================
# Keycloak Realm Management Script
# ============================================
# This script provides CLI commands to manage Keycloak realms
# for multi-tenant deployments.
#
# Usage:
#   ./scripts/keycloak-realm.sh <command> [options]
#
# Commands:
#   list                   List all realms
#   create                 Create a new realm with client
#   delete                 Delete a realm
#   info                   Show realm details
#   export                 Export realm config to JSON
#
# Examples:
#   ./scripts/keycloak-realm.sh list
#   ./scripts/keycloak-realm.sh create --realm acme-corp --client-id acme-app
#   ./scripts/keycloak-realm.sh delete --realm acme-corp --confirm
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

print_step() { echo -e "\n${BLUE}==>${NC} ${GREEN}$1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_info() { echo -e "${CYAN}ℹ️  $1${NC}"; }

# Configuration - can be overridden with environment variables
KEYCLOAK_URL="${KEYCLOAK_SERVER_URL:-https://supervity-keycloak-67689851625.us-central1.run.app}"
KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN_USERNAME:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-admin}"

# Check for required tools
check_dependencies() {
    for cmd in curl jq; do
        if ! command -v $cmd &> /dev/null; then
            print_error "$cmd is required but not installed."
            exit 1
        fi
    done
}

# Get admin access token
get_admin_token() {
    local token
    token=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
        -d "client_id=admin-cli" \
        -d "username=${KEYCLOAK_ADMIN}" \
        -d "password=${KEYCLOAK_ADMIN_PASSWORD}" \
        -d "grant_type=password" 2>/dev/null | jq -r '.access_token')
    
    if [ "$token" == "null" ] || [ -z "$token" ]; then
        print_error "Failed to authenticate with Keycloak. Check your credentials."
        exit 1
    fi
    
    echo "$token"
}

# Generate a random client secret
generate_secret() {
    openssl rand -hex 32
}

# List all realms
cmd_list() {
    print_step "Fetching all realms..."
    
    local token
    token=$(get_admin_token)
    
    local realms
    realms=$(curl -s "${KEYCLOAK_URL}/admin/realms" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json")
    
    echo ""
    echo -e "${BOLD}Realms:${NC}"
    echo "$realms" | jq -r '.[] | "  • \(.realm) (enabled: \(.enabled))"'
    echo ""
}

# Create a new realm with client
cmd_create() {
    local realm_name=""
    local client_id=""
    local admin_email=""
    local redirect_uris="http://localhost:3001/*"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --realm)
                realm_name="$2"
                shift 2
                ;;
            --client-id)
                client_id="$2"
                shift 2
                ;;
            --admin-email)
                admin_email="$2"
                shift 2
                ;;
            --redirect-uris)
                redirect_uris="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Validate required args
    if [ -z "$realm_name" ]; then
        print_error "Missing required argument: --realm"
        echo "Usage: $0 create --realm <name> --client-id <id> [--admin-email <email>] [--redirect-uris <uris>]"
        exit 1
    fi
    
    if [ -z "$client_id" ]; then
        client_id="${realm_name}-app"
        print_info "Using default client ID: $client_id"
    fi
    
    print_step "Creating realm: $realm_name"
    
    local token
    token=$(get_admin_token)
    
    local client_secret
    client_secret=$(generate_secret)
    
    # Convert redirect URIs to JSON array
    local redirect_uris_json
    redirect_uris_json=$(echo "$redirect_uris" | tr ',' '\n' | jq -R -s -c 'split("\n") | map(select(length > 0))')
    
    # Create realm JSON
    local realm_json=$(cat <<EOF
{
    "realm": "${realm_name}",
    "enabled": true,
    "registrationAllowed": false,
    "resetPasswordAllowed": true,
    "rememberMe": true,
    "verifyEmail": false,
    "loginWithEmailAllowed": true,
    "duplicateEmailsAllowed": false,
    "loginTheme": "supervity",
    "accountTheme": "supervity",
    "emailTheme": "supervity",
    "accessTokenLifespan": 300,
    "ssoSessionIdleTimeout": 1800,
    "ssoSessionMaxLifespan": 36000,
    "roles": {
        "realm": [
            {
                "name": "admin",
                "description": "Administrator with full access",
                "composite": false
            },
            {
                "name": "user",
                "description": "Regular user with standard access",
                "composite": false
            },
            {
                "name": "pending",
                "description": "User awaiting admin approval",
                "composite": false
            }
        ]
    },
    "defaultRoles": ["offline_access", "uma_authorization"],
    "clients": [
        {
            "clientId": "${client_id}",
            "name": "${realm_name} Application",
            "enabled": true,
            "publicClient": false,
            "secret": "${client_secret}",
            "protocol": "openid-connect",
            "standardFlowEnabled": true,
            "implicitFlowEnabled": false,
            "directAccessGrantsEnabled": false,
            "serviceAccountsEnabled": false,
            "authorizationServicesEnabled": false,
            "redirectUris": ${redirect_uris_json},
            "webOrigins": ["+"],
            "attributes": {
                "pkce.code.challenge.method": "S256"
            }
        }
    ]
}
EOF
)
    
    # Create the realm
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "${KEYCLOAK_URL}/admin/realms" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -d "$realm_json")
    
    local http_code
    http_code=$(echo "$response" | tail -n 1)
    local body
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" == "201" ] || [ "$http_code" == "204" ]; then
        print_success "Realm created successfully!"
    elif [ "$http_code" == "409" ]; then
        print_error "Realm '$realm_name' already exists."
        exit 1
    else
        print_error "Failed to create realm: $body"
        exit 1
    fi
    
    # Create admin user if email provided
    if [ -n "$admin_email" ]; then
        print_step "Creating admin user: $admin_email"
        
        local temp_password
        temp_password=$(openssl rand -base64 12)
        
        local user_json=$(cat <<EOF
{
    "username": "${admin_email}",
    "email": "${admin_email}",
    "enabled": true,
    "emailVerified": true,
    "credentials": [{
        "type": "password",
        "value": "${temp_password}",
        "temporary": true
    }]
}
EOF
)
        
        response=$(curl -s -w "\n%{http_code}" -X POST "${KEYCLOAK_URL}/admin/realms/${realm_name}/users" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" \
            -d "$user_json")
        
        http_code=$(echo "$response" | tail -n 1)
        
        if [ "$http_code" == "201" ]; then
            # Get the user ID and assign admin role
            local user_id
            user_id=$(curl -s "${KEYCLOAK_URL}/admin/realms/${realm_name}/users?email=${admin_email}" \
                -H "Authorization: Bearer $token" | jq -r '.[0].id')
            
            # Get admin role
            local admin_role
            admin_role=$(curl -s "${KEYCLOAK_URL}/admin/realms/${realm_name}/roles/admin" \
                -H "Authorization: Bearer $token")
            
            # Assign admin role
            curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${realm_name}/users/${user_id}/role-mappings/realm" \
                -H "Authorization: Bearer $token" \
                -H "Content-Type: application/json" \
                -d "[${admin_role}]"
            
            print_success "Admin user created with temporary password: $temp_password"
        else
            print_warning "Failed to create admin user (may already exist)"
        fi
    fi
    
    # Output summary
    echo ""
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}Realm Created Successfully!${NC}"
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}Realm Details:${NC}"
    echo -e "  Realm Name:     ${realm_name}"
    echo -e "  Client ID:      ${client_id}"
    echo -e "  Client Secret:  ${client_secret}"
    echo ""
    echo -e "${BOLD}OpenID Connect URLs:${NC}"
    echo -e "  Issuer:         ${KEYCLOAK_URL}/realms/${realm_name}"
    echo -e "  Auth URL:       ${KEYCLOAK_URL}/realms/${realm_name}/protocol/openid-connect/auth"
    echo -e "  Token URL:      ${KEYCLOAK_URL}/realms/${realm_name}/protocol/openid-connect/token"
    echo ""
    echo -e "${BOLD}Environment Variables for .env:${NC}"
    echo -e "  KEYCLOAK_SERVER_URL=${KEYCLOAK_URL}"
    echo -e "  KEYCLOAK_REALM=${realm_name}"
    echo -e "  KEYCLOAK_CLIENT_ID=${client_id}"
    echo -e "  KEYCLOAK_CLIENT_SECRET=${client_secret}"
    echo ""
    if [ -n "$admin_email" ]; then
        echo -e "${BOLD}Admin User:${NC}"
        echo -e "  Email:          ${admin_email}"
        echo -e "  Temp Password:  ${temp_password}"
        echo -e "  ${YELLOW}(User must change password on first login)${NC}"
        echo ""
    fi
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
}

# Delete a realm
cmd_delete() {
    local realm_name=""
    local confirm=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --realm)
                realm_name="$2"
                shift 2
                ;;
            --confirm)
                confirm=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    if [ -z "$realm_name" ]; then
        print_error "Missing required argument: --realm"
        exit 1
    fi
    
    if [ "$confirm" != true ]; then
        print_error "Deleting a realm is permanent. Pass --confirm to proceed."
        exit 1
    fi
    
    if [ "$realm_name" == "master" ]; then
        print_error "Cannot delete the master realm."
        exit 1
    fi
    
    print_step "Deleting realm: $realm_name"
    
    local token
    token=$(get_admin_token)
    
    local response
    response=$(curl -s -w "\n%{http_code}" -X DELETE "${KEYCLOAK_URL}/admin/realms/${realm_name}" \
        -H "Authorization: Bearer $token")
    
    local http_code
    http_code=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" == "204" ]; then
        print_success "Realm '$realm_name' deleted successfully."
    elif [ "$http_code" == "404" ]; then
        print_error "Realm '$realm_name' not found."
        exit 1
    else
        print_error "Failed to delete realm: $(echo "$response" | sed '$d')"
        exit 1
    fi
}

# Show realm info
cmd_info() {
    local realm_name=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --realm)
                realm_name="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    if [ -z "$realm_name" ]; then
        print_error "Missing required argument: --realm"
        exit 1
    fi
    
    print_step "Fetching realm info: $realm_name"
    
    local token
    token=$(get_admin_token)
    
    # Get realm info
    local realm_info
    realm_info=$(curl -s "${KEYCLOAK_URL}/admin/realms/${realm_name}" \
        -H "Authorization: Bearer $token")
    
    if echo "$realm_info" | jq -e '.error' > /dev/null 2>&1; then
        print_error "Realm not found: $realm_name"
        exit 1
    fi
    
    # Get clients
    local clients
    clients=$(curl -s "${KEYCLOAK_URL}/admin/realms/${realm_name}/clients?first=0&max=100" \
        -H "Authorization: Bearer $token" | jq '[.[] | select(.clientId | startswith("account") | not) | select(.clientId | startswith("admin") | not) | select(.clientId | startswith("broker") | not) | select(.clientId | startswith("realm") | not) | select(.clientId | startswith("security") | not)]')
    
    # Get user count
    local user_count
    user_count=$(curl -s "${KEYCLOAK_URL}/admin/realms/${realm_name}/users/count" \
        -H "Authorization: Bearer $token")
    
    echo ""
    echo -e "${BOLD}Realm: ${realm_name}${NC}"
    echo -e "  Enabled:              $(echo "$realm_info" | jq -r '.enabled')"
    echo -e "  Login Theme:          $(echo "$realm_info" | jq -r '.loginTheme // "keycloak"')"
    echo -e "  Registration Allowed: $(echo "$realm_info" | jq -r '.registrationAllowed')"
    echo -e "  Email Verification:   $(echo "$realm_info" | jq -r '.verifyEmail')"
    echo -e "  User Count:           ${user_count}"
    echo ""
    echo -e "${BOLD}Clients:${NC}"
    echo "$clients" | jq -r '.[] | "  • \(.clientId) (enabled: \(.enabled))"'
    echo ""
    echo -e "${BOLD}OpenID Connect URLs:${NC}"
    echo -e "  Issuer: ${KEYCLOAK_URL}/realms/${realm_name}"
    echo ""
}

# Export realm configuration
cmd_export() {
    local realm_name=""
    local output_file=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --realm)
                realm_name="$2"
                shift 2
                ;;
            --output)
                output_file="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    if [ -z "$realm_name" ]; then
        print_error "Missing required argument: --realm"
        exit 1
    fi
    
    if [ -z "$output_file" ]; then
        output_file="${realm_name}-realm.json"
    fi
    
    print_step "Exporting realm: $realm_name"
    
    local token
    token=$(get_admin_token)
    
    curl -s "${KEYCLOAK_URL}/admin/realms/${realm_name}" \
        -H "Authorization: Bearer $token" | jq '.' > "$output_file"
    
    print_success "Realm exported to: $output_file"
}

# Show usage help
show_help() {
    echo ""
    echo -e "${BOLD}${CYAN}Keycloak Realm Management${NC}"
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo "  $0 <command> [options]"
    echo ""
    echo -e "${BOLD}Commands:${NC}"
    echo "  list                              List all realms"
    echo "  create                            Create a new realm with client"
    echo "  delete                            Delete a realm (dangerous)"
    echo "  info                              Show realm details"
    echo "  export                            Export realm configuration"
    echo ""
    echo -e "${BOLD}Create Options:${NC}"
    echo "  --realm <name>                    Realm name (required)"
    echo "  --client-id <id>                  OAuth client ID (default: <realm>-app)"
    echo "  --admin-email <email>             Create admin user with this email"
    echo "  --redirect-uris <uris>            Comma-separated redirect URIs"
    echo ""
    echo -e "${BOLD}Delete Options:${NC}"
    echo "  --realm <name>                    Realm name (required)"
    echo "  --confirm                         Confirm deletion (required)"
    echo ""
    echo -e "${BOLD}Info/Export Options:${NC}"
    echo "  --realm <name>                    Realm name (required)"
    echo "  --output <file>                   Output file (export only)"
    echo ""
    echo -e "${BOLD}Environment Variables:${NC}"
    echo "  KEYCLOAK_SERVER_URL               Keycloak server URL"
    echo "  KEYCLOAK_ADMIN_USERNAME           Admin username (default: admin)"
    echo "  KEYCLOAK_ADMIN_PASSWORD           Admin password"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  # List all realms"
    echo "  $0 list"
    echo ""
    echo "  # Create a new realm for a client"
    echo "  $0 create --realm acme-corp --client-id acme-app \\"
    echo "      --admin-email admin@acme.com \\"
    echo "      --redirect-uris 'http://localhost:3001/*,https://acme.example.com/*'"
    echo ""
    echo "  # Get realm information"
    echo "  $0 info --realm acme-corp"
    echo ""
    echo "  # Delete a realm (requires confirmation)"
    echo "  $0 delete --realm acme-corp --confirm"
    echo ""
}

# Main entry point
main() {
    check_dependencies
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        list)
            cmd_list "$@"
            ;;
        create)
            cmd_create "$@"
            ;;
        delete)
            cmd_delete "$@"
            ;;
        info)
            cmd_info "$@"
            ;;
        export)
            cmd_export "$@"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
