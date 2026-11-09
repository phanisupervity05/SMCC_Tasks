#!/usr/bin/env python3
"""
Database seeding script.
Populates the database with initial sample data.
Used by the seed-db Cloud Run Job.
"""

import logging
import os
import sys

# Configure logging for scripts
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.models.item import Item

# Create a new session for this script
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_data():
    """Populates the database with initial data."""
    db = SessionLocal()
    try:
        log.info("Seeding initial data...")

        # Check if items already exist
        if db.query(Item).count() == 0:
            log.info("Adding sample items...")
            item1 = Item(
                name="First Sample Item",
                description="This is a test item from the seeder.",
            )
            item2 = Item(
                name="Second Sample Item",
                description="Another test item for demonstration.",
            )
            db.add_all([item1, item2])
            db.commit()
            log.info("Sample items added.")
        else:
            log.info("Items table is not empty, skipping seeding.")

        log.info("✅ Data seeding complete.")

    except Exception as e:
        log.error(f"❌ An error occurred during data seeding: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    log.info("--- Starting Database Seeding ---")
    seed_data()
