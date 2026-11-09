# Supervity AI Command Center - Full-Stack Template

A production-ready template for building modern, AI-first web applications with Python/FastAPI backend, Next.js/React frontend, Keycloak for identity management, and integrated Supervity AI features.

---

## 🚨 For New Client Projects - Read This First!

When starting a new project from this template, you need to understand what's **real functionality** vs **demo/placeholder**:

### What's Real (Production-Ready)

| Component | Description |
|-----------|-------------|
| **Authentication** | Full OAuth2/OIDC flow with Keycloak |
| **Authorization Engine** | JSON-based RBAC/ABAC policy system |
| **User Registration** | Self-registration with domain-based approval |
| **Admin User Management** | `/admin/users` - Approve/reject pending users |
| **Audit Logging** | `/admin/audit` - Automatic + custom event logging with export |
| **AI Policies** | `/ai/policies` - Natural language rule engine with DSL translation |
| **AI Insights** | `/ai/insights` - Proactive batch analysis and recommendations |
| **AI Manager** | Global chatbot modal - Agentic assistant with tool execution |
| **Database Setup** | PostgreSQL with Alembic migrations |
| **API Structure** | FastAPI with dependency injection |
| **Session Management** | NextAuth.js with token refresh |

### What's Demo (Replace for Production)

| Page | Location | Action Required |
|------|----------|-----------------|
| **Dashboard** | `/` (page.tsx) | Replace mock stats with real data |
| **Workbench** | `/workbench` | Add your actual AI tools/features |
| **Settings** | `/settings` | Implement real settings functionality |
| **Brand & Design** | `/brand` | **Remove from sidebar** (internal reference only) |

---

## ✨ Core Features

- **Production-Ready Stack:** FastAPI, Next.js, PostgreSQL, and Keycloak
- **Supervity AI Integration:** Policies, Insights, and AI Manager with Gemini
- **Pluggable Authorization Engine:** Complex access control rules in JSON
- **User Self-Registration:** With domain-based auto-approval or admin approval
- **Custom Keycloak Theme:** Branded login/registration pages
- **Comprehensive Audit Logging:** Automatic request logging + custom business events
- **Fully Containerized:** Docker and Docker Compose
- **Cloud-Ready:** Deploys to Google Cloud Run with Cloud SQL

---

## 💻 Technology Stack

| Area | Technology | Purpose |
|------|------------|---------|
| Backend | **Python 3.11** + **FastAPI** | High-performance API |
| Frontend | **Next.js 15** + **React 19** + **TypeScript** | Modern UI framework |
| AI | **Gemini API** (Supervity AI) | Policies, Insights, Chatbot |
| Identity | **Keycloak 24** on **Google Cloud Run** | Centralized IAM |
| Database | **PostgreSQL 15** | Application data |
| DevOps | **Docker** + **Docker Compose** | Containerization |

---

## 🚀 Quick Start

Get the Supervity AI Command Center running locally in under 5 minutes.

### Prerequisites

