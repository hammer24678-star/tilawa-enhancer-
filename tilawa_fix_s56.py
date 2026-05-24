#!/usr/bin/env python3
"""
tilawa_fix_s56.py — Background enhancement: resume polling on app foreground
=============================================================================
Problem: Timer.periodic stops when Android suspends the Dart isolate.
         Server finishes the job but Flutter never polls "done" status.

Fix:
  1. Add WidgetsBindingObserver to class declaration
  2. Register/unregister observer in initState/dispose
  3. Override didChangeAppLifecycleState — restart polling when app resumes
     AND _jobId is still set (job was in progress when backgrounded)
"""
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(old, new, lbl):
    global txt
    if old in txt: txt = txt.replace(old, new, 1); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s56  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# ── Fix 1: add WidgetsBindingObserver to class mixin list ────────────────────
rep(
    "class _HomeScreenState extends State<HomeScreen>\n"
    "    with TickerProviderStateMixin {",

    "class _HomeScreenState extends State<HomeScreen>\n"
    "    with TickerProviderStateMixin\n"
    "    implements WidgetsBindingObserver {",
    'Fix-1 add WidgetsBindingObserver to class')

# ── Fix 2: register observer in initState (after super.initState()) ──────────
rep(
    "  void initState() {\n"
    "    super.initState();",

    "  void initState() {\n"
    "    super.initState();\n"
    "    WidgetsBinding.instance.addObserver(this); // S56: lifecycle observer",
    'Fix-2 register observer in initState')

# ── Fix 3: unregister observer in dispose ────────────────────────────────────
rep(
    "  void dispose() {\n"
    "    _serverTimer?.cancel();\n"
    "    _pollTimer?.cancel();\n"
    "    _wakeTimer?.cancel();",

    "  void dispose() {\n"
    "    WidgetsBinding.instance.removeObserver(this); // S56\n"
    "    _serverTimer?.cancel();\n"
    "    _pollTimer?.cancel();\n"
    "    _wakeTimer?.cancel();",
    'Fix-3 unregister observer in dispose')

# ── Fix 4: add didChangeAppLifecycleState override ───────────────────────────
# Insert right after the dispose() closing brace.
# Anchor: the line after dispose's last dispose() call then closing brace.
# We look for the _checkServer definition which follows dispose.
rep(
    "  // ── SERVER BANNER (S19: wake button + hint) ────────────────────────────────",

    "  // S56: Resume polling when app returns to foreground\n"
    "  @override\n"
    "  void didChangeAppLifecycleState(AppLifecycleState state) {\n"
    "    if (state == AppLifecycleState.resumed &&\n"
    "        _jobId != null && _busy && _pollTimer == null) {\n"
    "      _pollErrors = 0;\n"
    "      _processStart ??= DateTime.now(); // reset timeout from resume\n"
    "      _startPolling();\n"
    "    }\n"
    "  }\n"
    "\n"
    "  // ── SERVER BANNER (S19: wake button + hint) ────────────────────────────────",
    'Fix-4 didChangeAppLifecycleState override')

HS.write_text(txt, encoding='utf-8')
ok('home_screen.dart saved')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S56: resume polling on app foreground -- WidgetsBindingObserver" && git push\n')
