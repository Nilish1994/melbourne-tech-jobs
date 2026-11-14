from dataclasses import dataclass
import uuid
from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from app.models.job import jobs
from app.models.job_skill import job_skills
from app.skills.extract import extract_skills
from app.sources.normalise import normalise


@dataclass(frozen=True)
class UpsertCounts:
    inserted: int
    updated: int


def upsert_jobs(conn, records, *, detailed=False):
    # Deduplicate within a page as well as against existing rows.
    unique = {(r["source"], r["source_job_id"]): r for r in records}
    if not unique:
        return UpsertCounts(0, 0) if detailed else 0
    values = [dict(row, id=uuid.uuid4()) for row in unique.values()]
    candidate_ids = {row["id"] for row in values}
    statement = insert(jobs).values(values)
    updates = {key: statement.excluded[key] for key in next(iter(unique.values()))
               if key not in {"id", "source", "source_job_id", "first_seen_at", "last_seen_at"}}
    updates["last_seen_at"] = func.clock_timestamp()
    returned = conn.execute(statement.on_conflict_do_update(
        constraint="uq_jobs_source_job", set_=updates)
        .returning(jobs.c.id, jobs.c.source, jobs.c.source_job_id)).all()
    returned_ids = {row.id for row in returned}
    # Skills follow the latest text, in the same transaction as the job row.
    replace_skills(conn, {row.id: unique[(row.source, row.source_job_id)] for row in returned})
    # Inserts return their proposed UUID; updates return the preserved existing UUID.
    inserted = len(returned_ids & candidate_ids)
    return UpsertCounts(inserted, len(unique) - inserted) if detailed else len(unique)


def replace_skills(conn, records_by_job_id):
    """Store the skills found in each job's title and description, replacing old ones."""
    if not records_by_job_id:
        return 0
    conn.execute(delete(job_skills).where(job_skills.c.job_id.in_(list(records_by_job_id))))
    rows = [{"job_id": job_id, "skill": skill}
            for job_id, record in records_by_job_id.items()
            for skill in extract_skills(record.get("title"), record.get("description"))]
    if rows:
        conn.execute(insert(job_skills).values(rows))
    return len(rows)


def ingest(engine, client, location, max_pages):
    count = 0
    for page in client.pages(location, max_pages):
        records = [normalise(raw) for raw in page]
        with engine.begin() as conn:
            count += upsert_jobs(conn, records)
    return count
