"""Fill an EMPTY local database with synthetic jobs so the dashboard has something to show.

For local development only: every row has source='demo' and invented companies.
It refuses to run when real (non-demo) jobs exist, and `--clear` removes only
demo rows. Real data comes from `python -m app.cli.ingest`.
"""
import argparse
from datetime import datetime, timedelta, timezone
import random
import sys

from sqlalchemy import delete, func, select

from app.db.session import get_engine
from app.models.job import jobs
from app.services.ingestion import upsert_jobs

ROLES = ["Software Engineer", "Senior Software Engineer", "Full Stack Developer", "Frontend Developer",
         "Backend Developer", "Data Engineer", "Data Analyst", "DevOps Engineer", "Cloud Engineer",
         "Machine Learning Engineer", "QA Automation Engineer", "Platform Engineer", "Solutions Architect"]
STACKS = {
    "Software Engineer": ["Python", "Java", "AWS", "Docker", "SQL", "Git", "Agile"],
    "Senior Software Engineer": ["Java", "Spring Boot", "Kafka", "Kubernetes", "AWS", "microservices", "TypeScript"],
    "Full Stack Developer": ["React", "TypeScript", "Node.js", "PostgreSQL", "AWS", "REST APIs", "Docker"],
    "Frontend Developer": ["React", "TypeScript", "Next.js", "Tailwind CSS", "Jest", "Cypress", "GraphQL"],
    "Backend Developer": ["Python", "Django", "FastAPI", "PostgreSQL", "Redis", "Docker", "C#", ".NET"],
    "Data Engineer": ["Python", "SQL", "Spark", "Airflow", "dbt", "Snowflake", "Databricks", "Azure"],
    "Data Analyst": ["SQL", "Power BI", "Tableau", "Python", "Excel", "Snowflake"],
    "DevOps Engineer": ["Terraform", "Kubernetes", "AWS", "Azure DevOps", "CI/CD", "Linux", "Ansible"],
    "Cloud Engineer": ["Azure", "AWS", "Terraform", "Kubernetes", "PowerShell", "Linux", "GCP"],
    "Machine Learning Engineer": ["Python", "PyTorch", "machine learning", "LLMs", "RAG", "MLOps", "AWS"],
    "QA Automation Engineer": ["Playwright", "Cypress", "Selenium", "test automation", "Java", "CI/CD"],
    "Platform Engineer": ["Kubernetes", "Go developer experience", "golang", "Terraform", "GCP", "observability"],
    "Solutions Architect": ["Azure", "AWS", "system design", "microservices", "Dynamics 365", "Salesforce"],
}
BASE_SALARY = {"Senior Software Engineer": 165000, "Solutions Architect": 185000, "Machine Learning Engineer": 170000,
               "Platform Engineer": 160000, "Data Engineer": 145000, "DevOps Engineer": 150000,
               "Cloud Engineer": 145000, "Data Analyst": 105000, "QA Automation Engineer": 115000}
AREAS = ["Melbourne CBD", "Melbourne CBD", "Melbourne CBD", "Docklands", "Southbank", "Richmond", "Cremorne",
         "Collingwood", "South Melbourne", "Box Hill", "Clayton", "Footscray", "Hawthorn", "Dandenong"]


def demo_jobs(count, rng, now):
    for n in range(count):
        role = rng.choice(ROLES)
        stack = rng.sample(STACKS[role], k=min(len(STACKS[role]), rng.randint(2, 5)))
        days_ago = int(rng.triangular(0, 120, 0))
        base = BASE_SALARY.get(role, 130000) * rng.uniform(0.85, 1.15)
        salary = (round(base, -3), round(base * 1.15, -3)) if rng.random() < 0.6 else (None, None)
        yield {
            "id": f"demo-{n}", "title": role, "description": f"Demo listing. Stack: {', '.join(stack)}.",
            "company": {"display_name": f"Demo Company {rng.randint(1, 60)}"},
            "location": {"display_name": f"{rng.choice(AREAS)}, Melbourne"},
            "salary_min": salary[0], "salary_max": salary[1], "contract_time": "full_time",
            "category": {"label": "IT Jobs"}, "redirect_url": None,
            "created": (now - timedelta(days=days_ago, hours=rng.randint(0, 23))).isoformat(),
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed synthetic demo jobs (local development only)")
    parser.add_argument("--count", type=int, default=800)
    parser.add_argument("--clear", action="store_true", help="delete demo rows and exit")
    args = parser.parse_args(argv)
    engine = get_engine()
    with engine.begin() as conn:
        if args.clear:
            removed = conn.execute(delete(jobs).where(jobs.c.source == "demo")).rowcount
            print(f"Removed {removed} demo jobs")
            return 0
        if conn.scalar(select(func.count()).select_from(jobs).where(jobs.c.source != "demo")):
            print("Refusing to seed: this database already holds real jobs.", file=sys.stderr)
            return 1
        rng, now = random.Random(42), datetime.now(timezone.utc)
        from app.sources.normalise import normalise
        records = [normalise(raw) | {"source": "demo"} for raw in demo_jobs(args.count, rng, now)]
        upsert_jobs(conn, records)
    print(f"Seeded {len(records)} demo jobs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
