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

from ..less_engine.yolo_config import (
    NORMALIZE_VIDEO_FRAME_COORDS as YOLO_NORMALIZE,
    NORMALIZED_FRAME_WIDTH as YOLO_FRAME_WIDTH,
)
from ..less_engine.yolo_pose_extractor import extract_poses as yolo_extract_poses
from ..less_engine.yolo_jump_detector import detect_jumps as yolo_detect_jumps
from ..less_engine.yolo_less_rules import (
    evaluate_yan_kamera as yolo_evaluate_yan,
    evaluate_on_kamera as yolo_evaluate_on,
    combine_results as yolo_combine_results,
    compute_total_score as yolo_compute_total_score,
    YOLO_NA_MADDE,
)
from ..less_engine.yolo_visualizer import create_yolo_camera_video

from ..less_engine.rtm_config import (
    NORMALIZE_VIDEO_FRAME_COORDS as RTM_NORMALIZE,
    NORMALIZED_FRAME_WIDTH as RTM_FRAME_WIDTH,
)
from ..less_engine.rtm_pose_extractor import extract_poses as rtm_extract_poses
from ..less_engine.rtm_jump_detector import detect_jumps as rtm_detect_jumps
from ..less_engine.rtm_less_rules import (
    evaluate_yan_kamera as rtm_evaluate_yan,
    evaluate_on_kamera as rtm_evaluate_on,
    combine_results as rtm_combine_results,
    compute_total_score as rtm_compute_total_score,
    RTM_NA_MADDE,
)
from ..less_engine.rtm_visualizer import create_rtm_camera_video


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


