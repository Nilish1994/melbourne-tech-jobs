"""Count every attempt, including failed requests, across CLI runs."""
import time
from sqlalchemy import text


class QuotaExceeded(RuntimeError):
    pass


class DatabaseQuota:
    def __init__(self, engine):
        self.engine = engine

    def acquire(self):
        while True:
            with self.engine.begin() as conn:
                # Serialize reservations across all ingestion processes using this DB.
                conn.execute(text("SELECT pg_advisory_xact_lock(73410921)"))
                counts = conn.execute(text("""
                    SELECT
                      count(*) FILTER (WHERE requested_at > clock_timestamp() - interval '1 minute') AS minute,
                      count(*) FILTER (WHERE requested_at > clock_timestamp() - interval '1 day') AS day,
                      count(*) FILTER (WHERE requested_at > clock_timestamp() - interval '7 days') AS week,
                      count(*) AS month,
                      extract(epoch FROM clock_timestamp() - max(requested_at)) AS elapsed
                    FROM adzuna_requests
                    WHERE requested_at > clock_timestamp() - interval '32 days'
                """)).mappings().one()
                for window, limit in (("day", 250), ("week", 1000), ("month", 2500)):
                    if counts[window] >= limit:
                        raise QuotaExceeded(f"Adzuna {window} quota exhausted; try after the rolling window expires")
                wait = max(0, 2.5 - float(counts["elapsed"])) if counts["elapsed"] is not None else 0
                if counts["minute"] >= 25:
                    wait = max(wait, 2.5)
                if wait == 0:
                    conn.execute(text("INSERT INTO adzuna_requests VALUES (clock_timestamp())"))
                    return
            time.sleep(wait)
