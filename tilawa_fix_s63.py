#!/usr/bin/env python3
"""
tilawa_fix_s63.py — S63: CPU PARTIAL_WAKE_LOCK via MethodChannel
  1. patch_android.py — add wake lock channel to MainActivity.kt
  2. home_screen.dart — acquire on poll start, release on done/error
"""
import sys
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
PA = Path.home() / 'tilawa-enhancer/patch_android.py'

def _h(t): print(f'\n{"="*54}\n  {t}\n{"="*54}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  NOT FOUND — {m}\n'); sys.exit(1)

def rep(f, old, new, lbl):
    t = f.read_text(encoding='utf-8')
    if old not in t: _xx(lbl)
    f.write_text(t.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

_h(f'S63  {datetime.now().strftime("%H:%M:%S")}')

# ── 1. patch_android.py — add wake lock MethodChannel ────────────
_h('1 — patch_android.py: wake lock channel')
rep(PA,
    '\'                else -> result.notImplemented()\\n\'\n'
    '\'            }\\n\'\n'
    '\'        }\\n\'\n'
    '\'    }\\n\'\n'
    '\'}\\n\'\n'
    ')',

    '\'                else -> result.notImplemented()\\n\'\n'
    '\'            }\\n\'\n'
    '\'        }\\n\'\n'
    '\'\\n\'\n'
    '\'        // S63: CPU wake lock — keeps polling alive with screen off\\n\'\n'
    '\'        var _wl: android.os.PowerManager.WakeLock? = null\\n\'\n'
    '\'        MethodChannel(\\n\'\n'
    '\'            flutterEngine.dartExecutor.binaryMessenger,\\n\'\n'
    '\'            "com.tilawa.tilawa_enhancer/wake"\\n\'\n'
    '\'        ).setMethodCallHandler { call, result ->\\n\'\n'
    '\'            val pm = getSystemService(POWER_SERVICE) as android.os.PowerManager\\n\'\n'
    '\'            when (call.method) {\\n\'\n'
    '\'                "acquire" -> {\\n\'\n'
    '\'                    _wl?.let { if (it.isHeld) it.release() }\\n\'\n'
    '\'                    _wl = pm.newWakeLock(\\n\'\n'
    '\'                        android.os.PowerManager.PARTIAL_WAKE_LOCK,\\n\'\n'
    '\'                        "tilawa:processing"\\n\'\n'
    '\'                    ).also { it.acquire(10 * 60 * 1000L) }\\n\'\n'
    '\'                    result.success(null)\\n\'\n'
    '\'                }\\n\'\n'
    '\'                "release" -> {\\n\'\n'
    '\'                    _wl?.let { if (it.isHeld) it.release() }\\n\'\n'
    '\'                    _wl = null\\n\'\n'
    '\'                    result.success(null)\\n\'\n'
    '\'                }\\n\'\n'
    '\'                else -> result.notImplemented()\\n\'\n'
    '\'            }\\n\'\n'
    '\'        }\\n\'\n'
    '\'    }\\n\'\n'
    '\'}\\n\'\n'
    ')',
    'wake lock MethodChannel added to MainActivity.kt'
)

# ── 2. home_screen.dart — declare channel ────────────────────────
_h('2 — home_screen.dart: declare _wakeCh')
rep(HS,
    "  static const _serverUrl = ApiService.baseUrl;",
    "  static const _serverUrl = ApiService.baseUrl;\n"
    "  static const _wakeCh = MethodChannel('com.tilawa.tilawa_enhancer/wake'); // S63",
    '_wakeCh channel declared'
)

# ── 3. acquire on polling start ───────────────────────────────────
_h('3 — acquire wake lock when polling starts')
rep(HS,
    '    _pollErrors = 0; // S22: fresh counter for each new polling session\n'
    '    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {',
    '    _pollErrors = 0; // S22: fresh counter for each new polling session\n'
    '    _wakeCh.invokeMethod(\'acquire\').catchError((_) {}); // S63\n'
    '    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {',
    'wake lock acquire on poll start'
)

# ── 4. release on error ───────────────────────────────────────────
_h('4 — release on error')
rep(HS,
    "        if (status == 'error') {\n"
    "          _pollTimer?.cancel();\n"
    "          setState(() {\n"
    "            _busy = false;\n"
    "            _isMerging = false;  // S20-B: clear merge animation on server error",
    "        if (status == 'error') {\n"
    "          _pollTimer?.cancel();\n"
    "          _wakeCh.invokeMethod('release').catchError((_) {}); // S63\n"
    "          setState(() {\n"
    "            _busy = false;\n"
    "            _isMerging = false;  // S20-B: clear merge animation on server error",
    'wake lock release on error'
)

# ── 5. release on done ────────────────────────────────────────────
_h('5 — release on done')
rep(HS,
    "        if (status == 'done') {\n"
    "          _pollTimer?.cancel();\n"
    "          if (_downloading) return; // RC3",
    "        if (status == 'done') {\n"
    "          _pollTimer?.cancel();\n"
    "          _wakeCh.invokeMethod('release').catchError((_) {}); // S63\n"
    "          if (_downloading) return; // RC3",
    'wake lock release on done'
)

_h('DONE')
print('\n  git add -A && git commit -m "S63: CPU wake lock — polling survives screen off" && git push\n')
