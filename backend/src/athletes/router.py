import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.model import User
from ..database import get_db
from .analysis_service import MEDIA_ROOT, media_url, run_less_analysis, run_yolo_less_analysis, save_upload
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


@router.get("/{athlete_id}", response_model=AthleteResponse)
def get_athlete(
    athlete_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return athlete_response(get_owned_athlete(athlete_id, current_user, db))


@router.post("/{athlete_id}/analyse", response_model=AnalysisResponse)
async def analyse_athlete(
    athlete_id: str,
    side_video: UploadFile = File(...),
    front_video: UploadFile = File(...),
    pose_model: str = Form("mediapipe"),
    test_side: str = Form("right"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = get_owned_athlete(athlete_id, current_user, db)
    analysis_id = new_public_id("ANL")
    analysis_dir = MEDIA_ROOT / "athletes" / athlete.id / analysis_id
    input_dir = analysis_dir / "inputs"
    output_dir = analysis_dir / "outputs"

    side_suffix = Path(side_video.filename or "").suffix or ".mp4"
    front_suffix = Path(front_video.filename or "").suffix or ".mp4"
    side_path = await save_upload(side_video, input_dir / f"yan_kamera{side_suffix}")
    front_path = await save_upload(front_video, input_dir / f"on_kamera{front_suffix}")

    use_yolo = pose_model.lower() == "yolo"
    normalised_test_side = test_side.lower() if test_side.lower() in ("left", "right") else "right"

    analysis = Analysis(
        id=analysis_id,
        athlete_id=athlete.id,
        user_id=current_user.id,
        status="processing",
        side_video_path=side_path,
        front_video_path=front_path,
        pose_model="yolo" if use_yolo else "mediapipe",
    )
    db.add(analysis)
    db.commit()

    try:
        if use_yolo:
            result = run_yolo_less_analysis(side_path, front_path, output_dir,
                                            test_side=normalised_test_side)
        else:
            result = run_less_analysis(side_path, front_path, output_dir)
    except Exception as exc:
        analysis.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    analysis.status = "reviewed"
    analysis.risk = result["risk"]
    analysis.total_score = result["total_score"]
    analysis.csv_path = result["csv_path"]
    analysis.side_output_path = result.get("side_output_path")
    analysis.front_output_path = result.get("front_output_path")
    db.commit()
    db.refresh(analysis)

    return AnalysisResponse(
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
    )


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

