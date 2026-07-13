#!/usr/bin/env python3
"""Run the SPWIN v2.7.1 knockout market guard research replay."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spwin_engine.v271_knockout_guard import main as replay_main


if __name__ == "__main__":
    sys.exit(replay_main())
