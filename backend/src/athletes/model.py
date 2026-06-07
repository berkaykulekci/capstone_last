import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


def new_public_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(String, primary_key=True, default=lambda: new_public_id("ATH"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    sport = Column(String, nullable=True)
    team = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    analyses = relationship("Analysis", back_populates="athlete", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: new_public_id("ANL"))
    athlete_id = Column(String, ForeignKey("athletes.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="reviewed", nullable=False)
    risk = Column(String, nullable=True)
    total_score = Column(Integer, nullable=True)
    side_video_path = Column(String, nullable=True)
    front_video_path = Column(String, nullable=True)
    csv_path = Column(String, nullable=True)
    side_output_path = Column(String, nullable=True)
    front_output_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    athlete = relationship("Athlete", back_populates="analyses")
