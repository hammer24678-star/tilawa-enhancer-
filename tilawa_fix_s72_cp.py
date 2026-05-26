#!/usr/bin/env python3
"""
tilawa_fix_s72_cp.py  —  fix cp same-file error in build_assets.sh
Run:
  cp /sdcard/Download/tilawa_fix_s72_cp.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s72_cp.py
  git add build_assets.sh
  git commit -m "S72: fix cp same-file error for deep-filter"
  git push
"""
from pathlib import Path

f = Path.home() / 'tilawa-enhancer/build_assets.sh'
txt = f.read_text()

OLD = 'cp "$GITHUB_WORKSPACE/assets/alpine/deep-filter" "$ASSETS/deep-filter"'
NEW = '[ "$GITHUB_WORKSPACE/assets/alpine/deep-filter" != "$ASSETS/deep-filter" ] && cp "$GITHUB_WORKSPACE/assets/alpine/deep-filter" "$ASSETS/deep-filter" || true'

if OLD not in txt:
    print("XX anchor not found — printing deep-filter lines:")
    for i, l in enumerate(txt.splitlines(), 1):
        if 'deep-filter' in l or 'DeepFilter' in l:
            print(f"  {i}: {l}")
else:
    f.write_text(txt.replace(OLD, NEW, 1))
    print("OK build_assets.sh patched")
