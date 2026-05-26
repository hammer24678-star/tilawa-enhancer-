#!/usr/bin/env python3
"""
tilawa_fix_s73_revert.py  —  revert S73 YAML edits
Run:
  cp /sdcard/Download/tilawa_fix_s73_revert.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s73_revert.py
  git add -A && git commit -m "revert S73: restore release build + keystore" && git push
"""
from pathlib import Path
import re

ROOT = Path.home() / 'tilawa-enhancer'
wf_dir = ROOT / '.github/workflows'
wf_files = list(wf_dir.glob('*.yml')) + list(wf_dir.glob('*.yaml'))
wf = wf_files[0]
txt = wf.read_text()

# 1. --debug back to --release
txt = re.sub(r'flutter build apk --debug(.*?)# S73', 'flutter build apk --release\\1', txt)

# 2. apk paths debug back to release
txt = re.sub(r'app-debug\.apk\s*# S73', 'app-release.apk', txt)
txt = re.sub(r'flutter-apk/app-debug\s*# S73', 'flutter-apk/app-release', txt)
txt = re.sub(r'outputs/apk/debug\s*# S73', 'outputs/apk/release', txt)

# 3. Restore commented-out keystore lines
txt = re.sub(r'\s*# S73-SKIP: ', '\n        ', txt)

wf.write_text(txt)
print(f'OK {wf.name} reverted')
print('Check it looks right:')
for i, l in enumerate(txt.splitlines(), 1):
    if 'keystore' in l.lower() or 'jks' in l.lower() or 'release' in l.lower() or 'debug' in l.lower():
        print(f'  {i}: {l}')
