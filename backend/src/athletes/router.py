import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.model import User
from ..database import get_db
from .analysis_service import (
    MEDIA_ROOT,
    media_url,
    run_less_analysis,
    run_rtm_less_analysis,
    run_yolo_less_analysis,
    save_upload,
)

VALID_POSE_MODELS = {"mediapipe", "yolo", "rtm"}
from .model import Analysis, Athlete, new_public_id
from .schema import AnalysisResponse, AnalysisSummary, AthleteCreate, AthleteResponse

router = APIRouter(prefix="/athletes", tags=["Athletes"])


def analysis_summary(analysis: Analysis | None) -> AnalysisSummary | None:
    if analysis is None:
        return None
    return AnalysisSummary(
        id=analysis.id,
        status=analysis.status,
        risk=analysis.risk,
        total_score=analysis.total_score,
        csv_url=media_url(analysis.csv_path),
        side_output_url=media_url(analysis.side_output_path),
        front_output_url=media_url(analysis.front_output_path),
        pose_model=analysis.pose_model,
        created_at=analysis.created_at,
    )


def athlete_response(athlete: Athlete) -> AthleteResponse:
    sorted_analyses = sorted(athlete.analyses, key=lambda item: item.created_at, reverse=True)
    return AthleteResponse(
        id=athlete.id,
        name=athlete.name,
        sport=athlete.sport,
        team=athlete.team,
        created_at=athlete.created_at,
        latest_analysis=analysis_summary(sorted_analyses[0] if sorted_analyses else None),
        analyses=[s for a in sorted_analyses if (s := analysis_summary(a)) is not None],
    )


def get_owned_athlete(athlete_id: str, user: User, db: Session) -> Athlete:
    athlete = db.query(Athlete).filter(
        Athlete.id == athlete_id,
        Athlete.user_id == user.id,
    ).first()
    if athlete is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Athlete not found")
    return athlete


@router.get("", response_model=list[AthleteResponse])
def list_athletes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athletes = db.query(Athlete).filter(Athlete.user_id == current_user.id).order_by(Athlete.created_at.desc()).all()
    return [athlete_response(athlete) for athlete in athletes]


