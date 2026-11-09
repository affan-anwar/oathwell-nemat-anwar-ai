from alembic import context

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import make_engine

target_metadata = Base.metadata


def run() -> None:
    engine = make_engine(get_settings().database_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()