| Tool | Required | Purpose |
|------|----------|---------|
| [Docker Desktop](https://www.docker.com/get-started) | ✅ Yes | Runs all services |
| `make` | ✅ Yes | Dev commands (built-in on macOS/Linux) |
| [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) | ❌ Optional | For cloud deployment |

### Step 1: Clone & Setup

```bash
# Clone the repository
git clone https://github.com/your-org/your-repo.git
cd your-repo

# Create your environment file
cp .env.example .env
```

### Step 2: Configure Secrets

Edit `.env` and set these required values:

```bash
# REQUIRED: Generate and paste this secret
openssl rand -base64 32
# Copy the output and set: NEXTAUTH_SECRET=<paste-here>

# OPTIONAL but RECOMMENDED: Enable AI features
# Get your API key from: https://aistudio.google.com/apikey
GEMINI_API_KEY=your-api-key-here
```

### Step 3: Start Everything

```bash
make up
```

This starts PostgreSQL, Backend (FastAPI), and Frontend (Next.js).

### Step 4: Access the App

| Service | URL | Description |
|---------|-----|-------------|
| 🌐 **Frontend** | http://localhost:3001 | Main application |
| 📡 **Backend API** | http://localhost:8001/docs | Swagger API docs |
| 🔐 **Keycloak Admin** | [Cloud Console](https://supervity-keycloak-67689851625.us-central1.run.app/admin) | Identity management |

### Useful Commands

```bash
make up          # Start all services
make down        # Stop all services
make logs-be     # View backend logs
make logs-fe     # View frontend logs
make restart-be  # Restart backend only
```

### Troubleshooting Quick Start

| Issue | Solution |
|-------|----------|
| Port 3001/8001 in use | Stop other services or change ports in `.env` |
| OAuth error on login | Clear cookies or use incognito mode |
| AI features not working | Check `GEMINI_API_KEY` is set in `.env` |
| Containers won't start | Run `docker compose down -v` then `make up` |

---

## 📂 Project Structure

```
.
├── app/                      # FastAPI Backend
│   ├── main.py              # API routes and endpoints
│   ├── security.py          # Auth/token validation
│   ├── authz.py             # Authorization engine
│   ├── authz.map.json       # Authorization rules (EDIT THIS)
│   ├── public.map.json      # Public endpoints list
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas
│   │   └── ai.py            # AI feature schemas
│   ├── routers/
│   │   └── ai.py            # AI endpoints (policies, insights, chat)
│   ├── services/
│   │   ├── ai/              # AI services
│   │   │   ├── chat.py      # AI Manager chat logic
│   │   │   ├── gemini.py    # Gemini API client
│   │   │   ├── policy.py    # Policy translation
│   │   │   └── tools.py     # AI function tools
│   │   └── keycloak_admin.py  # Keycloak Admin API client
│   └── core/
│       ├── database.py      # DB connection
│       └── storage.py       # File storage abstraction
│
├── frontend/                 # Next.js Frontend
│   └── src/
│       ├── app/             # App Router pages
│       │   ├── ai/          # AI feature pages
│       │   │   ├── policies/  # AI Policies page
│       │   │   └── insights/  # AI Insights page
│       │   ├── admin/       # Admin pages
│       │   └── auth/        # Auth pages
│       ├── components/
│       │   ├── ai/          # AI components
│       │   │   ├── AIManager.tsx    # Global chatbot modal
│       │   │   ├── policies/        # Policy components
│       │   │   └── insights/        # Insight components
│       │   ├── layout/      # Header, Sidebar, etc.
│       │   ├── ui/          # Reusable UI components
│       │   └── brand/       # Logo and branding components
│       ├── context/
│       │   └── AIContext.tsx  # Global AI state
│       ├── lib/
│       │   ├── api-client.ts  # Backend API client
│       │   └── utils.ts
│       └── middleware.ts    # Auth middleware
│
├── alembic/                 # Database migrations
├── keycloak/                # Keycloak Configuration
├── deployment/              # Deployment scripts
├── docker-compose.yml       # Local development
├── Makefile                 # Dev commands
└── .env.example             # Environment template
```

---

## 📝 Environment Variables

The `.env` file is organized into **Backend** and **Frontend** sections.

### Backend Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | Environment mode: `development` or `production` |
| `LOG_LEVEL` | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |
| `DATABASE_URL` | (composed) | PostgreSQL connection string |
| `STORAGE_BACKEND` | `local` | File storage: `local` or `gcs` |
| `GEMINI_API_KEY` | (empty) | API key for Supervity AI features |
| `AI_MODEL` | `gemini-2.5-flash` | AI model to use |

#### Backend Environment Modes (`APP_ENV`)

| Value | Workers | Hot Reload | Timeout | Use Case |
|-------|---------|------------|---------|----------|
| `development` | 1 | ✅ Yes | 5000s | Local development |
| `production` | (2 × CPUs) + 1 | ❌ No | 120s | Production deployment |

### Frontend Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ENV` | `development` | Next.js environment mode |
| `FRONTEND_TARGET` | `prod` | Docker build target: `dev` or `prod` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8001` | Backend API URL (browser) |
| `NEXT_PUBLIC_BASE_PATH` | (empty) | Base path for reverse proxy |
| `NEXTAUTH_SECRET` | (required) | Secret for NextAuth.js tokens |

#### Frontend Build Targets (`FRONTEND_TARGET`)

| Value | Command | Hot Reload | Use Case |
|-------|---------|------------|----------|
| `dev` | `npm run dev` | ✅ Yes | Frontend development |
| `prod` | `npm start` | ❌ No | Production/staging |

### Authentication (Keycloak)

| Variable | Description |
|----------|-------------|
| `KEYCLOAK_SERVER_URL` | Keycloak server URL |
| `KEYCLOAK_REALM` | Realm name |
| `KEYCLOAK_CLIENT_ID` | OAuth client ID |
| `KEYCLOAK_CLIENT_SECRET` | OAuth client secret |
| `APPROVED_EMAIL_DOMAINS` | Domains for auto-approval (comma-separated) |

---

## 🤖 AI Features

### AI Policies (`/ai/policies`)

Define business rules in natural language. The AI translates them into executable logic.

**Features:**
- Natural language rule input
- Automatic translation to logical DSL
- Support for both logical (DSL) and natural language policies
- Policy hierarchy with priority ordering
- Conflict detection and resolution

**Demo policies included:** Finance, HR, IT, Procurement, Security use cases

### AI Insights (`/ai/insights`)

Proactive analysis and recommendations based on system data.

**Features:**
- Automated pattern detection
- Anomaly identification
- Severity-based prioritization (Critical, Warning, Recommendation)
- Suggested actions with estimated impact

### AI Manager (Global Chatbot)

Accessible from any page via the header. Opens as a centered modal with blurred backdrop.

**Features:**
- Context-aware (knows current page)
- Tool execution (function calling)
- Markdown rendering in responses
- Quick action buttons
- Keyboard shortcut: `⌘M`

---

## 🛠️ Make Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services |
| `make down` | Stop all services |
| `make logs-be` | View backend logs |
| `make logs-fe` | View frontend logs |
| `make format` | Format all code |
| `make lint` | Lint all code |
| `make test-be` | Run backend tests |
| `make migrate-up` | Apply database migrations |
| `make migrate-create MSG='...'` | Create new migration |
| `make migrate-history` | View migration history |

---

## 🗄️ Database Migrations

Alembic migrations run automatically on container startup.

```bash
# View current migration status
make migrate-history

# Create a new migration
make migrate-create MSG='add_new_table'

# Apply pending migrations
make migrate-up

# Rollback one migration
make migrate-down
```

### Migration Chain

```
78594ac01b8d (BASE) → 07e23125fe28 → 472384599743 → a1b2c3d4e5f6 → b2c3d4e5f6g7 → c3d4e5f6g7h8 (HEAD)
```

---

## 🔐 Authentication & Authorization

### How It Works

1. **User clicks "Sign In"** → Redirected to Keycloak
2. **Keycloak authenticates** → Returns tokens to frontend
3. **Frontend stores tokens** → NextAuth.js manages session
4. **API calls include token** → Backend validates with Keycloak
5. **Authorization engine checks** → Policies in `authz.map.json`

### Adding Protected Endpoints

```python
# app/routers/your_router.py
@router.get("/api/my-endpoint")
def my_endpoint(user: dict = Depends(get_current_user)):
    return {"message": f"Hello {user['preferred_username']}"}
```

```json
// app/authz.map.json
{
  "/api/my-endpoint": {
    "ANY": ["admin", "user"]
  }
}
```

---

## 📊 Audit Logging System

Comprehensive audit logging with automatic request logging and custom event support.

### What's Automatically Logged

- HTTP method, endpoint, query params
- Request/response bodies (sensitive data masked)
- Response status code and time
- User info (from JWT token)
- Client IP and user agent

### Adding Custom Audit Logs

```python
from app.services.audit import audit

await audit.log_user_action(
    action="user.approve",
    actor=current_user,
    target_user_id=user_id,
    target_user_email="john@example.com",
)
```

📖 **Full documentation**: [docs/Audit System Guide.md](docs/Audit%20System%20Guide.md)

---

## ⚠️ Common Issues

### "OAuth error" when logging in
Clear cookies or use incognito. The app auto-clears stale sessions on error.

### API returns 401
Check that token is being passed. See browser Network tab for Authorization header.

### AI features not working
Ensure `GEMINI_API_KEY` is set in `.env`. Demo data loads even without API key.

### Frontend not updating after code changes
If using `FRONTEND_TARGET=prod`, rebuild with `docker compose build frontend`.

---

## 🏁 Checklist for New Projects

- [ ] Clone template and rename repository
- [ ] Update `.env` with new secrets (especially `NEXTAUTH_SECRET`)
- [ ] Add `GEMINI_API_KEY` for AI features
- [ ] Remove `/brand` page from sidebar
- [ ] Update branding (logo, colors, company name)
- [ ] Configure `APPROVED_EMAIL_DOMAINS`
- [ ] Replace demo pages (Dashboard, Workbench, Settings)
- [ ] Update this README for your project
