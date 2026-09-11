# app/db/__init__.py
from app.db.database import Base, engine, SessionLocal


def init_db():
    Base.metadata.create_all(engine)
    _migrate()


def _migrate():
    """已有库的轻量迁移（create_all 不会给旧表加列）"""
    with engine.begin() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(wishlist)")]
        if "city" not in cols:
            conn.exec_driver_sql("ALTER TABLE wishlist ADD COLUMN city TEXT DEFAULT ''")
