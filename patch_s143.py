#!/usr/bin/env python3
"""
patch_s143.py — 4 bugs found in S143 deep scan
================================================

Bug-13 [CRITICAL — server-mode cancel leaks wake lock]
  S142 fixed local-mode cancel by wrapping release inside if (_localMode).
  But server-mode wake lock acquired in _startPolling() is only released
  inside the polling timer (on done/error). If user cancels while polling,
  _pollTimer?.cancel() stops the timer but the wake lock is never released.
  Fix: move release outside the if (_localMode) block so it always runs.

Bug-14 [CRITICAL — Share button crashes on local mode outputs]
  S142 Bug-9 showed the Share button when _localMode && _output != null.
  Local output paths are cacheDir file:// paths. _shareFile() passes the
  raw path to MainActivity shareFile handler → Uri.parse('/data/...') →
  a path-only URI. Android's ACTION_SEND + FLAG_GRANT_READ_URI_PERMISSION
  only works with content:// URIs. Other apps cannot access private cacheDir.
  Fix: keep Share button gated on hasContentUri only. Open in Player remains
  available for both modes (it uses launchUrl which handles file:// fine).

Bug-15 [LOGIC — _reDownload() discards saveToDownloads return value]
  _reDownload() local branch calls saveToDownloads and throws away the
  returned content:// MediaStore URI. Then does setState(() { _output = src; })
  which is a no-op (src IS _output). After saving, Open in Player opens
  the cacheDir temp file instead of the permanent Downloads copy.
  Fix: capture the returned URI and update _output to the Downloads copy.

Bug-16 [LOGIC — _openInPlayer() uses Uri.file() for content:// paths]
  For server-mode results _output!.path is a content:// URI.
  Uri.file('content://...') produces file:///content://... — an invalid URI
  that launchUrl cannot handle. Open in Player has silently failed for all
  server-mode results since S138.
  Fix: use Uri.parse() for content:// paths, Uri.file() for file paths.
"""
from pathlib import Path
from datetime import datetime
import sys

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

_log = []
def ok(l):  print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l):  print(f'  XX  NOT FOUND — {l}'); _log.append(('XX', l)); sys.exit(1)

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old in t:
        path.write_text(t.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else:
        xx(lbl)

print(f'\n{"="*60}\n  S143  {datetime.now().strftime("%H:%M:%S")}\n{"="*60}')

# ── Bug-13: server-mode cancel leaks wake lock ─────────────────────────────────
print(f'\n{"="*60}\n  Bug-13: release wake lock on any cancel (not just local)\n{"="*60}')
rep(HS,
    '    if (_localMode) {\n'
    '      LocalEngineService.cancelEngine(); // S140: stop proot process\n'
    '      _wakeCh.invokeMethod(\'release\').catchError((_) {}); // S142: release on local cancel\n'
    '    }\n'
    '    setState(() {\n'
    '      _busy = false; _progress = 0;\n'
    '      _status = \'\'; _isMerging = false;\n'
    '      _jobId = null;\n'
    '    });',

    '    if (_localMode) LocalEngineService.cancelEngine(); // S140: stop proot process\n'
    '    _wakeCh.invokeMethod(\'release\').catchError((_) {}); // S143: always release on any cancel\n'
    '    setState(() {\n'
    '      _busy = false; _progress = 0;\n'
    '      _status = \'\'; _isMerging = false;\n'
    '      _jobId = null;\n'
    '    });',
    'Bug-13 fixed: wake lock released on server-mode cancel')

# ── Bug-14: Share button crashes on local mode (revert to hasContentUri only) ──
print(f'\n{"="*60}\n  Bug-14: Share button — gate on hasContentUri only\n{"="*60}')

# 14a: spacer condition
rep(HS,
    '            if (hasContentUri || (_localMode && _output != null))\n'
    '              const SizedBox(width: 8), // S142: spacer shown when both buttons present',

    '            if (hasContentUri)\n'
    '              const SizedBox(width: 8), // S143: spacer only when Share shows',
    'Bug-14a fixed: spacer gated on hasContentUri only')

# 14b: Share button condition
rep(HS,
    '            if (hasContentUri || (_localMode && _output != null)) Expanded( // S142\n'
    '              child: OutlinedButton.icon(\n'
    '                onPressed: _shareFile,',

    '            if (hasContentUri) Expanded( // S143: share requires content:// URI — local paths crash API24+\n'
    '              child: OutlinedButton.icon(\n'
    '                onPressed: _shareFile,',
    'Bug-14b fixed: Share button gated on hasContentUri only')

# ── Bug-15: _reDownload() discards saveToDownloads return URI ──────────────────
print(f'\n{"="*60}\n  Bug-15: capture saveToDownloads URI → update _output to Downloads copy\n{"="*60}')
rep(HS,
    '        const mediaChannel = MethodChannel(\'com.tilawa.tilawa_enhancer/media\'); // S141: was /wake\n'
    '        await mediaChannel.invokeMethod<String>(\n'
    '          \'saveToDownloads\', {\'path\': src.path, \'filename\': fname});\n'
    '        if (!mounted) return;\n'
    '        setState(() { _output = src; });',

    '        const mediaChannel = MethodChannel(\'com.tilawa.tilawa_enhancer/media\'); // S141: was /wake\n'
    '        final contentUri = await mediaChannel.invokeMethod<String>(\n'
    '          \'saveToDownloads\', {\'path\': src.path, \'filename\': fname});\n'
    '        if (!mounted) return;\n'
    '        // S143: update _output to the Downloads copy so Open/Share use the permanent file\n'
    '        if (contentUri != null && contentUri.startsWith(\'content://\')) {\n'
    '          setState(() { _output = File(contentUri); });\n'
    '        } else {\n'
    '          setState(() { _output = src; }); // fallback: API <29 returns file path\n'
    '        }',
    'Bug-15 fixed: _reDownload() updates _output to Downloads content:// URI')

# ── Bug-16: _openInPlayer() uses Uri.file() for content:// paths ───────────────
print(f'\n{"="*60}\n  Bug-16: Uri.parse() for content://, Uri.file() for local paths\n{"="*60}')
rep(HS,
    '      final uri = Uri.file(_output!.path); // S138: Uri.file for local paths',

    '      final uri = _output!.path.startsWith(\'content://\')\n'
    '          ? Uri.parse(_output!.path)   // S143: content:// from MediaStore\n'
    '          : Uri.file(_output!.path);   // local cacheDir path',
    'Bug-16 fixed: Uri.parse() used for content:// URIs in _openInPlayer()')

# ── Summary ────────────────────────────────────────────────────────────────────
print(f'\n{"="*60}')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  " + str(xx_n) + " FAILED"}  {ok_n} OK\n')
print('  git add -A && git commit -m "S143: 4 bugs — server cancel wake lock, share crash, reDownload URI, openInPlayer URI" && git push')
