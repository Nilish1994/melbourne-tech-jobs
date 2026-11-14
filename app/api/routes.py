from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, text
from sqlalchemy.exc import SQLAlchemyError
from app.db.session import connection
from app.models.job import jobs
from app.models.job_skill import job_skills

router = APIRouter()
# Adzuna's terms: link to the advert instead of republishing its description.
PRIVATE_COLUMNS = {"raw_payload", "description"}
public_columns = [column for column in jobs.c if column.name not in PRIVATE_COLUMNS]


def attach_skills(conn, items):
    ids = [item["id"] for item in items]
    skills = {}
    if ids:
        for row in conn.execute(select(job_skills.c.job_id, job_skills.c.skill)
                                .where(job_skills.c.job_id.in_(ids)).order_by(job_skills.c.skill)):
            skills.setdefault(row.job_id, []).append(row.skill)
    for item in items:
        item["skills"] = skills.get(item["id"], [])
    return items


@router.get("/health")
def health():
    from app.db.session import get_engine
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM jobs LIMIT 1"))
        return {"status": "ok"}
    except (SQLAlchemyError, ValueError):
        raise HTTPException(503, "Database unavailable or migrations missing") from None


@router.get("/jobs")
def list_jobs(search: str | None = Query(None, min_length=1, max_length=200),
              location: str | None = Query(None, min_length=1, max_length=200),
              skill: str | None = Query(None, min_length=1, max_length=50),
              page: int = Query(1, ge=1, le=100000),
              page_size: int = Query(20, ge=1, le=100), conn=Depends(connection)):
    filters = []
    if search:
        filters.append(or_(jobs.c.title.icontains(search, autoescape=True),
                           jobs.c.description.icontains(search, autoescape=True)))
    if location:
        filters.append(jobs.c.location.icontains(location, autoescape=True))
    if skill:
        filters.append(jobs.c.id.in_(select(job_skills.c.job_id).where(job_skills.c.skill == skill)))
    total = conn.scalar(select(func.count()).select_from(jobs).where(*filters))
    rows = conn.execute(select(*public_columns).where(*filters)
                        .order_by(func.coalesce(jobs.c.posted_at, jobs.c.first_seen_at).desc(), jobs.c.id.desc())
                        .offset((page - 1) * page_size).limit(page_size)).mappings()
    items = attach_skills(conn, [dict(row) for row in rows])
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/jobs/{id}")
def get_job(id: UUID, conn=Depends(connection)):
    row = conn.execute(select(*public_columns).where(jobs.c.id == id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Job not found")
    return attach_skills(conn, [dict(row)])[0]


@router.get("/ingestion-runs")
def list_ingestion_runs(page: int = Query(1, ge=1, le=100000),
                        page_size: int = Query(20, ge=1, le=100), conn=Depends(connection)):
    from app.models.ingestion_run import ingestion_runs as runs
    total = conn.scalar(select(func.count()).select_from(runs))
    rows = conn.execute(select(runs).order_by(runs.c.started_at.desc(), runs.c.id.desc())
                        .offset((page - 1) * page_size).limit(page_size)).mappings()
    return {"items": [dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/ingestion-runs/{id}")
def get_ingestion_run(id: UUID, conn=Depends(connection)):
    from app.models.ingestion_run import ingestion_runs as runs
    row = conn.execute(select(runs).where(runs.c.id == id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Ingestion run not found")
    return dict(row)


@router.get("/stats")
def stats(conn=Depends(connection)):
    from app.models.ingestion_run import ingestion_runs as runs
    def counts(column, label):
        return [dict(row) for row in conn.execute(
            select(column.label(label), func.count().label("count"))
            .group_by(column).order_by(column)).mappings()]
    return {
        "stored_job_count": conn.scalar(select(func.count()).select_from(jobs)),
        "source_counts": counts(jobs.c.source, "source"),
        "category_counts": counts(jobs.c.category, "category"),
        "latest_successful_ingestion_at": conn.scalar(select(func.max(runs.c.finished_at))
            .where(runs.c.status == "success")),
    }
