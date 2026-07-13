#!/usr/bin/env python3
"""
M2 migration: add structured-payload columns to question_answers and the
use_widget_assessment flag to lessons.

Columns added:
- question_answers.question_payload   TEXT   (JSON-serialized QuestionPayload)
- question_answers.response_payload   TEXT   (JSON-serialized LearnerResponse)
- question_answers.widget_type        VARCHAR (e.g. "mcq_single")
- question_answers.is_correct         BOOLEAN
- question_answers.concept_tested     VARCHAR (denormalized from payload)
- lessons.use_widget_assessment       BOOLEAN DEFAULT false

All columns are nullable / defaulted so existing chat-path rows remain valid.
Idempotent: safe to re-run; skips columns that already exist.

Run: uv run python scripts/migrate_m2_widget_payload.py
"""
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


QA_COLUMNS = [
    ("question_payload", "TEXT"),
    ("response_payload", "TEXT"),
    ("widget_type",      "VARCHAR(32)"),
    ("is_correct",       "BOOLEAN"),
    ("concept_tested",   "VARCHAR(255)"),
]

LESSON_COLUMNS = [
    ("use_widget_assessment", "BOOLEAN DEFAULT false"),
]


def _existing(conn, table_name):
    result = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :t
    """), {"t": table_name})
    return {row[0] for row in result}


def migrate():
    with engine.connect() as conn:
        for table_name, columns, default_clause in [
            ("question_answers", QA_COLUMNS, True),
            ("lessons", LESSON_COLUMNS, False),
        ]:
            existing = _existing(conn, table_name)
            for col_name, col_type in columns:
                if col_name in existing:
                    logger.info(f"{table_name}.{col_name} already exists")
                    continue
                logger.info(f"Adding {table_name}.{col_name} ({col_type})...")
                conn.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                ))
                conn.commit()
                logger.info(f"✓ Added {table_name}.{col_name}")

    logger.info("M2 migration completed successfully!")


if __name__ == "__main__":
    migrate()