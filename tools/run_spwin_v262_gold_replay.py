#!/usr/bin/env python3
"""Run SPWIN v2.6.2 experimental tiered Gold benchmark replay."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spwin_engine.v262 import main as replay_main

if __name__ == "__main__":
    sys.exit(replay_main())
