# AI Command Center - Cloud Deployment

This folder contains everything needed to deploy the AI Command Center to Google Cloud Run.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Google Cloud Run                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │   Frontend   │───▶│   Backend    │───▶│  Cloud SQL           │   │
│  │   (Next.js)  │    │   (FastAPI)  │    │  (PostgreSQL)        │   │
│  └──────────────┘    └──────────────┘    └──────────────────────┘   │
│         │                   │                       │               │
│         │                   │              ┌────────┴────────┐      │
│         │                   └─────────────▶│  Cloud Storage  │      │
│         │                                  │  (GCS)          │      │
│         │                                  └─────────────────┘      │
│         └───────────────────┬──────────────────────────────────────┼──▶ Keycloak (Shared)
│                             │                                       │    supervity-auth
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                     Cloud SQL Connector
                     (Secure Unix Socket)
```

## Prerequisites

1. **Google Cloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Docker** installed and running

3. **GCP Project** with billing enabled

## Quick Start

### 1. Configure Environment

```bash
# Copy the example config
cp deployment/prod.env.example deployment/prod.env

# Edit with your values
nano deployment/prod.env
```

**Key values to set:**
- `PROJECT_ID` - Your GCP project ID
- `DB_PASSWORD` - Strong password for the database
- `NEXTAUTH_SECRET` - Generate with `openssl rand -base64 32`
- `GCS_BUCKET` - Your GCS bucket for file storage
- `GCS_PREFIX` - Folder path within the bucket (e.g., `template-cc/files`)

### 2. First-Time Deployment

```bash
# Make script executable
chmod +x deployment/deploy.sh

# Run complete deployment
./deployment/deploy.sh all
```

This will:
1. Enable required GCP APIs
2. Create Artifact Registry repository
3. Create Cloud SQL database (with SSL required, no public IP access)
4. Create secrets in Secret Manager
5. Build and push Docker images
6. Deploy services to Cloud Run (using Cloud SQL Connector for secure DB access)
7. Auto-run database migrations on first startup

### 3. Update Keycloak Redirect URIs

After deployment, add the frontend URL to Keycloak:

1. Go to: https://supervity-auth-67689851625.us-central1.run.app/admin
2. Login: `admin` / `admin`
3. Switch to **supervity** realm
4. Go to: **Clients** → **super-client-dnh-dev-0001** → **Settings**
5. Add **Valid Redirect URIs:** `https://YOUR-FRONTEND-URL/*`
6. Add **Web Origins:** `https://YOUR-FRONTEND-URL`
7. Save

## Commands Reference

### Initial Deployment
| Command | Description |
|---------|-------------|
| `./deployment/deploy.sh setup` | Create GCP resources (Cloud SQL, Artifact Registry) |
| `./deployment/deploy.sh build` | Build and push Docker images |
| `./deployment/deploy.sh deploy` | Deploy services to Cloud Run |
| `./deployment/deploy.sh all` | Run all phases (first-time deployment) |

### After Code Changes
| Command | Description |
|---------|-------------|
| `./deployment/deploy.sh redeploy` | Rebuild and redeploy ALL services |
| `./deployment/deploy.sh redeploy-backend` | Rebuild and redeploy backend only |
| `./deployment/deploy.sh redeploy-frontend` | Rebuild and redeploy frontend only |

### Database & Storage Management
| Command | Description |
|---------|-------------|
| `./deployment/deploy.sh migrate` | Run Alembic migrations via Cloud Run Job |
| `./deployment/deploy.sh cleanup-db` | Drop ALL tables (⚠️ destroys all data!) |
| `./deployment/deploy.sh cleanup-storage` | Delete ALL files from GCS bucket |
| `./deployment/deploy.sh cleanup-all` | Clean both database AND storage |
| `./deployment/deploy.sh reset-db` | Full reset: clean DB + storage, redeploy backend (auto-migrates) |
| `./deployment/deploy.sh seed-db` | Run seed script (`scripts/seed_db.py`) |

### Utilities
| Command | Description |
|---------|-------------|
| `./deployment/deploy.sh status` | Show deployment status |
| `./deployment/deploy.sh secrets` | Create/update secrets |
| `./deployment/deploy.sh logs` | Show backend logs |
| `./deployment/deploy.sh logs template-cc-frontend` | Show frontend logs |

