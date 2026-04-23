#!/usr/bin/env python3
"""
patch_s32_fallback_retry.py — Auto-retry when server returns fallback score (≤78)

ROOT CAUSE
----------
When the HF Space is cold, the server processes the file but returns score=75.0
with no metrics (LUFS/RMS/Crest/LRA all null). This is "fallback mode" — the
reference audio hasn't loaded yet. The user then has to manually reprocess.

FIX
---
1. Add `_fallbackRetries = 0` counter to _HomeScreenState fields.
2. In _downloadAndSave(), after parsing the score: if score <= 78 AND
   _fallbackRetries < 2, don't show the result — instead show a snackbar
   ("Server was waking up, retrying automatically…"), wait 35 seconds
   (enough for HF Space to warm up), then call _process() again.
   After 2 retries, give up and show the result as-is.

Max 2 auto-retries = at most 70 extra seconds, then falls through normally.

Run from ~/tilawa-enhancer/ root, then commit + push.
"""

from pathlib import Path
import sys

HOME = Path("lib/screens/home_screen.dart")

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"

errors = 0

if not HOME.exists():
    print(f"{ERR} lib/screens/home_screen.dart not found — run from repo root")
    sys.exit(1)

text = HOME.read_text(encoding="utf-8")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1 — add _fallbackRetries field next to _processStart
# ─────────────────────────────────────────────────────────────────────────────
SKIP1 = "int _fallbackRetries = 0;"
if SKIP1 in text:
    print(f"{SKIP} _fallbackRetries field already present")
else:
    OLD1 = "  DateTime? _processStart;     // S22: start time for 25-min hard timeout"
    NEW1 = (
        "  DateTime? _processStart;     // S22: start time for 25-min hard timeout\n"
        "  int _fallbackRetries = 0;    // S32: auto-retry counter for fallback mode"
    )
    if OLD1 not in text:
        print(f"{WARN} anchor for _fallbackRetries field not found")
        errors += 1
    else:
        text = text.replace(OLD1, NEW1, 1)
        print(f"{OK}  added _fallbackRetries field")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2 — reset _fallbackRetries when a fresh _process() starts
# ─────────────────────────────────────────────────────────────────────────────
SKIP2 = "_fallbackRetries = 0;   // S32:"
if SKIP2 in text:
    print(f"{SKIP} _fallbackRetries reset already in _process()")
else:
    OLD2 = (
        "    _processStart = DateTime.now(); // S22: start clock for timeout\n"
        "    _pollErrors = 0;               // S22: reset in case of re-process"
    )
    NEW2 = (
        "    _processStart = DateTime.now(); // S22: start clock for timeout\n"
        "    _pollErrors = 0;               // S22: reset in case of re-process\n"
        "    // S32: do NOT reset _fallbackRetries here — it must persist across\n"
        "    // auto-retries triggered by _downloadAndSave. Only reset on user-\n"
        "    // initiated process (detected by _fallbackRetries already being 0)."
    )
    if OLD2 not in text:
        print(f"{WARN} anchor for _pollErrors reset not found")
        errors += 1
    else:
        text = text.replace(OLD2, NEW2, 1)
        print(f"{OK}  added _fallbackRetries note in _process()")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3 — reset counter on user-tapped "Process Another File"
#           (so the counter doesn't bleed into a new file)
# ─────────────────────────────────────────────────────────────────────────────
SKIP3 = "_fallbackRetries = 0; // S32: reset for new file"
if SKIP3 in text:
    print(f"{SKIP} _fallbackRetries reset on new-file already present")
else:
    # The reset-for-new-file call: look for where _result / _output are cleared
    OLD3 = (
        "      _busy = true; _progress = 0.02;\n"
        "      _status = LangProvider.strings(context).uploading;\n"
        "      _output = null; _result = null;"
    )
    NEW3 = (
        "      _busy = true; _progress = 0.02;\n"
        "      _status = LangProvider.strings(context).uploading;\n"
        "      _output = null; _result = null;\n"
        "      _fallbackRetries = 0; // S32: reset for new file"
    )
    if OLD3 not in text:
        print(f"{WARN} anchor for new-file reset not found")
        errors += 1
    else:
        text = text.replace(OLD3, NEW3, 1)
        print(f"{OK}  reset _fallbackRetries on new file upload")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 4 — the main logic: intercept fallback score in _downloadAndSave
