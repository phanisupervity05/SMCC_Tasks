# Keycloak Configuration & Deployment Guide

This directory contains the Keycloak identity provider configuration for the Supervity application.

## 📁 Directory Structure

```
keycloak/
├── README.md                    # This file
├── Dockerfile.cloud             # Production Docker image for Cloud Run
├── import/
│   └── supervity-realm.json     # Realm configuration (users, clients, roles)
└── themes/
    └── supervity/               # Custom theme (removes Keycloak branding)
        ├── login/               # Login page theme
        ├── account/             # Account management theme
        └── email/               # Email template theme
```

---

## 🚀 Deploying a New Keycloak Instance

### Prerequisites

1. **GCP Authentication**
   ```bash
   gcloud auth login your-email@domain.com
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Required APIs** (enabled automatically by deploy script)
   - Cloud Run
   - Cloud SQL Admin
   - Artifact Registry
   - Secret Manager

### Quick Deploy (Recommended)

```bash
# Deploy everything (Cloud SQL + Keycloak)
./deployment/deploy-keycloak.sh all

# Or run individual steps:
./deployment/deploy-keycloak.sh setup   # Create Cloud SQL instance
./deployment/deploy-keycloak.sh build   # Build Docker image
./deployment/deploy-keycloak.sh deploy  # Deploy to Cloud Run
```

### Environment Variables

Set these before deploying:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ID` | `fde-rnd` | GCP Project ID |
| `REGION` | `us-central1` | GCP Region |
| `KEYCLOAK_ADMIN_PASSWORD` | `admin` | Initial admin password |

Example:
```bash
PROJECT_ID=my-project KEYCLOAK_ADMIN_PASSWORD=SecurePass123! ./deployment/deploy-keycloak.sh all
```

---

## 🗄️ Database Configuration

### Cloud SQL Instance

| Setting | Value |
|---------|-------|
| **Instance Name** | `supervity-keycloak-db` |
| **Database** | `keycloak` |
| **Username** | `keycloak` |
| **Engine** | PostgreSQL 15 |
| **Region** | us-central1 |

### Reset Database (Fresh Start)

```bash
# 1. Stop Keycloak service
gcloud run services delete supervity-keycloak --region=us-central1 --quiet

# 2. Restart Cloud SQL to clear connections
gcloud sql instances restart supervity-keycloak-db

# 3. Delete and recreate database
gcloud sql databases delete keycloak --instance=supervity-keycloak-db --quiet
gcloud sql databases create keycloak --instance=supervity-keycloak-db

# 4. Redeploy Keycloak
./deployment/deploy-keycloak.sh deploy
```

### View Database Password

```bash
gcloud secrets versions access latest --secret=supervity-keycloak-db-password
```

---

## 🔐 Admin Credentials

After fresh deployment:

| | |
|---|---|
| **Admin Console** | `https://supervity-keycloak-{PROJECT_NUMBER}.{REGION}.run.app/admin` |
| **Username** | `admin` |
| **Password** | Value of `KEYCLOAK_ADMIN_PASSWORD` (default: `admin`) |

### Change Admin Password

1. Login to Admin Console
2. Go to **master** realm → **Users** → **admin**
3. **Credentials** tab → **Set password**

Or via API:
```bash
# Get admin token
TOKEN=$(curl -s -X POST "https://YOUR_KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=OLD_PASSWORD" \
  -d "grant_type=password" | jq -r '.access_token')

# Update .env
sed -i '' 's/KEYCLOAK_ADMIN_PASSWORD=.*/KEYCLOAK_ADMIN_PASSWORD=NEW_PASSWORD/' .env
```

---

## 👥 Default Users (from Realm Import)

| Username | Email | Roles | Default Password |
|----------|-------|-------|------------------|
| `super_admin` | admin@supervity.ai | admin, user | *(set manually)* |
| `super_user` | user@supervity.ai | user | *(set manually)* |
| `mohit@supervity.ai` | mohit@supervity.ai | - | *(set manually)* |

