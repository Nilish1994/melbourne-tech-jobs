"""Add collection audit without changing jobs or the quota ledger."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE ingestion_runs (
            id UUID PRIMARY KEY,
            source TEXT NOT NULL,
            search_location TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            finished_at TIMESTAMPTZ,
            status TEXT NOT NULL CHECK (status IN
                ('running', 'success', 'partial', 'failed', 'quota_exhausted')),
            mode TEXT NOT NULL CHECK (mode IN ('full', 'incremental')),
            max_pages INTEGER NOT NULL CHECK (max_pages > 0),
            lookback_days INTEGER NOT NULL CHECK (lookback_days > 0),
            overlap_days INTEGER NOT NULL CHECK (overlap_days >= 0),
            max_days_old INTEGER CHECK (max_days_old > 0),
            pages_requested INTEGER NOT NULL DEFAULT 0 CHECK (pages_requested >= 0),
            pages_completed INTEGER NOT NULL DEFAULT 0 CHECK (pages_completed >= 0),
            observations_processed INTEGER NOT NULL DEFAULT 0 CHECK (observations_processed >= 0),
            newly_inserted_jobs INTEGER NOT NULL DEFAULT 0 CHECK (newly_inserted_jobs >= 0),
            existing_jobs_updated INTEGER NOT NULL DEFAULT 0 CHECK (existing_jobs_updated >= 0),
            error_summary TEXT,
            CHECK (pages_completed <= pages_requested),
            CHECK ((status = 'running') = (finished_at IS NULL))
        )
    """)
    op.execute("CREATE INDEX ix_ingestion_runs_started ON ingestion_runs(started_at DESC, id DESC)")
    op.execute("""CREATE INDEX ix_ingestion_runs_checkpoint
                  ON ingestion_runs(source, lower(search_location), started_at DESC)
                  WHERE status = 'success'""")


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; use a reviewed migration.")