## Auto-Migration Feature

The backend **automatically runs migrations on every deployment**:

```
🔍 Verifying database connectivity...
✅ Database connected
📄 Running database migrations...
INFO  [alembic.runtime.migration] Running upgrade 07e23125fe28 -> 472384599743, add_status_to_items
✅ Migrations up to date!
🏭 Starting production server with dynamic workers...
```

**How it works:**
1. On startup, the backend verifies database connectivity
2. Runs `alembic upgrade head` - this is **idempotent** (only runs pending migrations)
3. Starts production server with dynamic workers

**This means:**
- **New migrations run automatically** on every redeploy - no manual intervention
- **Safe for production** - Alembic only runs migrations that haven't been applied
- **No downtime** - migrations run before workers start (with `preload_app=True`)
- **Multiple instances safe** - first instance runs migrations, others just start

## Creating New Migrations

```bash
# Create a new migration locally
alembic revision -m "description_of_change"

# Edit the migration file in alembic/versions/

# Rebuild and redeploy - migration will auto-run
./deployment/deploy.sh redeploy-backend
```

For an empty database (after `cleanup-db` or `reset-db`), migrations run automatically.
For incremental migrations on existing data, use:
```bash
./deployment/deploy.sh migrate
```

## Configuration Reference

### prod.env Variables

```bash
# GCP Project
PROJECT_ID=your-project-id           # Your GCP project
REGION=us-central1                   # Cloud Run region
REPO_NAME=template-deployment        # Artifact Registry repository name

# Service Names
BACKEND_SERVICE=template-cc-backend   # Backend Cloud Run service name
FRONTEND_SERVICE=template-cc-frontend # Frontend Cloud Run service name

# Database
DB_INSTANCE_NAME=template-cc-db       # Cloud SQL instance name
DB_NAME=template_cc_app               # Database name
DB_USER=postgres                      # Database user
DB_PASSWORD=xxx                       # Database password (use strong password!)

# Cloud Storage
GCS_BUCKET=your-bucket-name           # GCS bucket for file uploads
GCS_PREFIX=template-cc/files          # Folder path within bucket

# Keycloak (shared instance)
KEYCLOAK_SERVER_URL=https://supervity-auth-67689851625.us-central1.run.app
KEYCLOAK_REALM=supervity
KEYCLOAK_CLIENT_ID=super-client-dnh-dev-0001
KEYCLOAK_CLIENT_SECRET=supervity-witty   # ⚠️ Do NOT regenerate!

# NextAuth
NEXTAUTH_SECRET=xxx                   # Generate with: openssl rand -base64 32

# Resource Limits
BACKEND_MEMORY=1Gi
BACKEND_CPU=1
FRONTEND_MEMORY=512Mi
FRONTEND_CPU=1

# Worker Configuration (optional)
# WEB_CONCURRENCY=4                   # Override auto-calculated workers
# GUNICORN_TIMEOUT=120                # Request timeout in seconds
```

### Secret Manager

The following secrets are stored in Secret Manager:
| Secret Name | Description |
|-------------|-------------|
| `template-cc-database-url` | PostgreSQL connection string (Cloud SQL Connector format) |
| `template-cc-keycloak-secret` | Keycloak client secret |
| `template-cc-nextauth-secret` | NextAuth.js secret |

## Database Security

The Cloud SQL database is configured with **maximum security**:

1. **No public IP access** - Uses Cloud SQL Connector (Unix socket)
2. **SSL required** - All connections must use SSL
3. **IAM authentication** - Cloud Run service account has `cloudsql.client` role

Connection format (used by Cloud SQL Connector):
```
postgresql+psycopg2://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
```

## File Storage

**Production (GCS):**
- Files stored in Google Cloud Storage
- Configurable bucket and prefix
- Backend service account has `storage.objectAdmin` role

**Local Development (Docker):**
- Files stored in Docker volume (`document_storage`)
- Mounted to `/app/document_storage`

