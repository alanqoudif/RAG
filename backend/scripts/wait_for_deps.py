"""Block until the platform database is reachable. Used by container entrypoints."""

import sys
import time

from sqlalchemy import create_engine, text

from app.config import get_settings


def wait_for_database(max_attempts: int = 30, delay_seconds: float = 2.0) -> bool:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"[wait_for_deps] database reachable after {attempt} attempt(s)")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[wait_for_deps] database not ready (attempt {attempt}/{max_attempts}): {type(exc).__name__}")
            time.sleep(delay_seconds)
    return False


if __name__ == "__main__":
    ok = wait_for_database()
    sys.exit(0 if ok else 1)
