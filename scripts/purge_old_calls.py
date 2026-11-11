#!/usr/bin/env python3
"""
Remove old calls, their results and their stored recordings (data retention).

A DRY RUN by default: it only reports what would be removed. Add --apply to delete.

    python scripts/purge_old_calls.py --days 180            # report only
    python scripts/purge_old_calls.py --days 180 --apply    # delete

--days defaults to the RETENTION_DAYS environment variable. The minimum is 30 days.
Only finished calls ("done" or "failed") are removed; calls in progress are never touched.
Run it from a scheduled job (for example a Cloud Run Job or cron), the same way as cleanup_db.py.
"""

import argparse
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=int(os.getenv("RETENTION_DAYS", "0") or 0))
    parser.add_argument("--apply", action="store_true", help="Delete for real (default is a dry run)")
    args = parser.parse_args()
    if args.days <= 0:
        print("Give --days N or set RETENTION_DAYS. Nothing was done.", file=sys.stderr)
        return 2

    from app.core.database import SessionLocal
    from app.services.retention import MIN_DAYS, purge_old_calls

    if args.days < MIN_DAYS:
        print(f"Retention must be at least {MIN_DAYS} days. Nothing was done.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        summary = asyncio.run(purge_old_calls(db, args.days, apply=args.apply))
    finally:
        db.close()
    print(json.dumps(summary, indent=2))
    if not args.apply:
        print("\nDry run only. Add --apply to delete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
