"""Feed of newly seen jobs, with descriptions, for downstream tools on the same host.

Unlike /jobs, this includes the description snippet, so it must stay private:
the API binds to localhost, and the web app's /api proxy does not forward
/feed/* (see web/app/api/[...path]/route.ts). Consumers page forward with the
returned `next_cursor` until `has_more` is false.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select

from app.api.routes import attach_skills
from app.db.session import connection
from app.models.job import jobs

router = APIRouter(prefix="/feed", tags=["feed"])

FEED_COLUMNS = [jobs.c.id, jobs.c.title, jobs.c.company_name, jobs.c.location, jobs.c.description,
                jobs.c.salary_min, jobs.c.salary_max, jobs.c.employment_type, jobs.c.category,
                jobs.c.source, jobs.c.source_url, jobs.c.posted_at, jobs.c.first_seen_at]


@router.get("/jobs")
def new_jobs(since: datetime | None = Query(None, description="first_seen_at strictly after this"),
             after_id: UUID | None = Query(None, description="tie-breaker for jobs first seen at `since`"),
             limit: int = Query(100, ge=1, le=500), conn=Depends(connection)):
    query = select(*FEED_COLUMNS).where(jobs.c.source != "demo")
    if since is not None:
        if after_id is not None:
            query = query.where(or_(jobs.c.first_seen_at > since,
                                    and_(jobs.c.first_seen_at == since, jobs.c.id > after_id)))
        else:
            query = query.where(jobs.c.first_seen_at > since)
    rows = conn.execute(query.order_by(jobs.c.first_seen_at, jobs.c.id).limit(limit + 1)).mappings().all()
    items = attach_skills(conn, [dict(row) for row in rows[:limit]])
    last = items[-1] if items else None
    return {
        "items": items,
        "has_more": len(rows) > limit,
        "next_cursor": {"since": last["first_seen_at"], "after_id": last["id"]} if last else None,
    }
