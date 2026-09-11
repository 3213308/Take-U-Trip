# app/db/models.py
"""ORM 模型 — 三张表"""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, Float, DateTime, Index
from app.db.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(Text, primary_key=True)
    data = Column(Text, nullable=False)       # JSON 字符串
    updated_at = Column(DateTime, default=datetime.now)


class Itinerary(Base):
    __tablename__ = "itineraries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False, index=True)
    data = Column(Text, nullable=False)       # JSON 行程
    saved_at = Column(DateTime, default=datetime.now)


class Wishlist(Base):
    __tablename__ = "wishlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    category = Column(Text, default="")
    city = Column(Text, default="")
    note = Column(Text, default="")
    checked = Column(Integer, default=0)      # 0=未打卡, 1=已打卡
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_wishlist_user", "user_id", "sort_order"),
    )