### Set User Password via Admin Console

1. Go to **supervity** realm → **Users**
2. Click on user → **Credentials** tab
3. Click **Set password** → Enter password → **Temporary = OFF**
4. **Save**

### Set User Password via API

```bash
# Get admin token
TOKEN=$(curl -s -X POST "https://YOUR_KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" -d "username=admin" -d "password=admin" \
  -d "grant_type=password" | jq -r '.access_token')

# Get user ID
USER_ID=$(curl -s "https://YOUR_KEYCLOAK_URL/admin/realms/supervity/users?email=user@example.com" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

# Set password
curl -X PUT "https://YOUR_KEYCLOAK_URL/admin/realms/supervity/users/$USER_ID/reset-password" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type": "password", "value": "NewPassword123!", "temporary": false}'
```

---

## 🎨 Custom Theme (Supervity Branding)

The custom theme replaces Keycloak branding with Supervity branding on:
- ✅ Login page
- ✅ Registration page
- ✅ Account management
- ❌ Admin Console (still shows Keycloak - admins only)

### Theme Files

- `themes/supervity/login/theme.properties` - Theme configuration
- `themes/supervity/login/resources/css/styles.css` - Custom CSS
- `themes/supervity/login/messages/messages_en.properties` - Custom text

### Customizing the Theme

1. Edit files in `themes/supervity/`
2. Rebuild and redeploy:
   ```bash
   ./deployment/deploy-keycloak.sh build
   ./deployment/deploy-keycloak.sh deploy
   ```

---

## 🔧 Client Configuration

### Application Client

| Setting | Value |
|---------|-------|
| **Client ID** | `super-client-dnh-dev-0001` |
| **Client Secret** | `supervity-witty` |
| **Valid Redirect URIs** | `http://localhost:3001/*` |
| **Web Origins** | `http://localhost:3001` |

### Adding Production Redirect URIs

1. Go to **supervity** realm → **Clients** → `super-client-dnh-dev-0001`
2. Add to **Valid redirect URIs**: `https://your-production-url/*`
3. Add to **Web origins**: `https://your-production-url`
4. **Save**

---

## 📧 Email Configuration (Optional)

### SMTP Settings

1. Go to **Realm settings** → **Email** tab
2. Configure:

| Field | Value |
|-------|-------|
| Host | `smtp.office365.com` |
| Port | `587` |
| Enable SSL | OFF |
| Enable StartTLS | ON |
| Authentication | Enabled |
| Username | `your-email@domain.com` |
| Password | Your password or App Password |

3. **Save** → **Test connection**

### Disable Email Verification

If SMTP isn't configured:
1. **Realm settings** → **Login** tab
2. Set **Verify email** = OFF
3. **Save**

---

## 🔄 Common Operations

### View Keycloak Logs

```bash
./deployment/deploy-keycloak.sh logs
# or
gcloud run logs read --service=supervity-keycloak --region=us-central1 --limit=100
```

### Check Deployment Status

```bash
./deployment/deploy-keycloak.sh status
# or
gcloud run services describe supervity-keycloak --region=us-central1
```

### Update Realm Configuration

1. Export realm from Keycloak Admin Console (or edit `supervity-realm.json`)
2. Rebuild and redeploy:
   ```bash
   ./deployment/deploy-keycloak.sh build
   ./deployment/deploy-keycloak.sh deploy
   ```

**Note:** Realm import only creates new objects; it doesn't update existing ones.
To apply changes to existing objects, reset the database first.

---

## 🌐 URLs Reference

| Environment | Keycloak URL |
|-------------|-------------|
| **Production** | `https://supervity-keycloak-{PROJECT_NUMBER}.{REGION}.run.app` |
| **Current** | `https://supervity-keycloak-67689851625.us-central1.run.app` |

### Important Endpoints

| Endpoint | Description |
|----------|-------------|
| `/admin` | Admin Console |
| `/realms/supervity` | Supervity Realm |
| `/realms/supervity/account` | User Account Management |
| `/realms/supervity/.well-known/openid-configuration` | OIDC Discovery |
| `/health/ready` | Health Check |

