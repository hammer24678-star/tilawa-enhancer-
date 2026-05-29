#!/usr/bin/env python3
"""
tilawa_fix_upload_hang.py — Fix upload stuck at 2%
====================================================
Root cause: _uploadDirectTo() calls res.stream.bytesToString()
with NO timeout. Connection opens but server never finishes
sending the response body → hangs forever at 2%.

Fixes:
  1. Add .timeout(30s) to bytesToString()
  2. Pass onProgress into _uploadDirectTo
  3. Show 'جار الرفع...' before entering direct upload
  4. Show retry message on each attempt
"""
import sys
from pathlib import Path
from datetime import datetime

AS = Path.home() / 'tilawa-enhancer/lib/services/api_service.dart'

def _h(t):  print(f'\n{"="*52}\n  {t}\n{"="*52}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  NOT FOUND — {m}\n'); sys.exit(1)

def rep(old, new, lbl):
    t = AS.read_text(encoding='utf-8')
    if old not in t: _xx(lbl)
    AS.write_text(t.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

_h(f'upload-hang fix  {datetime.now().strftime("%H:%M:%S")}')

# ── 1. bytesToString timeout ──────────────────────────────────────────────────
_h('1 — bytesToString: add 30s timeout')
rep(
    '        final res = await req.send().timeout(const Duration(seconds: 60));\n'
    '        final body = await res.stream.bytesToString();',

    '        final res = await req.send().timeout(const Duration(seconds: 60));\n'
    '        final body = await res.stream\n'
    '            .bytesToString()\n'
    '            .timeout(const Duration(seconds: 30)); // FIX: was no timeout',

    'bytesToString: 30s timeout'
)

# ── 2. _uploadDirectTo signature ─────────────────────────────────────────────
_h('2 — _uploadDirectTo: add onProgress param')
rep(
    '  static Future<Map<String, dynamic>> _uploadDirectTo(\n'
    '      File file, String engine, String server) async {',

    '  static Future<Map<String, dynamic>> _uploadDirectTo(\n'
    '      File file, String engine, String server, {\n'
    '      void Function(double, String)? onProgress}) async {',

    '_uploadDirectTo: onProgress param'
)

# ── 3. uploadFile: pass onProgress + uploading status ────────────────────────
_h('3 — uploadFile: pass onProgress to direct upload')
rep(
    "    // S65: small files (<5MB) get priority direct upload\n"
    "    if (size <= 5 * 1024 * 1024) {\n"
    "      return _uploadDirectTo(file, engine, server);\n"
    "    }",

    "    // S65: small files (<5MB) get priority direct upload\n"
    "    if (size <= 5 * 1024 * 1024) {\n"
    "      onProgress?.call(0.02, '\u062c\u0627\u0631 \u0627\u0644\u0631\u0641\u0639...');\n"
    "      return _uploadDirectTo(file, engine, server, onProgress: onProgress);\n"
    "    }",

    'uploadFile: onProgress passed + uploading status set'
)

# ── 4. Retry message in _uploadDirectTo ──────────────────────────────────────
_h('4 — _uploadDirectTo: retry message')
rep(
    "    for (int attempt = 0; attempt < 3; attempt++) {\n"
    "      try {\n"
    "        final req = http.MultipartRequest('POST', Uri.parse('$server/upload'));",

    "    for (int attempt = 0; attempt < 3; attempt++) {\n"
    "      try {\n"
    "        if (attempt > 0) onProgress?.call(0.02, '\u0625\u0639\u0627\u062f\u0629 \u0645\u062d\u0627\u0648\u0644\u0629 \u0627\u0644\u0631\u0641\u0639 \u0623\u062b\u0646\u0627\u0621 \u0627\u0644\u0634\u0628\u0643\u0629...');\n"
    "        final req = http.MultipartRequest('POST', Uri.parse('$server/upload'));",

    '_uploadDirectTo: retry message'
)

_h('DONE')
print('\n  git add -A && git commit -m "fix upload hang: bytesToString timeout + onProgress" && git push\n')
