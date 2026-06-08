#!/usr/bin/env python3
from pathlib import Path
import sys

SRC = Path("lib/screens/home_screen.dart")
if not SRC.exists():
    print("ERROR: lib/screens/home_screen.dart not found.")
    sys.exit(1)

text = SRC.read_text(encoding="utf-8")

OLD = (
    "      // Progress update\n"
    "      final msg = ev['msg'] as String? ?? '';\n"
    "      if (msg.isNotEmpty) setState(() { _localMsg = msg; _status = msg; });\n"
    "    }\n"
    "  }"
)

NEW = (
    "      // S-PROGRESS: advance bar from engine phase pct; never regress; cap at 98%\n"
    "      final pct = ev['pct'] as int? ?? -1;\n"
    "      final msg = ev['msg'] as String? ?? '';\n"
    "      setState(() {\n"
    "        if (pct > 0) _progress = (pct / 100.0).clamp(_progress, 0.98);\n"
    "        if (msg.isNotEmpty) { _localMsg = msg; _status = msg; }\n"
    "      });\n"
    "    }\n"
    "  }"
)

count = text.count(OLD)
if count == 0:
    print("ERROR: target block not found.")
    sys.exit(1)

text = text.replace(OLD, NEW, 1)
SRC.write_text(text, encoding="utf-8")
print(f"  home_screen.dart patched ({SRC.stat().st_size} bytes)")
