#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IZCIVSwitch entry point.

The implementation lives in run-fs.py; this wrapper keeps the branded command
and forwards every argument unchanged.
"""
from __future__ import annotations

import pathlib
import runpy
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "run-fs.py"
if not TARGET.is_file():
    raise SystemExit("run-fs.py not found next to IZCIVSwitch.py")
sys.argv[0] = str(HERE / "IZCIVSwitch.py")
runpy.run_path(str(TARGET), run_name="__main__")
