import os
import shutil
from pathlib import Path

from fastapi import UploadFile

from ..less_engine.config import NORMALIZE_VIDEO_FRAME_COORDS, NORMALIZED_FRAME_WIDTH
from ..less_engine.pose_extractor import extract_poses, detect_test_side
from ..less_engine.jump_detector import detect_jumps
from ..less_engine.less_rules import evaluate_yan_kamera, evaluate_on_kamera, combine_results
from ..less_engine.report_generator import generate_csv
from ..less_engine.visualizer import create_camera_video


MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "media")).resolve()


def media_url(path: str | None) -> str | None:
    if not path:
        return None
    try:
        rel = Path(path).resolve().relative_to(MEDIA_ROOT)
    except ValueError:
        return None
    return f"/media/{rel.as_posix()}"


def score_to_risk(score: int | None) -> str:
    if score is None:
        return "No data"
    if score >= 10:
        return "High"
    if score >= 6:
        return "Moderate"
    return "Low"


async def save_upload(upload: UploadFile, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out_file:
        shutil.copyfileobj(upload.file, out_file)
    await upload.close()
    return str(destination)


def run_less_analysis(side_video_path: str, front_video_path: str, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    yan_poses, yan_w, yan_h, yan_fps, yan_total = extract_poses(side_video_path)
    on_poses, on_w, on_h, on_fps, on_total = extract_poses(front_video_path)

    test_side = detect_test_side(yan_poses)
    jumps_yan = detect_jumps(yan_poses, test_side, label="YAN")
    jumps_on = detect_jumps(on_poses, test_side, label="ON")

    if not jumps_yan:
        raise RuntimeError("Yan kamera videosunda iniş tespit edilemedi.")
    if not jumps_on:
        raise RuntimeError("Ön kamera videosunda iniş tespit edilemedi.")

    yan_results = evaluate_yan_kamera(yan_poses, jumps_yan, test_side)
    on_analysis_width = NORMALIZED_FRAME_WIDTH if NORMALIZE_VIDEO_FRAME_COORDS else on_w
    on_results = evaluate_on_kamera(on_poses, jumps_on, test_side, on_analysis_width)
    combined = combine_results(yan_results, on_results)

    csv_path = output_dir / "less_sonuclar.csv"
    side_output_path = output_dir / "gorsel_analiz_yan.mp4"
    front_output_path = output_dir / "gorsel_analiz_on.mp4"

    total_score = generate_csv(combined, str(csv_path))
    create_camera_video(side_video_path, jumps_yan, combined, "yan", str(side_output_path))
    create_camera_video(front_video_path, jumps_on, combined, "on", str(front_output_path))

    return {
        "total_score": total_score,
        "risk": score_to_risk(total_score),
        "csv_path": str(csv_path),
        "side_output_path": str(side_output_path),
        "front_output_path": str(front_output_path),
        "jumps_yan": jumps_yan,
        "jumps_on": jumps_on,
    }
