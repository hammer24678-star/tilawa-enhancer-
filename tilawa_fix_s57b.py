#!/usr/bin/env python3
"""tilawa_fix_s57b — correct anchors for all 4 failing patches"""
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
API = Path.home() / 'tilawa-enhancer/lib/services/api_service.dart'
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(path, old, new, lbl):
    txt = path.read_text(encoding='utf-8')
    if old in txt: path.write_text(txt.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s57b  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# Fix-A: ApiService — 2sp indent, closing brace has no gap before //
rep(API,
    "  }  // ── Upload — auto-selects direct or chunked ────────────────────────────────",

    "  }\n"
    "\n"
    "  // S57: persist active job_id so app-kill never loses in-progress jobs\n"
    "  static const _activeJobKey    = 'active_job_id_v1';\n"
    "  static const _activeEngineKey = 'active_job_engine_v1';\n"
    "\n"
    "  static Future<void> saveJobId(String jobId, String engine) async {\n"
    "    try {\n"
    "      final prefs = await SharedPreferences.getInstance();\n"
    "      await prefs.setString(_activeJobKey,    jobId);\n"
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
    "      if (jobId != null && jobId.isNotEmpty) return {'job_id': jobId, 'engine': engine};\n"
    "    } catch (_) {}\n"
    "    return null;\n"
    "  }\n"
    "\n"
    "  // ── Upload — auto-selects direct or chunked ────────────────────────────────",
    'Fix-A ApiService saveJobId / loadJobId / clearJobId')

# Fix-B: save job_id after upload
rep(HS,
    "      _jobId = resp['job_id'];\n"
    "      _startPolling();",

    "      _jobId = resp['job_id'];\n"
    "      ApiService.saveJobId(_jobId!, _engine); // S57\n"
    "      _startPolling();",
    'Fix-B save job_id after upload')

# Fix-C: clear on cancel
rep(HS,
    "      _busy = false; _progress = 0;\n"
    "      _status = ''; _isMerging = false;\n"
    "      _jobId = null;\n"
    "    });",

    "      _busy = false; _progress = 0;\n"
    "      _status = ''; _isMerging = false;\n"
    "      _jobId = null;\n"
    "    });\n"
    "    ApiService.clearJobId(); // S57",
    'Fix-C clear job_id on cancel')

# Fix-C2: clear on reset
rep(HS,
    "      _file = null; _result = null; _output = null;\n"
    "      _progress = 0; _status = '';\n"
    "      _jobId = null; _busy = false;\n"
    "      _isMerging = false; _sizeLabel = '';\n"
    "      _isLarge = false; _fileBytes = 0;\n"
    "    });",

    "      _file = null; _result = null; _output = null;\n"
    "      _progress = 0; _status = '';\n"
    "      _jobId = null; _busy = false;\n"
    "      _isMerging = false; _sizeLabel = '';\n"
    "      _isLarge = false; _fileBytes = 0;\n"
    "    });\n"
    "    ApiService.clearJobId(); // S57",
    'Fix-C2 clear job_id on reset')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S57: persist job_id across app kills -- resume enhancement after restart" && git push\n')
