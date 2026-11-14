from contextlib import contextmanager

import pytest
from sqlalchemy import select

from app.cli.backfill_skills import backfill
from app.models.job import jobs
from app.models.job_skill import job_skills
from app.services.ingestion import upsert_jobs
from app.skills.catalog import SKILLS
from app.skills.extract import extract_skills, skill_group
from app.sources.normalise import normalise


@pytest.mark.parametrize("text, expected", [
    ("Senior Python Developer", ["Python"]),
    ("Experience with JavaScript and TypeScript", ["JavaScript", "TypeScript"]),
    ("Java developer", ["Java"]),
    ("C# / .NET Core engineer", [".NET", "C#"]),
    ("Modern C++ (C++17)", ["C++"]),
    ("Node.js, Express.js and MongoDB", ["Express", "MongoDB", "Node.js"]),
    ("PostgreSQL and MySQL; strong SQL", ["MySQL", "PostgreSQL", "SQL"]),
    ("Deploy on AWS with Docker & Kubernetes (EKS)", ["AWS", "Docker", "Kubernetes"]),
    ("Terraform, CI/CD pipelines in GitHub Actions", ["CI/CD", "GitHub Actions", "Terraform"]),
    ("Build RAG apps with LLMs", ["LLMs", "RAG"]),
    ("Golang backend engineer", ["Go"]),
    ("React and React Native", ["React", "React Native"]),
    ("Next.js with Tailwind CSS", ["Next.js", "Tailwind CSS"]),
    ("Power BI dashboards on Snowflake using dbt", ["Power BI", "Snowflake", "dbt"]),
    ("Spring Boot microservices", ["Microservices", "Spring"]),
    ("Dynamics 365 and Power Apps", ["Dynamics 365", "Power Platform"]),
])
def test_extracts_expected_skills(text, expected):
    assert extract_skills(text) == expected


@pytest.mark.parametrize("text, absent", [
    ("JavaScript only", "Java"),
    ("MySQL administration", "SQL"),
    ("Work with GitHub daily", "Git"),
    ("Able to react quickly to incidents", "React"),
    ("A swift response to customers", "Swift"),
    ("Starting this spring", "Spring"),
    ("Go above and beyond for clients", "Go"),
    ("Guard rails for safety", "Ruby on Rails"),
    ("Network node maintenance", "Node.js"),
    ("Express interest by applying", "Express"),
])
def test_avoids_false_positives(text, absent):
    assert absent not in extract_skills(text)


def test_matches_across_line_breaks_and_case():
    assert extract_skills("machine\n  LEARNING engineer") == ["Machine Learning"]


def test_combines_title_and_description_and_ignores_empty():
    assert extract_skills("Data Engineer", None, "Airflow and Spark") == ["Airflow", "Spark"]
    assert extract_skills(None, "") == []


def test_every_skill_has_a_group():
    assert all(skill_group(skill) for skill in SKILLS)
    assert skill_group("Not a skill") is None


def test_upsert_stores_and_replaces_skills(conn, raw):
    upsert_jobs(conn, [normalise(raw | {"title": "Python Developer", "description": "Django and AWS"})])
    job_id = conn.scalar(select(jobs.c.id))
    stored = lambda: sorted(conn.scalars(select(job_skills.c.skill).where(job_skills.c.job_id == job_id)))
    assert stored() == ["AWS", "Django", "Python"]
    upsert_jobs(conn, [normalise(raw | {"title": "Java Developer", "description": "Spring Boot"})])
    assert stored() == ["Java", "Spring"]


class Engine:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        with self.conn.begin_nested():
            yield self.conn


def test_backfill_recomputes_all_jobs(conn, raw):
    upsert_jobs(conn, [normalise(raw | {"id": str(n), "title": f"Python Developer {n}"}) for n in range(5)])
    conn.execute(job_skills.delete())
    assert backfill(Engine(conn), batch_size=2) == 5
    assert sorted(conn.scalars(select(job_skills.c.skill))) == ["Python"] * 5
