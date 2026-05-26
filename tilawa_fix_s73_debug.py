#!/usr/bin/env python3
"""
tilawa_fix_s73_debug.py  —  S73: switch to debug APK build
=============================================================
Problem: tilawa_release.jks not in repo, no GitHub secrets set up
Fix:     Use flutter build apk --debug (no signing needed, APK runs fine)
         Remove keystore-related steps from workflow

Run:
  cp /sdcard/Download/tilawa_fix_s73_debug.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s73_debug.py
  git add -A
  git commit -m "S73: switch to debug APK — no keystore needed"
  git push
"""
from pathlib import Path
import re

_log = []
def ok(m):  print(f'  OK  {m}'); _log.append(('OK', m))
def xx(m):  print(f'  XX  {m}'); _log.append(('XX', m))
def sk(m):  print(f'  --  {m}'); _log.append(('SK', m))

ROOT = Path.home() / 'tilawa-enhancer'

# ── Find the workflow file ───────────────────────────────────────────────────
wf_dir = ROOT / '.github/workflows'
wf_files = list(wf_dir.glob('*.yml')) + list(wf_dir.glob('*.yaml'))
if not wf_files:
    xx(f'No workflow files found in {wf_dir}')
    exit(1)

wf = wf_files[0]
print(f'  Workflow: {wf.name}')
txt = wf.read_text()

if '// S73' in txt or '# S73' in txt:
    sk('S73 already applied'); exit(0)

changes = 0

# ── 1. flutter build apk --release  →  --debug ──────────────────────────────
old1 = 'flutter build apk --release --no-tree-shake-icons'
new1 = 'flutter build apk --debug --no-tree-shake-icons  # S73'
if old1 in txt:
    txt = txt.replace(old1, new1, 1); ok('--release → --debug'); changes += 1
else:
    # Try without --no-tree-shake-icons
    old1b = 'flutter build apk --release'
    new1b = 'flutter build apk --debug  # S73'
    if old1b in txt:
        txt = txt.replace(old1b, new1b, 1); ok('--release → --debug (simple)'); changes += 1
    else:
        xx('flutter build apk --release not found')

# ── 2. APK artifact path release → debug ────────────────────────────────────
for old, new in [
    ('app-release.apk', 'app-debug.apk  # S73'),
    ('flutter-apk/app-release', 'flutter-apk/app-debug  # S73'),
    ('outputs/apk/release', 'outputs/apk/debug  # S73'),
]:
    if old in txt:
        txt = txt.replace(old, new); ok(f'Path: {old} → debug'); changes += 1

# ── 3. Comment out keystore decode/setup steps ──────────────────────────────
# Find lines that reference keystore setup
keystore_patterns = [
    r'echo \$\{.*KEYSTORE.*\}.*base64',
    r'base64.*decode.*jks',
    r'KEYSTORE_BASE64',
    r'key\.properties',
    r'tilawa_release\.jks',
]
lines = txt.splitlines()
new_lines = []
in_keystore_step = False
for line in lines:
    is_ks = any(re.search(p, line, re.IGNORECASE) for p in keystore_patterns)
    if is_ks and not line.strip().startswith('#'):
        new_lines.append('        # S73-SKIP: ' + line.lstrip())
        changes += 1
    else:
        new_lines.append(line)
txt = '\n'.join(new_lines)
if changes > 2:
    ok(f'Commented out keystore lines')

# ── Write ────────────────────────────────────────────────────────────────────
if changes > 0:
    wf.write_text(txt)
    ok(f'{wf.name} saved ({changes} changes)')
else:
    xx('No changes made — paste output to Claude')

print(f'\n  {"OK" if all(s=="OK" for s,_ in _log) else "FAIL"} — {sum(1 for s,_ in _log if s=="OK")} OK, {sum(1 for s,_ in _log if s=="XX")} FAIL')
if all(s in ("OK","SK") for s,_ in _log):
    print("""
  git add -A && git commit -m "S73: switch to debug APK — no keystore needed" && git push
""")
