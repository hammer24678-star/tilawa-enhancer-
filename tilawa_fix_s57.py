#!/usr/bin/env python3
"""
tilawa_fix_s57.py — Persist _jobId across app kills
=====================================================
Saves job_id to SharedPreferences when set, clears on done/cancel.
On initState, restores job_id and resumes polling if found.
Combined with S56 (WidgetsBindingObserver), enhancement now survives
both backgrounding AND full app kill+restart.

Patches:
  A  ApiService: add saveJobId / loadJobId / clearJobId
  B  home_screen: save job_id after upload succeeds
  C  home_screen: clear job_id on cancel/reset
  D  home_screen: restore job_id in initState and resume polling
"""
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
API = Path.home() / 'tilawa-enhancer/lib/services/api_service.dart'
_log = []

def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(path, old, new, lbl):
    txt = path.read_text(encoding='utf-8')
    if old in txt:
        path.write_text(txt.replace(old, new, 1), encoding='utf-8')
        ok(lbl)
    else:
        xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s57  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# ── A: ApiService — add saveJobId / loadJobId / clearJobId ──────────────────
rep(API,
    "    }  // ── Upload — auto-selects direct or chunked ────────────────────────────────",

    "    }\n"
    "\n"
    "  // S57: persist active job_id so app-kill doesn't lose in-progress jobs\n"
    "  static const _activeJobKey = 'active_job_id_v1';\n"
    "  static const _activeEngineKey = 'active_job_engine_v1';\n"
    "\n"
    "  static Future<void> saveJobId(String jobId, String engine) async {\n"
    "    try {\n"
    "      final prefs = await SharedPreferences.getInstance();\n"
    "      await prefs.setString(_activeJobKey, jobId);\n"
    "      await prefs.setString(_activeEngineKey, engine);\n"
    "    } catch (_) {}\n"
    "  }\n"
    "\n"
    "  static Future<void> clearJobId() async {\n"
    "    try {\n"
    "      final prefs = await SharedPreferences.getInstance();\n"
    "      await prefs.remove(_activeJobKey);\n"
    "      await prefs.remove(_activeEngineKey);\n"
    "    } catch (_) {}\n"
    "  }\n"
    "\n"
    "  static Future<Map<String, String>?> loadJobId() async {\n"
    "    try {\n"
    "      final prefs = await SharedPreferences.getInstance();\n"
    "      final jobId  = prefs.getString(_activeJobKey);\n"
    "      final engine = prefs.getString(_activeEngineKey) ?? 'v10.0';\n"
    "      if (jobId != null && jobId.isNotEmpty) {\n"
    "        return {'job_id': jobId, 'engine': engine};\n"
    "      }\n"
    "    } catch (_) {}\n"
    "    return null;\n"
    "  }\n"
    "\n"
    "    // ── Upload — auto-selects direct or chunked ────────────────────────────────",
    'Fix-A ApiService saveJobId / loadJobId / clearJobId')

# ── B: save job_id right after upload returns ────────────────────────────────
rep(HS,
    "        _jobId = resp['job_id'];\n"
    "        _startPolling();",

    "        _jobId = resp['job_id'];\n"
    "        ApiService.saveJobId(_jobId!, _engine); // S57: persist across kills\n"
    "        _startPolling();",
    'Fix-B save job_id after upload')

# ── C: clear persisted job_id on cancel and reset ───────────────────────────
rep(HS,
    "        _busy = false; _progress = 0;\n"
    "        _status = ''; _isMerging = false;\n"
    "        _jobId = null;\n"
    "      });\n"
    "    }\n"
    "\n"
    "    // ── S28: Reset for new file",

    "        _busy = false; _progress = 0;\n"
    "        _status = ''; _isMerging = false;\n"
    "        _jobId = null;\n"
    "        ApiService.clearJobId(); // S57\n"
    "      });\n"
    "    }\n"
    "\n"
    "    // ── S28: Reset for new file",
    'Fix-C clear job_id on cancel')

rep(HS,
    "        _file = null; _result = null; _output = null;\n"
    "        _progress = 0; _status = '';\n"
    "        _jobId = null; _busy = false;",

    "        _file = null; _result = null; _output = null;\n"
    "        _progress = 0; _status = '';\n"
    "        _jobId = null; _busy = false;\n"
    "        ApiService.clearJobId(); // S57",
    'Fix-C2 clear job_id on reset')

# ── D: restore job_id in initState, resume polling if found ─────────────────
rep(HS,
    "    // S30-F1: restored — one loadLastEngine call\n"
    "    ApiService.loadLastEngine().then((e) {\n"
    "      if (mounted) setState(() => _engine = e);\n"
    "    });",

    "    // S30-F1: restored — one loadLastEngine call\n"
    "    ApiService.loadLastEngine().then((e) {\n"
    "      if (mounted) setState(() => _engine = e);\n"
    "    });\n"
    "    // S57: restore in-progress job after app kill\n"
    "    ApiService.loadJobId().then((saved) {\n"
    "      if (!mounted || saved == null) return;\n"
    "      setState(() {\n"
    "        _jobId  = saved['job_id'];\n"
    "        _engine = saved['engine'] ?? _engine;\n"
    "        _busy   = true;\n"
    "        _status = 'استئناف المعالجة...';\n"
    "        _progress = 0.35;\n"
    "        _processStart = DateTime.now();\n"
    "      });\n"
    "      _startPolling();\n"
    "    });",
    'Fix-D restore job_id in initState and resume polling')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S57: persist job_id across app kills -- resume enhancement after restart" && git push\n')