Toggle via environment:
```bash
# Production (default when APP_ENV=production)
STORAGE_BACKEND=gcs
GCS_BUCKET=your-bucket
GCS_PREFIX=your-folder

# Development
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=/app/document_storage
```

## Worker Configuration

The backend automatically scales workers based on CPU cores:

```python
workers = (2 * cpu_count) + 1
```

Override with `WEB_CONCURRENCY` environment variable:
```bash
WEB_CONCURRENCY=4  # Force 4 workers
```

**Features:**
- `preload_app=True` - Shares memory between workers
- Graceful shutdown handling
- Dynamic scaling based on Cloud Run instance size

## Costs

Estimated monthly costs (with minimal traffic):
- **Cloud Run**: ~$0-10 (pay per use, min-instances=0)
- **Cloud SQL** (db-g1-small): ~$30-50
- **Artifact Registry**: ~$0.10 per GB stored
- **Secret Manager**: ~$0.06 per secret version
- **Cloud Storage**: ~$0.02 per GB stored

**Tip**: Set `BACKEND_MIN_INSTANCES=0` and `FRONTEND_MIN_INSTANCES=0` to minimize costs during development.

## Troubleshooting

### "Permission denied" on deploy.sh
```bash
chmod +x deployment/deploy.sh
```

### Database connection issues
1. Check Cloud SQL is running:
   ```bash
   ./deployment/deploy.sh status
   ```
2. Verify Cloud SQL Connector is configured:
   ```bash
   gcloud run services describe template-cc-backend --region=us-central1 \
     --format="value(spec.template.metadata.annotations.'run.googleapis.com/cloudsql-instances')"
   ```
3. Check secrets are configured:
   ```bash
   gcloud secrets list
   ```

### Frontend can't reach backend
1. Check CORS is configured with frontend URL
2. Verify `NEXT_PUBLIC_API_URL` is correct in frontend env
3. Check backend logs:
   ```bash
   ./deployment/deploy.sh logs template-cc-backend
   ```

### Authentication not working
1. Verify Keycloak redirect URIs are set correctly
2. Check frontend is using correct Keycloak URL
3. Verify client secret matches (`supervity-witty`)
4. Check for token expiration issues in browser console

### Migrations not running
1. Check if database is truly empty:
   ```bash
   ./deployment/deploy.sh logs template-cc-backend | grep -i migration
   ```
2. Force migration via job:
   ```bash
   ./deployment/deploy.sh migrate
   ```
3. Check migration files are included in Docker image

### Files not uploading
1. Verify GCS bucket exists and is accessible
2. Check service account has `storage.objectAdmin` role:
   ```bash
   gcloud projects get-iam-policy PROJECT_ID --flatten="bindings[].members" \
     --filter="bindings.members:SERVICE_ACCOUNT"
   ```

## Security Notes

1. **Secrets**: All sensitive values are stored in Secret Manager
2. **Database**: Uses Cloud SQL Connector - no public network access
3. **SSL**: Required for all database connections
4. **Keycloak**: The shared instance uses fixed credentials - do NOT regenerate client secret
5. **HTTPS**: Cloud Run automatically provides SSL certificates
6. **IAM**: Cloud Run services use default compute service account

## Clean Up

To remove all deployed resources:

```bash
# Delete Cloud Run services
gcloud run services delete template-cc-backend --region=us-central1 --quiet
gcloud run services delete template-cc-frontend --region=us-central1 --quiet

# Delete Cloud Run jobs
gcloud run jobs delete cleanup-db --region=us-central1 --quiet
gcloud run jobs delete migrate-db --region=us-central1 --quiet
gcloud run jobs delete seed-db --region=us-central1 --quiet

# Delete Cloud SQL (WARNING: deletes all data!)
gcloud sql instances delete template-cc-db --quiet

# Delete secrets
gcloud secrets delete template-cc-database-url --quiet
gcloud secrets delete template-cc-keycloak-secret --quiet
gcloud secrets delete template-cc-nextauth-secret --quiet

# Delete GCS files (optional)
gsutil rm -r gs://YOUR_BUCKET/template-cc/files/

# Delete Artifact Registry images (optional)
gcloud artifacts repositories delete template-deployment --location=us-central1 --quiet
```
