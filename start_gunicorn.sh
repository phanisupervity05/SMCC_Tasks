#!/bin/sh

# Unified entrypoint script for the application
# Handles both development and production environments
#
# PRODUCTION & DEVELOPMENT:
#   - Always runs migrations on startup (alembic upgrade head)
#   - Alembic is idempotent - only runs pending migrations
#   - Safe with preload_app=True (runs before workers fork)
#
# PRODUCTION:
#   - Multiple workers spawned after migrations
#   - App is preloaded before forking workers
#
# DEVELOPMENT:
#   - Single worker with hot reload
#   - Waits for database to be ready

set -e  # Exit immediately if a command exits with a non-zero status

echo "🚀 Starting application..."
echo "   Environment: ${APP_ENV:-development}"

# Determine which gunicorn config to use based on environment
if [ "${APP_ENV}" = "production" ]; then
    echo "🏭 Production mode detected"
    
    # Verify database connectivity before running migrations
    echo "🔍 Verifying database connectivity..."
    
    set +e  # Temporarily disable exit-on-error
    python -c "
import os
import sys
from urllib.parse import urlparse, parse_qs

database_url = os.getenv('DATABASE_URL', '')
if not database_url:
    print('⚠️  DATABASE_URL not set')
    sys.exit(1)

try:
    import psycopg2
    
    parsed = urlparse(database_url)
    conn_params = {
        'user': parsed.username,
        'password': parsed.password,
        'database': parsed.path.lstrip('/'),
        'connect_timeout': 10
    }
    
    query_params = parse_qs(parsed.query)
    if 'host' in query_params:
        conn_params['host'] = query_params['host'][0]
    elif parsed.hostname:
        conn_params['host'] = parsed.hostname
        conn_params['port'] = str(parsed.port or 5432)
    
    conn = psycopg2.connect(**conn_params)
    conn.close()
    print('✅ Database connected')
    sys.exit(0)
        
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
"
    DB_STATUS=$?
    set -e  # Re-enable exit-on-error
    
    if [ $DB_STATUS -ne 0 ]; then
        echo "❌ Cannot connect to database. Exiting."
        exit 1
    fi
    
    # Always run migrations - Alembic is idempotent
    # It only runs migrations that haven't been applied yet
    echo "📄 Running database migrations..."
    alembic upgrade head
    echo "✅ Migrations up to date!"
    
    echo "🏭 Starting production server with dynamic workers..."
    exec gunicorn -c gunicorn/prod.py app.main:app
    
else
    echo "🛠️  Development mode detected"
    
    # Wait for database to be ready (development only)
    echo "🔍 Waiting for database..."
    python utils/wait_for_db.py
    
    # Run database migrations (safe in dev - single worker)
    echo "📄 Running database migrations..."
    alembic upgrade head
    
    echo "🛠️  Starting development server..."
    exec gunicorn -c gunicorn/dev.py app.main:app
fi
