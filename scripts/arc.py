#!/usr/bin/env python3
"""Run directly from an extracted skill folder; installation is optional."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from oden_arc.cli import main
if __name__ == '__main__':
    raise SystemExit(main())
