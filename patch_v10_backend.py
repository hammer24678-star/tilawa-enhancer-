#!/usr/bin/env python3
"""
patch_v10_backend.py — Update HF Space app.py
  Add v10.0, remove v8.9 from ENGINE_SCRIPTS
Run this from your HF Space repo directory.
"""

from pathlib import Path
import sys

APP = Path("app.py")
OK  = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"

def patch(old, new, label):
    text = APP.read_text(encoding="utf-8")
    if old not in text:
        print(f"{WARN} anchor not found — {label}"); return False
    if new.split('\n')[0] in text:
        print(f"{SKIP} already applied — {label}"); return True
    APP.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{OK}  {label}")
    return True

print("\n[app.py — ENGINE_SCRIPTS]")

patch(
    'ENGINE_SCRIPTS = {\n'
    '    "v9.0": BASE / "engine_v90.py",\n'
    '    "v8.9": BASE / "engine_v89.py",',
    'ENGINE_SCRIPTS = {\n'
    '    "v10.0": BASE / "engine_v100.py",  # S31: Aetherion Foundation\n'
    '    "v9.0": BASE / "engine_v90.py",',
    "ENGINE_SCRIPTS: v10.0 added, v8.9 removed"
)

print()
print("=" * 60)
print("\033[92m Done \033[0m")
print()
print("Now push the engine file and this change to HF Space:")
print("  cp /sdcard/Download/engine_v10_base.py ./engine_v100.py")
print("  git add app.py engine_v100.py")
print("  git commit -m 'S31: Add v10.0 engine, remove v8.9'")
print("  git push")
