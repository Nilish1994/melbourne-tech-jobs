"""Record each run's Adzuna category and the skills found in each job."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE ingestion_runs ADD COLUMN search_category TEXT")
    # Checkpoints are per location AND category, so an all-categories run never
    # advances the incremental window of an it-jobs run (or the reverse).
    op.execute("DROP INDEX ix_ingestion_runs_checkpoint")
    op.execute("""CREATE INDEX ix_ingestion_runs_checkpoint
                  ON ingestion_runs(source, lower(search_location), search_category, started_at DESC)
                  WHERE status = 'success'""")
    op.execute("""
        CREATE TABLE job_skills (
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            skill TEXT NOT NULL,
            PRIMARY KEY (job_id, skill)
        )
    """)
    op.execute("CREATE INDEX ix_job_skills_skill ON job_skills(skill)")


def downgrade():
    op.execute("DROP TABLE job_skills")
    op.execute("DROP INDEX ix_ingestion_runs_checkpoint")
    op.execute("""CREATE INDEX ix_ingestion_runs_checkpoint
                  ON ingestion_runs(source, lower(search_location), started_at DESC)
                  WHERE status = 'success'""")
    op.execute("ALTER TABLE ingestion_runs DROP COLUMN search_category")
