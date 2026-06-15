import sys
import os
import traceback
from pathlib import Path

# Add src to python path if needed
sys.path.append(os.path.abspath("."))

from src.athletes.analysis_service import run_rtm_less_analysis

side_video = "/Users/baharcakir/capstone/capstone_last/backend/media/athletes/ATH_4FA18EB1C07C/shared_inputs/yan_kamera.mp4"
front_video = "/Users/baharcakir/capstone/capstone_last/backend/media/athletes/ATH_4FA18EB1C07C/shared_inputs/on_kamera.mp4"
output_dir = Path("media/athletes/ATH_4FA18EB1C07C/ANL_3BDA991DC05B/test_outputs").resolve()

try:
    print("Starting RTMPose analysis test...")
    res = run_rtm_less_analysis(side_video, front_video, output_dir, test_side="right")
    print("Analysis success! Result:", res)
except Exception as e:
    print("Analysis failed with error:")
    traceback.print_exc()
