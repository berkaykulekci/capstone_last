"""
Benchmark - Reporter
İki CSV dosyası üretir:
  1. summary_results.csv   — video × model bazında özet metrikler
  2. per_frame_results.csv — her frame için detay satırı
"""
import os
import csv
import numpy as np
from typing import List, Dict, Any


# ── Sütun tanımları ───────────────────────────────────────────────────────────

SUMMARY_FIELDS = [
    'video',
    'model',
    'total_frames',
    'fps',
    'latency_ms',
    'missing_kp_pct',
    'jitter_coord_std',
    'jitter_accel_mean',
    'limb_self_std',
    'limb_anthropo_pct',
    'biomech_self_std',
    'biomech_anthropo_pct',
    'mean_confidence',
]

PER_FRAME_FIELDS = [
    'video',
    'model',
    'frame_idx',
    'inference_time_ms',
    'n_missing_kp',
    'jitter_coord',
    'jitter_accel',
    'femur_len',
    'tibia_len',
    'knee_angle',
    'hip_angle',
    'mean_confidence',
]


def _fmt(v, decimals: int = 4) -> str:
    """NaN ve None değerleri boş string; sayıları yuvarla."""
    if v is None:
        return ''
    if isinstance(v, float) and np.isnan(v):
        return ''
    if isinstance(v, float):
        return f'{v:.{decimals}f}'
    return str(v)


def write_summary_csv(results: List[Dict[str, Any]], output_path: str) -> None:
    """
    Parameters
    ----------
    results     : Her eleman bir model+video çalışmasının özet sonuçlarını içerir.
    output_path : CSV dosyasının tam yolu.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS, extrasaction='ignore')
        writer.writeheader()
        for row in results:
            writer.writerow({k: _fmt(row.get(k)) for k in SUMMARY_FIELDS})
    print(f'  ✓ Summary CSV → {output_path}  ({len(results)} satır)')


def write_per_frame_csv(frame_rows: List[Dict[str, Any]], output_path: str) -> None:
    """
    Parameters
    ----------
    frame_rows  : Her eleman bir frame için detay satırını içerir.
    output_path : CSV dosyasının tam yolu.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=PER_FRAME_FIELDS, extrasaction='ignore')
        writer.writeheader()
        for row in frame_rows:
            writer.writerow({k: _fmt(row.get(k)) for k in PER_FRAME_FIELDS})
    print(f'  ✓ Per-frame CSV → {output_path}  ({len(frame_rows)} satır)')
