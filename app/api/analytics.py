"""Aggregates behind the dashboard. Everything is computed in PostgreSQL.

A job counts on the date it was listed (Adzuna's `created`), falling back to
when we first saw it. Windows are "the last N days" relative to now.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Numeric, and_, case, cast, distinct, func, literal, select

from app.db.session import connection
from app.models.ingestion_run import ingestion_runs as runs
from app.models.job import jobs
from app.models.job_skill import job_skills
from app.skills.catalog import SKILLS
from app.skills.extract import skill_group

router = APIRouter(prefix="/analytics", tags=["analytics"])

listed_at = func.coalesce(jobs.c.posted_at, jobs.c.first_seen_at)

# Adzuna salaries are annual AUD. Values outside this band are hourly/daily
# rates or data errors and would distort medians, so they are left out.
MIN_ANNUAL_SALARY = 30_000
MAX_ANNUAL_SALARY = 500_000
salary_midpoint = case(
    (and_(jobs.c.salary_min.is_not(None), jobs.c.salary_max.is_not(None), jobs.c.salary_min > 0),
     (jobs.c.salary_min + jobs.c.salary_max) / 2),
    else_=func.coalesce(func.nullif(jobs.c.salary_max, 0), func.nullif(jobs.c.salary_min, 0)),
)
plausible_salary = salary_midpoint.between(MIN_ANNUAL_SALARY, MAX_ANNUAL_SALARY)


def since(days):
    return listed_at >= func.now() - timedelta(days=days)


def between(start_days_ago, end_days_ago):
    return and_(listed_at >= func.now() - timedelta(days=start_days_ago),
                listed_at < func.now() - timedelta(days=end_days_ago))


def rounded(value, places=1):
    return None if value is None else round(float(value), places)


@router.get("/summary")
def summary(days: int = Query(30, ge=1, le=365), conn=Depends(connection)):
    window = since(days)
    row = conn.execute(select(
        func.count().label("jobs"),
        func.count(distinct(jobs.c.company_name)).label("companies"),
        func.count().filter(plausible_salary).label("with_salary"),
    ).where(window)).mappings().one()
    top = conn.execute(
        select(job_skills.c.skill, func.count().label("jobs"))
        .join(jobs, jobs.c.id == job_skills.c.job_id).where(window)
        .group_by(job_skills.c.skill).order_by(func.count().desc(), job_skills.c.skill).limit(1)
    ).mappings().first()
    return {
        "days": days,
        "jobs": row["jobs"],
        "companies": row["companies"],
        "salary_coverage_pct": rounded(100 * row["with_salary"] / row["jobs"]) if row["jobs"] else None,
        "jobs_last_7_days": conn.scalar(select(func.count()).select_from(jobs).where(since(7))),
        "total_jobs_stored": conn.scalar(select(func.count()).select_from(jobs)),
        "top_skill": dict(top) if top else None,
        "last_updated": conn.scalar(select(func.max(runs.c.finished_at)).where(runs.c.status == "success")),
    }


@router.get("/skills")
def skills(days: int = Query(30, ge=7, le=365), limit: int = Query(20, ge=1, le=100),
           group: str | None = Query(None, max_length=50), conn=Depends(connection)):
    """Most-requested skills in the window, with the change from the window before."""
    total = conn.scalar(select(func.count()).select_from(jobs).where(since(days)))
    previous_total = conn.scalar(select(func.count()).select_from(jobs).where(between(2 * days, days)))
    current = func.count().filter(since(days))
    previous = func.count().filter(between(2 * days, days))
    query = (select(job_skills.c.skill, current.label("jobs"), previous.label("previous_jobs"))
             .join(jobs, jobs.c.id == job_skills.c.job_id)
             .where(since(2 * days))
             .group_by(job_skills.c.skill)
             .having(current > 0)
             .order_by(current.desc(), job_skills.c.skill))
    if group:
        names = [skill for skill, (skill_group_name, _) in SKILLS.items() if skill_group_name == group]
        if not names:
            raise HTTPException(404, "Unknown skill group")
        query = query.where(job_skills.c.skill.in_(names))
    items = []
    for row in conn.execute(query.limit(limit)).mappings():
        share = 100 * row["jobs"] / total if total else 0
        previous_share = 100 * row["previous_jobs"] / previous_total if previous_total else None
        items.append({
            "skill": row["skill"], "group": skill_group(row["skill"]),
            "jobs": row["jobs"], "share_pct": rounded(share),
            "previous_jobs": row["previous_jobs"],
            # Change in share, not raw count, so a busier month doesn't inflate every skill.
            "share_change_pts": rounded(share - previous_share) if previous_share is not None else None,
        })
    return {"days": days, "total_jobs": total, "items": items}


@router.get("/skills/groups")
def skill_groups():
    groups: dict[str, list[str]] = {}
    for skill, (group, _) in SKILLS.items():
        groups.setdefault(group, []).append(skill)
    return [{"group": group, "skills": sorted(names)} for group, names in groups.items()]


@router.get("/skills/trend")
def skill_trend(skill: list[str] = Query(..., min_length=1, max_length=5),
                weeks: int = Query(12, ge=2, le=52), conn=Depends(connection)):
    """Weekly share of jobs mentioning each skill (Monday-based ISO weeks)."""
    unknown = [name for name in skill if name not in SKILLS]
    if unknown:
        raise HTTPException(404, f"Unknown skill: {unknown[0]}")
    week = func.date_trunc("week", listed_at)
    window = listed_at >= func.date_trunc("week", func.now()) - timedelta(weeks=weeks - 1)
    totals = {row.week: row.jobs for row in conn.execute(
        select(week.label("week"), func.count().label("jobs")).where(window).group_by(week))}
    counts = {}
    for row in conn.execute(
            select(week.label("week"), job_skills.c.skill, func.count().label("jobs"))
            .join(jobs, jobs.c.id == job_skills.c.job_id)
            .where(window, job_skills.c.skill.in_(skill))
            .group_by(week, job_skills.c.skill)):
        counts[(row.week, row.skill)] = row.jobs
    points = []
    for week_start in sorted(totals):
        point = {"week": week_start.date().isoformat(), "total_jobs": totals[week_start]}
        for name in skill:
            jobs_count = counts.get((week_start, name), 0)
            point[name] = rounded(100 * jobs_count / totals[week_start])
        points.append(point)
    return {"skills": skill, "weeks": weeks, "points": points}


@router.get("/salaries")
def salaries(days: int = Query(90, ge=7, le=365), min_jobs: int = Query(5, ge=1, le=100),
             limit: int = Query(15, ge=1, le=50), conn=Depends(connection)):
    """Annual salary quartiles per skill, from jobs that advertise a plausible salary."""
    def quartiles(label_column, *, group=True, join=True):
        mid = cast(salary_midpoint, Numeric)
        query = select(
            label_column,
            func.count().label("jobs"),
            func.percentile_cont(0.25).within_group(mid).label("p25"),
            func.percentile_cont(0.5).within_group(mid).label("median"),
            func.percentile_cont(0.75).within_group(mid).label("p75"),
        )
        if join:
            query = query.select_from(job_skills.join(jobs, jobs.c.id == job_skills.c.job_id))
        else:
            query = query.select_from(jobs)
        query = query.where(since(days), plausible_salary)
        return query.group_by(label_column) if group else query

    def shape(row):
        return {"skill": row["skill"], "jobs": row["jobs"],
                "p25": rounded(row["p25"], 0), "median": rounded(row["median"], 0), "p75": rounded(row["p75"], 0)}

    overall = conn.execute(quartiles(literal("All tech jobs").label("skill"), group=False, join=False)).mappings().one()
    rows = conn.execute(quartiles(job_skills.c.skill.label("skill"))
                        .having(func.count() >= min_jobs)
                        .order_by(func.count().desc(), job_skills.c.skill).limit(limit)).mappings()
    items = sorted((shape(row) for row in rows), key=lambda item: -(item["median"] or 0))
    return {"days": days, "overall": shape(overall) if overall["jobs"] else None, "items": items,
            "note": f"Annual AUD; midpoint of advertised range; values outside "
                    f"${MIN_ANNUAL_SALARY:,}-${MAX_ANNUAL_SALARY:,} excluded."}


@router.get("/locations")
def locations(days: int = Query(30, ge=1, le=365), limit: int = Query(15, ge=1, le=50),
              conn=Depends(connection)):
    """Where the jobs are: the first part of Adzuna's location name, e.g. 'Richmond'."""
    area = func.nullif(func.trim(func.split_part(jobs.c.location, ",", 1)), "")
    total = conn.scalar(select(func.count()).select_from(jobs).where(since(days)))
    rows = conn.execute(select(area.label("area"), func.count().label("jobs"))
                        .where(since(days), area.is_not(None))
                        .group_by(area).order_by(func.count().desc(), area).limit(limit)).mappings()
    return {"days": days, "total_jobs": total,
            "items": [{"area": row["area"], "jobs": row["jobs"],
                       "share_pct": rounded(100 * row["jobs"] / total) if total else 0} for row in rows]}
