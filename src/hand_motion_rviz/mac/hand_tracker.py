"""Compatibility entry point; the shared tracker now lives in ../tracker/."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    tracker = Path(__file__).resolve().parents[1] / 'tracker' / 'hand_tracker.py'
    sys.path.insert(0, str(tracker.parent))
    runpy.run_path(str(tracker), run_name='__main__')
