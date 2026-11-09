#!/usr/bin/env python3
"""
Digest generation script using gitingest.
Development utility for creating code digests.
"""

import logging
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def generate_digest_cli(
    source, output_file="digest.txt", exclude_exts=None, is_frontend=False
):
    cmd = ["gitingest", source, "-o", output_file]

    # Frontend-specific exclusions when processing frontend folder
    if is_frontend:
        exclusions = [
            # Build and cache directories
            "node_modules",
            "node_modules/*",
            ".next",
            ".next/*",
            "out",
            "build",
            "dist",
            ".cache",
            # Generated files
            "package-lock.json",
            "yarn.lock",
            ".tsbuildinfo",
            "*.tsbuildinfo",
            # Test and coverage
            "coverage",
            "__tests__/coverage",
            ".nyc_output",
            # Static assets
            "public/images",
            "public/fonts",
            "public/*.ico",
            "public/*.png",
            "public/*.svg",
            # IDE and system files
            ".vscode",
            ".idea",
            ".DS_Store",
            # Storybook
            "storybook-static",
            ".storybook-build",
            # Environment files
            ".env",
            ".env.*",
            # Temporary files
            "*.log",
            "npm-debug.log*",
            "yarn-debug.log*",
            "yarn-error.log*",
        ]
    else:
        # Default exclusions for non-frontend directories
        exclusions = [
            # Project-specific directories
            "ai_ap_manager",
            "ai_ap_manager/*",
            "invoices",
            "processed_documents",
            "sample_data",
            "sample_data/*",
            "sample_data/**",
            "sample_data/invoices",
            "sample_data/invoices/*",
            "sample_data/invoices/**",
            "sample_data/demo_inoices",
            "sample_data/demo_inoices/*",
            "sample_data/demo_inoices/**",
            "sample_data/GRNs",
            "sample_data/GRNs/*",
            "sample_data/GRNs/**",
            "sample_data/POs",
            "sample_data/POs/*",
            "sample_data/POs/**",
            "sample_data/pdf_templates.py",
            # Generated documents and output files
            "generated_documents",
            "generated_documents/*",
            "generated_documents/**",
            "*.pdf",
            "REGEN_*.pdf",
            # Database export files
            "database_export",
            "database_export/*",
            "database_export/**",
            "database_export/csv",
            "database_export/csv/*",
            "database_export/json",
            "database_export/json/*",
            "ap_database_master.csv",
            "ap_database_master.json",
            "database_summary.txt",
            "export_summary.json",
            "alembic",
            "alembic/*",
            "alembic/**",
            "alembic.ini",
            "alembic.ini/*",
            "alembic.ini/**",
            "scripts/",
            "scripts/alembic/*",
            "scripts/alembic/**",
            "scripts/alembic.ini",
            "scripts/alembic.ini/*",
            "scripts/alembic.ini/**",
            "alembic.ini.py",
            # Token usage and monitoring files
            "token_usage",
            "token_usage/*",
            "token_usage/**",
            "job_*.json",
            "jobs_summary.json",
            # Script conversion and processing files
            "scripts/converted",
            "scripts/converted/*",
            "scripts/converted/**",
            "scripts/to_convert",
            "scripts/to_convert/*",
            "scripts/to_convert/**",
            "scripts/to_convert/processed",
            "scripts/to_convert/processed/*",
            "scripts/to_convert/processed/**",
            # Utility and setup scripts (non-core business logic)
            "scripts/data_generator.py",
            "scripts/file_converter.py",
            "scripts/verify_test_data.py",
            "export_database.py",
            "make_ingest.py",
            "run_fresh.py",
            "run.py",
            "start_gunicorn.sh",
            # Database files
            "*.sqlite3",
            "*.sqlite",
            "ap_data.db",
            "chroma.sqlite3",
            # Python-related
            "__pycache__",
            "__pycache__/*",
            "*/__pycache__",
            "*/__pycache__/*",
            "**/__pycache__/**",
            "*.pyc",
            "*.pyo",
            "*.egg-info",
            ".pytest_cache",
            "venv",
            "venv/*",
            ".venv",
            "env",
            ".env",
            # Poetry and dependency management
            "poetry.lock",
            "*/poetry.lock",
            "ai_ap_manager/*/poetry.lock",
            # Database and vector store files (ai_ap_manager specific)
            "chroma_db",
            "chroma_db/*",
            "*/chroma_db",
            "*/chroma_db/*",
            "**/chroma_db/**",
            "ai_ap_manager/*/chroma_db",
            "ai_ap_manager/*/chroma_db/*",
            # Binary data files (vector store related)
            "*.bin",
            "data_level0.bin",
            "ai_ap_manager/",
            "ai_ap_manager/*",
            "header.bin",
            "length.bin",
            "link_lists.bin",
            # Version control
            ".git",
            ".gitignore",
            # System files
            ".DS_Store",
            "Thumbs.db",
            "desktop.ini",
            # Build and distribution
            "build",
            "dist",
            "*.egg",
            # Logs and temporary files
            "*.log",
            "*.tmp",
            "*.temp",
            "logs",
            # Documentation and media files
            "*.doc",
            "*.docx",
            "*.xls",
            "*.xlsx",
            "*.ppt",
            "*.pptx",
            "*.png",
            "*.jpg",
            "*.jpeg",
            "*.gif",
            "DOCKER_GUIDE.md",
            "FEATURES.md",
            "*.svg",
            "*.ico",
            "favicon.png",
            "favicon.ico",
            # IDE and editor files
            ".vscode",
            ".idea",
            "*.swp",
            "*.swo",
            # Node.js and React/Next.js related - more comprehensive exclusions
            "node_modules",
            "node_modules/*",
            "*/node_modules",
            "*/node_modules/*",
            "**/node_modules/**",
            "frontend/node_modules",
            "frontend/node_modules/*",
            "frontend/package-lock.json",
            "frontend/yarn.lock",
            "frontend/.next",
            "frontend/.next/*",
            "frontend/.next/**",
            "frontend/public",
            "frontend/public/*",
            "frontend/public/**",
            "frontend/.nuxt",
            "frontend/.nuxt/*",
            "frontend/out",
            "frontend/out/*",
            "frontend/build",
            "frontend/dist",
            "frontend/.cache",
            "frontend/.parcel-cache",
            "frontend/.vercel",
            "frontend/.netlify",
            "frontend/coverage",
            "frontend/.nyc_output",
            "frontend/.storybook-build",
            "frontend/storybook-static",
            "frontend/.turbo",
            "frontend/.swc",
            "frontend/.tsbuildinfo",
            "frontend/*.tsbuildinfo",
            "frontend/copy-pdf-worker.js",
            "frontend/next-env.d.ts",
            "npm-debug.log",
            "yarn-error.log",
            "package-lock.json",
            "yarn.lock",
            ".next",
            ".next/*",
            ".next/**",
            ".nuxt",
            ".nuxt/*",
            "out",
            "out/*",
            "build",
            "dist",
            ".cache",
            ".parcel-cache",
            ".vercel",
            ".netlify",
            "coverage",
            ".nyc_output",
            ".storybook-build",
            "storybook-static",
            ".turbo",
            ".swc",
            ".tsbuildinfo",
            "*.tsbuildinfo",
            # Frontend build artifacts and static files
            "build-manifest.json",
            "app-build-manifest.json",
            "fallback-build-manifest.json",
            "next-minimal-server.js.nft.json",
            "next-server.js.nft.json",
            "export-marker.json",
            "images-manifest.json",
            "prerender-manifest.json",
            "routes-manifest.json",
            "required-server-files.json",
            "app-path-routes-manifest.json",
            "react-loadable-manifest.json",
            "BUILD_ID",
            "trace",
            "transform.js",
            "transform.js.map",
            "pdf.worker.mjs",
            "pdf.worker.min.mjs",
            "logo.svg",
            "logo-dark.svg",
            # Archives
            "*.zip",
            "*.tar",
            "*.tar.gz",
            "*.rar",
            "*.7z",
            # CSV and data files (non-core)
            "*.csv",
            "grns.csv",
            "pos.json",
            "GRN_Header.csv",
            "GRN_LineItem.csv",
            "PO_Header.csv",
            "PO_LineItem.csv",
            "QC_RangIndia.csv",
            "QC_mahawat.pdf",
            "contract_*.pdf",
            "invoice_*.pdf",
            "Sindri*.pdf",
        ]

    if exclude_exts:
        # Format extensions as "*.ext" and add to exclusions
        exclusions.extend(f"*{ext}" for ext in exclude_exts)

    if is_frontend:
        # Include only relevant frontend code files
        include_patterns = [
            "*.tsx",
            "*.ts",
            "*.jsx",
            "*.js",
            "*.css",
            "*.scss",
            "*.sass",
            "*.less",
            "*.module.css",
            "*.module.scss",
            "*.module.sass",
            "*.module.less",
            "*.json",  # For configuration files
            "*.html",
            "*.md",  # For documentation
        ]
        cmd += ["-i", ",".join(include_patterns)]

    if exclusions:
        patterns = ",".join(exclusions)
        cmd += ["-e", patterns]

    log.info(f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        log.info(f"✅ Digest written to {output_file}")
    except subprocess.CalledProcessError as e:
        log.error(f"❌ Error during gitingest execution: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log.error(
            "Usage: python make_ingest.py <path_or_url> [output_file] [--frontend] [excluded_exts...]"
        )
        sys.exit(1)

    source = sys.argv[1]
    output_file = "digest.txt"
    exclude_exts = []
    is_frontend = False

    # Process arguments
    args = sys.argv[2:]
    while args:
        arg = args.pop(0)
        if arg == "--frontend":
            is_frontend = True
        elif arg.startswith("."):
            exclude_exts.append(arg)
        else:
            output_file = arg

    # Check if the source path contains 'frontend' and automatically set is_frontend
    if not is_frontend and (
        "frontend" in source.lower() or "front-end" in source.lower()
    ):
        is_frontend = True
        log.info("Detected frontend directory, using frontend-specific processing...")

    generate_digest_cli(source, output_file, exclude_exts, is_frontend)
