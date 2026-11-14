"""Skills found in a job's title and description (see app/skills)."""
from sqlalchemy import Table, Column, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.job import metadata

job_skills = Table(
    "job_skills", metadata,
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("skill", Text, primary_key=True),
)
