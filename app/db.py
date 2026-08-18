from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

is_sqlite = settings.database_url.startswith("sqlite")
is_sqlite_memory = is_sqlite and ":memory:" in settings.database_url

engine_kwargs = {}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
if is_sqlite_memory:
    # In-memory sqlite is per-connection; without StaticPool each pooled
    # connection sees an empty database, so tables created on one
    # connection are invisible to queries on another.
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401 (ensures models are registered)

    Base.metadata.create_all(bind=engine)