def run_yolo_less_analysis(
    side_video_path: str,
    front_video_path: str,
    output_dir: Path,
    test_side: str = "right",
) -> dict:
    """
    YOLO Pose tabanlı LESS analizi.

    MediaPipe sürümünden farklar:
      - test_side otomatik belirlenemiyor (Z yok) → parametre olarak alınır
      - M4, M9, M10 hesaplanamaz → yolo_na_madde listesinde döner
      - total_score max 16'dır (19 yerine)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    yan_poses, yan_w, yan_h, yan_fps, _ = yolo_extract_poses(side_video_path)
    on_poses,  on_w,  on_h,  on_fps,  _ = yolo_extract_poses(front_video_path)

    jumps_yan = yolo_detect_jumps(yan_poses, test_side, label="YAN")
    jumps_on  = yolo_detect_jumps(on_poses,  test_side, label="ON")

    if not jumps_yan:
        raise RuntimeError("[YOLO] Yan kamera videosunda iniş tespit edilemedi.")
    if not jumps_on:
        raise RuntimeError("[YOLO] Ön kamera videosunda iniş tespit edilemedi.")

    on_analysis_width = YOLO_FRAME_WIDTH if YOLO_NORMALIZE else on_w

    yan_results = yolo_evaluate_yan(yan_poses, jumps_yan, test_side)
    on_results  = yolo_evaluate_on(on_poses, jumps_on, test_side, on_analysis_width)
    combined    = yolo_combine_results(yan_results, on_results)

    total_score, skorlar, yaklasik_maddeler = yolo_compute_total_score(combined)

    csv_path         = output_dir / "yolo_less_sonuclar.csv"
    side_output_path = output_dir / "gorsel_analiz_yan.mp4"
    front_output_path = output_dir / "gorsel_analiz_on.mp4"

    _write_yolo_csv(str(csv_path), combined, skorlar, total_score, test_side, yaklasik_maddeler)

    create_yolo_camera_video(
        side_video_path, yan_poses, jumps_yan, yan_results, "yan", str(side_output_path))
    create_yolo_camera_video(
        front_video_path, on_poses, jumps_on, on_results, "on", str(front_output_path))

    return {
        "total_score": total_score,
        "risk": score_to_risk(total_score),
        "csv_path": str(csv_path),
        "side_output_path": str(side_output_path),
        "front_output_path": str(front_output_path),
        "jumps_yan": jumps_yan,
        "jumps_on": jumps_on,
        "yolo_na_madde": [],
        "yolo_yaklasik_madde": yaklasik_maddeler,
        "pose_model": "yolo",
    }


def _write_yolo_csv(path: str, combined, skorlar, toplam, test_side, yaklasik_maddeler=None, model='yolo'):
    import pandas as pd
    from ..less_engine.report_generator import MADDE_ISIMLERI, MADDE_SIRASI
    if yaklasik_maddeler is None:
        yaklasik_maddeler = []

    rows = []
    for mk in MADDE_SIRASI:
        m_name, kamera = MADDE_ISIMLERI[mk]
        m_no = int(mk[1:])
        puanlar = []
        row = {
            'model': model,
            'test_tarafi': test_side,
            'madde_no': m_no,
            'madde_adi': m_name,
            'kamera': kamera,
            'yaklaşık': m_no in yaklasik_maddeler,
        }
        for idx, jump_res in enumerate(combined):
            if mk in jump_res:
                r = jump_res[mk]
                row[f'atlayis_{idx+1}_deger'] = r['olcum']
                row[f'atlayis_{idx+1}_puan'] = r['puan']
                puanlar.append(r['puan'])
            else:
                row[f'atlayis_{idx+1}_deger'] = '-'
                row[f'atlayis_{idx+1}_puan'] = '-'
                puanlar.append(0)
        for missing in range(len(combined), 3):
            row[f'atlayis_{missing+1}_deger'] = '-'
            row[f'atlayis_{missing+1}_puan'] = '-'
            puanlar.append(0)
        row['karar_puani'] = skorlar.get(mk, 0)
        rows.append(row)

    rows.append({
        'model': model, 'test_tarafi': test_side,
        'madde_no': '', 'madde_adi': 'TOPLAM LESS PUANI', 'kamera': '', 'yaklaşık': False,
        'atlayis_1_deger': '', 'atlayis_1_puan': '',
        'atlayis_2_deger': '', 'atlayis_2_puan': '',
        'atlayis_3_deger': '', 'atlayis_3_puan': '',
        'karar_puani': toplam,
    })
    pd.DataFrame(rows).to_csv(path, index=False, encoding='utf-8-sig')


def run_rtm_less_analysis(
    side_video_path: str,
    front_video_path: str,
    output_dir: Path,
    test_side: str = "right",
) -> dict:
    """
    RTMPose-WholeBody (ONNX) tabanlı LESS analizi.

    YOLO sürümünden farkları:
      - heel + toe keypoint'leri MEVCUT → M4, M9, M10 PROXY OLMADAN exact hesaplanır
      - yaklaşık (yaklasik) madde YOKTUR; tüm 17 madde tam, max skor 19
      - test_side otomatik belirlenemiyor (Z yok) → parametre olarak alınır
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    yan_poses, yan_w, yan_h, yan_fps, _ = rtm_extract_poses(side_video_path)
    on_poses,  on_w,  on_h,  on_fps,  _ = rtm_extract_poses(front_video_path)

    jumps_yan = rtm_detect_jumps(yan_poses, test_side, label="YAN")
    jumps_on  = rtm_detect_jumps(on_poses,  test_side, label="ON")

    if not jumps_yan:
        raise RuntimeError("[RTMPose] Yan kamera videosunda iniş tespit edilemedi.")
    if not jumps_on:
        raise RuntimeError("[RTMPose] Ön kamera videosunda iniş tespit edilemedi.")

    on_analysis_width = RTM_FRAME_WIDTH if RTM_NORMALIZE else on_w

    yan_results = rtm_evaluate_yan(yan_poses, jumps_yan, test_side)
    on_results  = rtm_evaluate_on(on_poses, jumps_on, test_side, on_analysis_width)
    combined    = rtm_combine_results(yan_results, on_results)

    total_score, skorlar, yaklasik_maddeler = rtm_compute_total_score(combined)

    csv_path         = output_dir / "rtm_less_sonuclar.csv"
    side_output_path = output_dir / "gorsel_analiz_yan.mp4"
    front_output_path = output_dir / "gorsel_analiz_on.mp4"

    _write_yolo_csv(str(csv_path), combined, skorlar, total_score, test_side,
                    yaklasik_maddeler, model="rtm")

    create_rtm_camera_video(
        side_video_path, yan_poses, jumps_yan, yan_results, "yan", str(side_output_path))
    create_rtm_camera_video(
        front_video_path, on_poses, jumps_on, on_results, "on", str(front_output_path))

    return {
        "total_score": total_score,
        "risk": score_to_risk(total_score),
        "csv_path": str(csv_path),
        "side_output_path": str(side_output_path),
        "front_output_path": str(front_output_path),
        "jumps_yan": jumps_yan,
        "jumps_on": jumps_on,
        "rtm_na_madde": sorted(RTM_NA_MADDE),
        "rtm_yaklasik_madde": yaklasik_maddeler,
        "pose_model": "rtm",
    }
