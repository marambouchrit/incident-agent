from alembic import context
from sqlalchemy import create_engine

from app import config
from app.models import Base

target_metadata = Base.metadata


def run_migrations() -> None:
    engine = create_engine(config.DATABASE_URL)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
