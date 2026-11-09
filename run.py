#!/usr/bin/env python3
"""
Main startup script for the Supervity AP Command Center.
This script sets up the path and runs the FastAPI application using uvicorn.
It can run in 'development' (default) or 'production' mode.
"""
import sys
import os
import uvicorn

# Windows consoles default to cp1252, which cannot print the emoji below.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    """Configures path and starts the Uvicorn server."""
    # Add the project root directory to the Python path
    # This allows us to import 'app' as a top-level module
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

    # --- START FIX: Check APP_ENV correctly ---
    # The presence of the variable, not its content, was being checked.
    is_production = os.getenv("APP_ENV", "development").lower() == "production"
    # --- END FIX ---
    host = "0.0.0.0" if is_production else "127.0.0.1"
    # 8001 matches NEXT_PUBLIC_API_URL in .env (Docker maps 8001 -> 8000). Override with PORT.
    port = int(os.getenv("PORT", "8001"))

    print("🚀 Starting Supervity AP Command Center API server...")
    if is_production:
        print("   Mode: Production")
    else:
        print("   Mode: Development (auto-reloading enabled)")

    print(f"API Documentation will be available at: http://{host}:{port}/docs")
    print(f"API Root endpoint: http://{host}:{port}/")
    print("\nPress Ctrl+C to stop the server")

    uvicorn.run(
        "app.main:app",  # The import string for the application
        host=host,
        port=port,
        reload=not is_production,
        reload_dirs=["app"] if not is_production else None,
        log_level="info",
    )


if __name__ == "__main__":
    main()
