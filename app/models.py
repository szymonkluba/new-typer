from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    bets = relationship("Bet", back_populates="user")


class Competition(Base):
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True)
    fis_event_id = Column(Integer, nullable=True)
    fis_race_id = Column(Integer, nullable=True)
    name = Column(String(200), nullable=False)
    venue = Column(String(200), nullable=False)
    date = Column(Date, nullable=False)
    category = Column(String(20), default="WC")
    type = Column(String(20), default="individual")
    gender = Column(String(5), default="M")
    status = Column(String(20), default="upcoming")

    results = relationship("Result", back_populates="competition", cascade="all, delete-orphan")
    bets = relationship("Bet", back_populates="competition", cascade="all, delete-orphan")


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    athlete_name = Column(String(200), nullable=False)
    nation = Column(String(10), nullable=False)
    total_points = Column(Float, nullable=True)

    competition = relationship("Competition", back_populates="results")


class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    position = Column(Integer, nullable=False)
    athlete_name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bets")
    competition = relationship("Competition", back_populates="bets")

    __table_args__ = (UniqueConstraint("user_id", "competition_id", "position", name="uq_user_comp_pos"),)
