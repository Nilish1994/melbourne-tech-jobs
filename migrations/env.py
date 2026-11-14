from alembic import context
from app.db.session import get_engine
from app.models.job import metadata
from app.models.ingestion_run import ingestion_runs  # noqa: F401

with get_engine().connect() as connection:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()
