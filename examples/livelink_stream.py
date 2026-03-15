"""Example: stream a saved lens profile to Unreal over UDP."""

from pathlib import Path
import time

from src.calibration import LensProfile
from src.livelink_emitter import LiveLinkEmitter


profile = LensProfile.load_json(Path("./my_lens.json"))
emitter = LiveLinkEmitter(target_ip="192.168.1.100", port=11111)

try:
    emitter.start_streaming(profile, fps=24)
    time.sleep(5.0)
finally:
    emitter.close()
