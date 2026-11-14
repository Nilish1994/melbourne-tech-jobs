"""Recompute job_skills for every stored job, e.g. after the skill catalog changes.

Runs in batches, one transaction per batch, so it is safe to stop and re-run.
"""
import argparse
import sys
from sqlalchemy import select
from app.db.session import get_engine
from app.models.job import jobs
from app.services.ingestion import replace_skills


def backfill(engine, batch_size=500):
    total, last_id = 0, None
    while True:
        with engine.begin() as conn:
            query = select(jobs.c.id, jobs.c.title, jobs.c.description).order_by(jobs.c.id).limit(batch_size)
            if last_id is not None:
                query = query.where(jobs.c.id > last_id)
            batch = conn.execute(query).mappings().all()
            if not batch:
                return total
            replace_skills(conn, {row["id"]: dict(row) for row in batch})
            total += len(batch)
            last_id = batch[-1]["id"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recompute the skills stored for every job")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 10000:
        parser.error("batch-size must be between 1 and 10000")
    print(f"Recomputed skills for {backfill(get_engine(), args.batch_size)} jobs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
