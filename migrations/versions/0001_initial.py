"""Initial jobs schema and persistent API request accounting."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE TABLE jobs (
            id UUID PRIMARY KEY,
            source TEXT NOT NULL, source_job_id TEXT NOT NULL, title TEXT NOT NULL,
            company_name TEXT, location TEXT,
            latitude NUMERIC(10,7), longitude NUMERIC(10,7), description TEXT,
            salary_min NUMERIC(14,2), salary_max NUMERIC(14,2), salary_currency TEXT,
            employment_type TEXT, category TEXT, source_url TEXT, posted_at TIMESTAMPTZ,
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true, raw_payload JSONB NOT NULL,
            CONSTRAINT uq_jobs_source_job UNIQUE(source, source_job_id)
        )
    """)
    op.execute("CREATE INDEX ix_jobs_first_seen_id ON jobs (first_seen_at DESC, id DESC)")
    for column in ("title", "description", "location"):
        op.execute(f"CREATE INDEX ix_jobs_{column}_trgm ON jobs USING gin ({column} gin_trgm_ops)")
    op.execute("CREATE TABLE adzuna_requests (requested_at TIMESTAMPTZ NOT NULL)")
    op.execute("CREATE INDEX ix_adzuna_requests_time ON adzuna_requests(requested_at)")


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; use a reviewed migration.")
