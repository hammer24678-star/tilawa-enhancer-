#!/usr/bin/env python3
"""
patch_s176.py — S176: fix missing `break;` in _installHandler() switch
                  (lib/services/local_engine_service.dart)

Bug:
  switch (call.method) { case 'setupProgress': ... case 'setupDone': ... }
  has NO break/continue/return/throw at the end of any case body except
  the last ('engineError'). Dart's switch statement forbids implicit
  fall-through for non-empty case clauses — this is a compile-time error
  (case_block_not_terminated), so the file fails to build as-is.

Fix:
  Add `break;` at the end of each of the 5 affected case bodies
  (setupProgress, setupDone, setupError, engineProgress, engineDone).
  'engineError' is the last case and doesn't strictly need one, but a
  trailing break is added too for consistency/future-proofing.
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent  # run from repo root

def fail(msg):
    print(f'  FAIL  {msg}'); sys.exit(1)

def patch(path, old, new, tag):
    p = Path(path)
    if not p.exists(): fail(f'{path} not found')
    src = p.read_text(encoding='utf-8')
    if new.strip() in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        fail(f'{tag}: anchor not found in {path}')
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

# ── idempotency guard ─────────────────────────────────────────────────────────
STAMP = Path('.patch_s176_done')
if STAMP.exists():
    print('patch_s176: already applied — delete .patch_s176_done to re-run'); sys.exit(0)

print('\n── S176: fix switch fall-through in local_engine_service.dart ──────────────')

DART = Path('lib/services/local_engine_service.dart')

OLD = """      switch (call.method) {
        // Setup events
        case 'setupProgress':
          if (_setupCtrl != null && !_setupCtrl!.isClosed)
            _setupCtrl!.add(Map<String, dynamic>.from(call.arguments as Map));
        case 'setupDone':
          _setupCtrl?.close(); _setupCtrl = null;
        case 'setupError':
          if (_setupCtrl != null && !_setupCtrl!.isClosed) {
            _setupCtrl!.addError(Exception(
              ((call.arguments as Map?)?['msg'] as String?) ?? 'Setup failed'));
            _setupCtrl!.close(); _setupCtrl = null;
          }
        // Engine events
        case 'engineProgress':
          if (_engineCtrl != null && !_engineCtrl!.isClosed)
            _engineCtrl!.add({'pct': -1,
              ...Map<String, dynamic>.from(call.arguments as Map)});
        case 'engineDone':
          if (_engineCtrl != null && !_engineCtrl!.isClosed) {
            _engineCtrl!.add({'done': true,
              ...Map<String, dynamic>.from(call.arguments as Map)});
            _engineCtrl!.close(); _engineCtrl = null;
          }
        case 'engineError':
          if (_engineCtrl != null && !_engineCtrl!.isClosed) {
            _engineCtrl!.add({'error': true,
              ...Map<String, dynamic>.from(call.arguments as Map)});
            _engineCtrl!.close(); _engineCtrl = null;
          }
      }"""

NEW = """      switch (call.method) {
        // Setup events
        case 'setupProgress':
          if (_setupCtrl != null && !_setupCtrl!.isClosed)
            _setupCtrl!.add(Map<String, dynamic>.from(call.arguments as Map));
          break;  // S176
        case 'setupDone':
          _setupCtrl?.close(); _setupCtrl = null;
          break;  // S176
        case 'setupError':
          if (_setupCtrl != null && !_setupCtrl!.isClosed) {
            _setupCtrl!.addError(Exception(
              ((call.arguments as Map?)?['msg'] as String?) ?? 'Setup failed'));
            _setupCtrl!.close(); _setupCtrl = null;
          }
          break;  // S176
        // Engine events
        case 'engineProgress':
          if (_engineCtrl != null && !_engineCtrl!.isClosed)
            _engineCtrl!.add({'pct': -1,
              ...Map<String, dynamic>.from(call.arguments as Map)});
          break;  // S176
        case 'engineDone':
          if (_engineCtrl != null && !_engineCtrl!.isClosed) {
            _engineCtrl!.add({'done': true,
              ...Map<String, dynamic>.from(call.arguments as Map)});
            _engineCtrl!.close(); _engineCtrl = null;
          }
          break;  // S176
        case 'engineError':
          if (_engineCtrl != null && !_engineCtrl!.isClosed) {
            _engineCtrl!.add({'error': true,
              ...Map<String, dynamic>.from(call.arguments as Map)});
            _engineCtrl!.close(); _engineCtrl = null;
          }
          break;  // S176
      }"""

patch(DART, OLD, NEW, 'S176: add break; to every case in _installHandler switch')

# ── stamp ─────────────────────────────────────────────────────────────────────
STAMP.write_text('S176\n')
print('\n✅  patch_s176 done')
print('   git add lib/services/local_engine_service.dart')
print('   git commit -m "S176: fix missing break in _installHandler switch (case_block_not_terminated)"')
print('   git push')