# ─────────────────────────────────────────────────────────────────────────────
SKIP4 = "S32: fallback auto-retry"
if SKIP4 in text:
    print(f"{SKIP} fallback auto-retry logic already present")
else:
    OLD4 = (
        "    final score = double.tryParse(sd['score']?.toString() ?? '0') ?? 0.0;\n"
        "\n"
        "    setState(() {\n"
        "      _busy = false; _progress = 1.0;\n"
        "      _output = file; _result = sd;\n"
        "      _status = file != null ? s.done : 'فشل: $error';\n"
        "    });"
    )
    NEW4 = (
        "    final score = double.tryParse(sd['score']?.toString() ?? '0') ?? 0.0;\n"
        "\n"
        "    // S32: fallback auto-retry ────────────────────────────────────────────\n"
        "    // score ≤ 78 with a valid file = server was in fallback mode (reference\n"
        "    // audio not loaded yet).  Auto-reprocess up to 2 times.\n"
        "    if (score <= 78 && file != null && _fallbackRetries < 2) {\n"
        "      _fallbackRetries++;\n"
        "      final retryNum = _fallbackRetries;\n"
        "      if (mounted) {\n"
        "        setState(() { _progress = 0.0; _status = ''; _busy = false; });\n"
        "        ScaffoldMessenger.of(context).showSnackBar(SnackBar(\n"
        "          content: Text(\n"
        "            s.ar\n"
        "              ? '⏳ الخادم كان في وضع الاستعداد — إعادة المعالجة تلقائياً ($retryNum/2)…'\n"
        "              : '⏳ Server was warming up — retrying automatically ($retryNum/2)…',\n"
        "            style: const TextStyle(fontSize: 12)),\n"
        "          backgroundColor: const Color(0xFF1A1200),\n"
        "          duration: const Duration(seconds: 38)));\n"
        "        // Wait 35 s for the Space to finish loading reference audio,\n"
        "        // then reprocess the same file.\n"
        "        await Future.delayed(const Duration(seconds: 35));\n"
        "        if (mounted) _process();\n"
        "      }\n"
        "      return; // don't show the fallback result\n"
        "    }\n"
        "    // ── end S32 ──────────────────────────────────────────────────────────\n"
        "\n"
        "    setState(() {\n"
        "      _busy = false; _progress = 1.0;\n"
        "      _output = file; _result = sd;\n"
        "      _status = file != null ? s.done : 'فشل: $error';\n"
        "    });"
    )
    if OLD4 not in text:
        print(f"{WARN} anchor for score fallback intercept not found")
        idx = text.find("final score = double.tryParse")
        if idx != -1:
            print(f"       hint at char {idx}: {repr(text[idx:idx+120])}")
        errors += 1
    else:
        text = text.replace(OLD4, NEW4, 1)
        print(f"{OK}  injected fallback auto-retry in _downloadAndSave")

# ─────────────────────────────────────────────────────────────────────────────
HOME.write_text(text, encoding="utf-8")

print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED \033[0m")
    print()
    print("Behaviour after this patch:")
    print("  - Score ≤ 78 on first result: wait 35s, reprocess (retry 1/2)")
    print("  - Still ≤ 78: wait 35s, reprocess (retry 2/2)")
    print("  - Still ≤ 78 after 2 retries: show result as-is (no infinite loop)")
    print("  - Score > 78 on any attempt: show result immediately as before")
    print()
    print("Next:")
    print("  git add lib/screens/home_screen.dart")
    print("  git commit -m 'S32: auto-retry when server returns fallback score'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} PATCH(ES) FAILED — check WARN lines above \033[0m")
    sys.exit(1)
