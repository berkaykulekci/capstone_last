from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AthleteCreate(BaseModel):
    name: str
    sport: Optional[str] = None
    team: Optional[str] = None


class AnalysisSummary(BaseModel):
    id: str
    status: str
    risk: Optional[str] = None
    total_score: Optional[int] = None
    csv_url: Optional[str] = None
    side_output_url: Optional[str] = None
    front_output_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AthleteResponse(BaseModel):
    id: str
    name: str
    sport: Optional[str] = None
    team: Optional[str] = None
    created_at: datetime
    latest_analysis: Optional[AnalysisSummary] = None


class AnalysisResponse(AnalysisSummary):
    athlete_id: str