---

## 🛠️ Troubleshooting

### Admin Login Failed

```bash
# Check if password matches env var
gcloud run services describe supervity-keycloak --region=us-central1 --format='json' | \
  jq '.spec.template.spec.containers[0].env[] | select(.name=="KEYCLOAK_ADMIN_PASSWORD")'
```

If database has old password, reset database (see above).

### Service Not Starting

```bash
# Check logs for errors
gcloud run logs read --service=supervity-keycloak --region=us-central1 --limit=50

# Common issues:
# - Database connection failed: Check Cloud SQL IP authorization
# - Port binding: Ensure KC_HTTP_PORT=8080
```

### Database Connection Issues

```bash
# Verify authorized networks include 0.0.0.0/0
gcloud sql instances describe supervity-keycloak-db --format='yaml' | grep -A5 authorizedNetworks
```

---

## 🏢 Multi-Tenant Realm Management

The Keycloak instance supports multiple realms for different clients/tenants. Each realm provides complete isolation of users, roles, and clients.

### Creating a New Realm for a Client

Use the realm management script to add new realms:

```bash
# Create a new realm for a client
./scripts/keycloak-realm.sh create \
  --realm "acme-corp" \
  --client-id "acme-app" \
  --admin-email "admin@acme.com" \
  --redirect-uris "http://localhost:3001/*,https://acme.example.com/*"
```

This creates:
- A new realm with Supervity branding
- An OAuth client with the specified redirect URIs
- Admin, user, and pending roles
- An admin user (if email provided) with temporary password

### Realm Management Commands

```bash
# List all realms
./scripts/keycloak-realm.sh list

# Show realm details
./scripts/keycloak-realm.sh info --realm acme-corp

# Export realm configuration
./scripts/keycloak-realm.sh export --realm acme-corp --output acme-realm.json

# Delete a realm (dangerous - requires confirmation)
./scripts/keycloak-realm.sh delete --realm acme-corp --confirm
```

### What Each New Realm Gets

| Feature | Value |
|---------|-------|
| **Supervity Theme** | Custom login branding |
| **Registration** | Disabled (managed by app) |
| **Realm Roles** | `admin`, `user`, `pending` |
| **OAuth Client** | PKCE-enabled, confidential client |
| **Password Reset** | Enabled |

### Connecting a New Client Project

After creating a realm, update the client project's `.env`:

```env
KEYCLOAK_SERVER_URL=https://supervity-keycloak-67689851625.us-central1.run.app
KEYCLOAK_REALM=acme-corp
KEYCLOAK_CLIENT_ID=acme-app
KEYCLOAK_CLIENT_SECRET=<generated-secret>
```

### Managing Users Across Realms

Each realm has independent users. To manage users:

1. **Admin Console**: Login at `/admin` → Select realm from dropdown
2. **Admin API**: Authenticate against master realm, then call `/admin/realms/{realm}/users`
3. **In-App**: Each realm's users are managed via the app's Admin Panel (at `/admin/users`)

---

## 🔐 Admin Panel Features

The Supervity template includes a comprehensive admin panel for user management.

### User Actions

| Action | Description |
|--------|-------------|
| **Approve** | Change pending user to approved (user role) |
| **Reject** | Disable pending user's account |
| **Make Admin** | Grant admin privileges |
| **Remove Admin** | Revoke admin privileges |
| **Revoke Access** | Disable user account (preserve data) |
| **Restore Access** | Re-enable disabled account |
| **Delete** | Permanently remove user |

### Bulk Operations

| Action | Description |
|--------|-------------|
| **Delete by Domain** | Remove all users from @example.com |
| **Revoke by Domain** | Disable all users from @example.com |
| **Reset All Users** | Delete all non-admin users (dangerous) |

### Admin Settings

Access at `/admin/settings` to configure:
- **Approved Email Domains**: Users from these domains get instant access
- Other domains require admin approval

---

## 📚 Related Documentation

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)