@router.post("", response_model=AthleteResponse, status_code=status.HTTP_201_CREATED)
def create_athlete(
    payload: AthleteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = Athlete(
        id=new_public_id("ATH"),
        user_id=current_user.id,
        name=payload.name.strip(),
        sport=(payload.sport or "").strip() or None,
        team=(payload.team or "").strip() or None,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete_response(athlete)


@router.get("/statistics")
def get_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return aggregated statistics for all athletes owned by the current user."""
    from collections import defaultdict

    athletes = (
        db.query(Athlete)
        .filter(Athlete.user_id == current_user.id)
        .order_by(Athlete.created_at.asc())
        .all()
    )

    total_athletes = len(athletes)
    total_analyses = 0
    risk_counts = {"High": 0, "Moderate": 0, "Low": 0, "No data": 0}
    model_counts = defaultdict(int)
    sport_stats = defaultdict(lambda: {"count": 0, "scores": [], "high": 0, "moderate": 0, "low": 0})
    score_timeline = []
    athlete_summaries = []

    for athlete in athletes:
        analyses = sorted(athlete.analyses, key=lambda a: a.created_at)
        scores = [a.total_score for a in analyses if a.total_score is not None]

        total_analyses += len(analyses)

        for analysis in analyses:
            r = analysis.risk or "No data"
            if r in risk_counts:
                risk_counts[r] += 1
            else:
                risk_counts["No data"] += 1

            model_counts[analysis.pose_model or "mediapipe"] += 1

            if analysis.total_score is not None:
                score_timeline.append({
                    "date": analysis.created_at.strftime("%Y-%m-%d"),
                    "score": analysis.total_score,
                    "athlete": athlete.name,
                    "model": analysis.pose_model or "mediapipe",
                })

            sport_key = athlete.sport or "Unknown"
            sport_stats[sport_key]["count"] += 1
            if analysis.total_score is not None:
                sport_stats[sport_key]["scores"].append(analysis.total_score)
            r_lower = (analysis.risk or "").lower()
            if r_lower == "high":
                sport_stats[sport_key]["high"] += 1
            elif r_lower == "moderate":
                sport_stats[sport_key]["moderate"] += 1
            elif r_lower == "low":
                sport_stats[sport_key]["low"] += 1

        latest = analyses[-1] if analyses else None
        avg_score = round(sum(scores) / len(scores), 1) if scores else None
        athlete_summaries.append({
            "id": athlete.id,
            "name": athlete.name,
            "sport": athlete.sport,
            "team": athlete.team,
            "total_analyses": len(analyses),
            "avg_score": avg_score,
            "latest_score": latest.total_score if latest else None,
            "latest_risk": latest.risk if latest else None,
            "latest_model": latest.pose_model if latest else None,
        })

    score_distribution = {"0-4": 0, "5-9": 0, "10-14": 0, "15-19": 0}
    for entry in score_timeline:
        s = entry["score"]
        if s <= 4:
            score_distribution["0-4"] += 1
        elif s <= 9:
            score_distribution["5-9"] += 1
        elif s <= 14:
            score_distribution["10-14"] += 1
        else:
            score_distribution["15-19"] += 1

    sport_summary = []
    for sport, data in sport_stats.items():
        avg = round(sum(data["scores"]) / len(data["scores"]), 1) if data["scores"] else None
        sport_summary.append({
            "sport": sport,
            "analyses": data["count"],
            "avg_score": avg,
            "high": data["high"],
            "moderate": data["moderate"],
            "low": data["low"],
        })
    sport_summary.sort(key=lambda x: x["analyses"], reverse=True)

    return {
        "total_athletes": total_athletes,
        "total_analyses": total_analyses,
        "risk_distribution": risk_counts,
        "score_distribution": score_distribution,
        "model_usage": dict(model_counts),
        "sport_summary": sport_summary,
        "score_timeline": sorted(score_timeline, key=lambda x: x["date"]),
        "athlete_summaries": athlete_summaries,
    }


@router.get("/{athlete_id}", response_model=AthleteResponse)
def get_athlete(
    athlete_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return athlete_response(get_owned_athlete(athlete_id, current_user, db))


@router.post("/{athlete_id}/analyse", response_model=list[AnalysisResponse])
async def analyse_athlete(
    athlete_id: str,
    side_video: UploadFile = File(...),
    front_video: UploadFile = File(...),
    pose_models: str = Form("mediapipe"),
    pose_model: str = Form(""),
    test_side: str = Form("right"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = get_owned_athlete(athlete_id, current_user, db)
    normalised_test_side = test_side.lower() if test_side.lower() in ("left", "right") else "right"

    # Resolve which models to run. `pose_models` is the new multi-value field
    # (comma-separated); `pose_model` is the legacy single-value fallback.
    raw_models = pose_models or pose_model or "mediapipe"
    selected_models = [
        m for m in (m.strip().lower() for m in raw_models.split(","))
        if m in VALID_POSE_MODELS
    ] or ["mediapipe"]
    # Deduplicate while preserving order
    seen: set[str] = set()
    selected_models = [m for m in selected_models if not (m in seen or seen.add(m))]  # type: ignore[func-returns-value]

    # Save uploads once, shared across all model runs
    shared_dir = MEDIA_ROOT / "athletes" / athlete.id / "shared_inputs"
    side_suffix = Path(side_video.filename or "").suffix or ".mp4"
    front_suffix = Path(front_video.filename or "").suffix or ".mp4"
    side_path = await save_upload(side_video, shared_dir / f"yan_kamera{side_suffix}")
    front_path = await save_upload(front_video, shared_dir / f"on_kamera{front_suffix}")

    responses: list[AnalysisResponse] = []

    for model in selected_models:
        analysis_id = new_public_id("ANL")
        output_dir = MEDIA_ROOT / "athletes" / athlete.id / analysis_id / "outputs"

        analysis = Analysis(
            id=analysis_id,
            athlete_id=athlete.id,
            user_id=current_user.id,
            status="processing",
            side_video_path=side_path,
            front_video_path=front_path,
            pose_model=model,
        )
        db.add(analysis)
        db.commit()

        try:
            if model == "yolo":
                result = run_yolo_less_analysis(side_path, front_path, output_dir,
                                                test_side=normalised_test_side)
            elif model == "rtm":
                result = run_rtm_less_analysis(side_path, front_path, output_dir,
                                               test_side=normalised_test_side)
            else:
                result = run_less_analysis(side_path, front_path, output_dir)
        except Exception as exc:
            analysis.status = "failed"
            db.commit()
            responses.append(AnalysisResponse(
                id=analysis.id,
                athlete_id=analysis.athlete_id,
                status="failed",
                risk=None,
                total_score=None,
                csv_url=None,
                side_output_url=None,
                front_output_url=None,
                pose_model=model,
                created_at=analysis.created_at,
            ))
            continue

        analysis.status = "reviewed"
        analysis.risk = result["risk"]
        analysis.total_score = result["total_score"]
        analysis.csv_path = result["csv_path"]
        analysis.side_output_path = result.get("side_output_path")
        analysis.front_output_path = result.get("front_output_path")
        db.commit()
        db.refresh(analysis)

        responses.append(AnalysisResponse(
            id=analysis.id,
            athlete_id=analysis.athlete_id,
            status=analysis.status,
            risk=analysis.risk,
            total_score=analysis.total_score,
            csv_url=media_url(analysis.csv_path),
            side_output_url=media_url(analysis.side_output_path),
            front_output_url=media_url(analysis.front_output_path),
            pose_model=analysis.pose_model,
            created_at=analysis.created_at,
        ))

    return responses


@router.delete("/{athlete_id}/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    athlete_id: str,
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = get_owned_athlete(athlete_id, current_user, db)
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.athlete_id == athlete.id,
        Analysis.user_id == current_user.id,
    ).first()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    # Delete files from disk if they exist
    analysis_dir = MEDIA_ROOT / "athletes" / athlete.id / analysis.id
    if analysis_dir.exists():
        shutil.rmtree(analysis_dir, ignore_errors=True)

    db.delete(analysis)
    db.commit()

