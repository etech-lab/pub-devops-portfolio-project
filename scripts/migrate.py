#!/usr/bin/env python3
from pathlib import Path
import sys


APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from site_test.rds_connection import get_connection


def run_migration() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS websites (
                    id SERIAL PRIMARY KEY,
                    url VARCHAR(2048) NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS test_results (
                    id SERIAL PRIMARY KEY,
                    website_id INTEGER REFERENCES websites(id) ON DELETE CASCADE,
                    status_code INTEGER,
                    response_time_ms INTEGER,
                    date_header VARCHAR(255),
                    server_header VARCHAR(255),
                    content_type VARCHAR(255),
                    content_length VARCHAR(50),
                    last_modified VARCHAR(255),
                    tested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_test_results_website_id
                ON test_results(website_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_test_results_tested_at
                ON test_results(tested_at DESC);
                """
            )

            # Idempotent column additions for pre-existing tables missing columns
            cur.execute(
                """
                ALTER TABLE test_results
                    ADD COLUMN IF NOT EXISTS status_code INTEGER,
                    ADD COLUMN IF NOT EXISTS response_time_ms INTEGER,
                    ADD COLUMN IF NOT EXISTS date_header VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS server_header VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS content_type VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS content_length VARCHAR(50),
                    ADD COLUMN IF NOT EXISTS last_modified VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS tested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
                """
            )

        conn.commit()
        print("Schema migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
