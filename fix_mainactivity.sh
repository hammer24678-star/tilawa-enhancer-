#!/bin/bash
# Fix: MainActivity package mismatch
# flutter create generates: package com.example.tilawa_enhancer
# manifest expects:         com.tilawa.tilawa_enhancer.MainActivity
# This 1-line mismatch = ClassNotFoundException = instant crash before any Flutter code
#
# Run: cd ~/tilawa-enhancer && bash /sdcard/Download/fix_mainactivity.sh

cd ~/tilawa-enhancer

# Add a new step to build.yml AFTER "Regenerate android/" and BEFORE "Patch android/"
python3 - << 'EOF'
from pathlib import Path

f = Path(".github/workflows/build.yml")
txt = f.read_text()

fix_step = """
      - name: Fix MainActivity package
        run: |
          OLD="android/app/src/main/kotlin/com/example/tilawa_enhancer"
          NEW="android/app/src/main/kotlin/com/tilawa/tilawa_enhancer"
          mkdir -p "$NEW"
          mv "$OLD/MainActivity.kt" "$NEW/MainActivity.kt"
          sed -i 's/package com.example.tilawa_enhancer/package com.tilawa.tilawa_enhancer/' "$NEW/MainActivity.kt"
          echo "MainActivity.kt package fixed:"
          head -1 "$NEW/MainActivity.kt"
"""

target = "      - name: Patch android/ v6"
if fix_step.strip() not in txt:
    txt = txt.replace(target, fix_step + target)
    f.write_text(txt)
    print("✅ Fix step added to build.yml")
else:
    print("✅ Already fixed")
EOF

git add .github/workflows/build.yml
git commit -m "fix: move MainActivity.kt to correct package — stops ClassNotFoundException crash"
git push

echo ""
echo "Done — https://github.com/c42742910-ops/tilawa-enhancer/actions"
