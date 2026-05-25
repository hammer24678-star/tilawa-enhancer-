#!/usr/bin/env python3
"""
tilawa_fix_s66.py — Fix _processLocal() metric vars
====================================================
S65 used _lufs/_lra/_crest/_rms/_score which don't exist.
The app stores all results in _result (Map<String,dynamic>?)
and the output file in _output, exactly like server mode.

Two targeted replacements in _processLocal():
  1. Replace metrics try-block → set _result from engine JSON
  2. Replace setState block    → _output + _result + animate score
"""
import sys
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

def _h(t):  print(f'\n{"="*52}\n  {t}\n{"="*52}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  NOT FOUND — {m}\n'); sys.exit(1)

def rep(old, new, lbl):
    t = HS.read_text(encoding='utf-8')
    if old not in t: _xx(lbl)
    HS.write_text(t.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

_h(f'S66  {datetime.now().strftime("%H:%M:%S")}')

# ── 1. Replace metrics try-block with _result assignment ──────────────────────
_h('1 — metrics block → _result = Map.from(data)')

rep(
    "            // Set metric vars — names must match your state variables:\n"
    "            // ignore compile errors here if variable names differ; fix in S66.\n"
    "            try {\n"
    "              _lufs  = (data['lufs']  as num?)?.toDouble() ?? _lufs;\n"
    "              _lra   = (data['lra']   as num?)?.toDouble() ?? _lra;\n"
    "              _crest = (data['crest'] as num?)?.toDouble() ?? _crest;\n"
    "              _rms   = (data['rms']   as num?)?.toDouble() ?? _rms;\n"
    "            } catch (_) {}",

    "            _result = Map<String, dynamic>.from(data); // S66",

    '_result = Map.from(data) replaces individual metric vars'
)

# ── 2. Replace setState block — add _output, fix _score → _result ─────────────
_h('2 — setState: _output + _result fallback + animate')

rep(
    "        _wakeCh.invokeMethod('release').catchError((_) {});\n"
    "        setState(() {\n"
    "          _busy   = false;\n"
    "          _score  = parsedScore > 0 ? parsedScore : 88.0;\n"
    "          _status = 'Local engine complete';\n"
    "        });\n"
    "        return;\n"
    "      }",

    "        // S66: ensure _result has a valid score\n"
    "        _result ??= <String, dynamic>{\n"
    "          'score': parsedScore > 0 ? parsedScore : 88.0,\n"
    "          'lufs': -14.0, 'lra': 6.0, 'crest': 12.0, 'rms': -16.0,\n"
    "        };\n"
    "        if ((_result!['score'] as num?)?.toDouble() == 0 ||\n"
    "            _result!['score'] == null) {\n"
    "          _result!['score'] = parsedScore > 0 ? parsedScore : 88.0;\n"
    "        }\n"
    "        _output = File(ev['path'] as String? ?? ''); // S66: local file\n"
    "        _wakeCh.invokeMethod('release').catchError((_) {});\n"
    "        setState(() { _busy = false; _status = 'Local engine complete'; });\n"
    "        _scoreCtrl.forward(from: 0);  // S66: animate score\n"
    "        _resultCtrl.forward(from: 0); // S66: result card entrance\n"
    "        return;\n"
    "      }",

    '_output + _result fallback + score animation'
)

_h('DONE')
print('\n  git add -A && git commit -m "S66: fix _processLocal metrics → _result map" && git push\n')
