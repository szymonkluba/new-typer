import zoneinfo
from datetime import datetime, time

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(Integer, primary_key=True)
    fis_code = Column(Integer, unique=True, nullable=False)
    competitor_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    nation = Column(String(10), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    start_time = Column(Time, nullable=True)
    category = Column(String(20), default="WC")
    type = Column(String(20), default="individual")
    gender = Column(String(5), default="M")
    status = Column(String(20), default="upcoming")

    results = relationship("Result", back_populates="competition", cascade="all, delete-orphan")
    bets = relationship("Bet", back_populates="competition", cascade="all, delete-orphan")

    @property
    def betting_open(self) -> bool:
        if self.status != "upcoming":
            return False
        from app.config import BET_CUTOFF_HOUR, TIMEZONE

        tz = zoneinfo.ZoneInfo(TIMEZONE)
        now = datetime.now(tz)
        cutoff_time = self.start_time if self.start_time else time(BET_CUTOFF_HOUR)
        cutoff = datetime.combine(self.date, cutoff_time, tzinfo=tz)
        return now < cutoff


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    fis_code = Column(Integer, nullable=True)
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
