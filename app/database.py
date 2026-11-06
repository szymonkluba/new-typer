from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_db():
    inspector = sa_inspect(engine)
    if "results" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("results")]
        if "fis_code" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE results ADD COLUMN fis_code INTEGER"))


def create_tables():
    Base.metadata.create_all(bind=engine)
    _migrate_db()
