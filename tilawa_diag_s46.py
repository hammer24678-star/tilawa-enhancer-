#!/usr/bin/env python3
"""
tilawa_diag_s46.py — find exact text for every failing s45 anchor
Run:
  cp /sdcard/Download/tilawa_diag_s46.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_diag_s46.py 2>&1 | tee /sdcard/Download/diag_s46.txt
"""
from pathlib import Path

SC = Path.home() / 'tilawa-enhancer/lib/screens'

def dump(label, txt, keywords, ctx=4):
    lines = txt.splitlines()
    print(f'\n=== {label} ===')
    hits = [i for i,l in enumerate(lines) if any(k in l for k in keywords)]
    if not hits:
        print('  NOT FOUND')
        return
    for i in hits[:6]:
        lo, hi = max(0,i-ctx), min(len(lines),i+ctx+1)
        for j in range(lo,hi):
            marker = '>>' if j==i else '  '
            print(f'  {marker} {j+1:5}  {repr(lines[j][:110])}')
        print()

# ── HOME SCREEN ──────────────────────────────────────────────────────────────
ht = (SC / 'home_screen.dart').read_text(encoding='utf-8')

# H1 arch — find file card borderRadius (we know it was circular(22))
dump('H1 file-card borderRadius', ht, ['BorderRadius.circular(22)', 'BorderRadius.only', 'topLeft: Radius'])

# H2 portal label — find pickFile usage
dump('H2 pickFile label', ht, ['pickFile', 'sacred portal', 'أسقط'])

# H3 format hint — find sizeLimit context
dump('H3 sizeLimit context', ht, ['sizeLimit', 'SizedBox(height: 6)', 'SizedBox(height: 3)'])

# H4 mandala — find progress bar context
dump('H4 progress bar LinearProgressIndicator', ht,
     ['LinearProgressIndicator', 'SizedBox(height: 12)', 'ClipRRect', 'S45-MANDALA'])

# ── SETTINGS SCREEN ──────────────────────────────────────────────────────────
st = (SC / 'settings_screen.dart').read_text(encoding='utf-8')

dump('S1 settings _cBg/_cCard/_cBorder', st,
     ['_cBg', '_cCard', '_cBorder', '0xFF080A0E', '0xFF161B22', '0xFF020D0C', '0xFF0F2420'])

dump('S1 settings dialog bg', st,
     ['backgroundColor', '0xFF0C1E28', '0xFF0F2420', 'AlertDialog', 'showDialog'])

# ── HISTORY SCREEN ────────────────────────────────────────────────────────────
vt = (SC / 'history_screen.dart').read_text(encoding='utf-8')

dump('V1 history _cBg/_cCard/_cBorder', vt,
     ['_cBg', '_cCard', '_cBorder', '0xFF080A0E', '0xFF161B22', '0xFF020D0C'])

# ── WELCOME SCREEN ────────────────────────────────────────────────────────────
wt = (SC / 'welcome_screen.dart').read_text(encoding='utf-8')

dump('W2 welcome _cBg/_cCard/_cBorder', wt,
     ['_cBg', '_cCard', '_cBorder', '0xFF080A0E', '0xFF161B22', '0xFF020D0C'])

dump('W3b WelcomeStarsPainter teal', wt,
     ['1C8EA8', '1DB898', 'withOpacity(alpha)', '_WelcomeStarsPainter'])

dump('W3c lang toggle bg', wt,
     ['0xFF161B22', '0xFF21262D', 'BorderRadius.circular(20)', 'lang toggle', 'S45-WEL-LANG'])
