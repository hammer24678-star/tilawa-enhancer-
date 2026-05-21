#!/usr/bin/env python3
"""tilawa_fix_s29_v6 — two remaining compile errors"""
from pathlib import Path

LIB = Path.home() / 'tilawa-enhancer/lib'
ok_all = True

# 1. lang_provider.dart — remove old version getter (2.7), keep new (2.9)
f = LIB / 'state/lang_provider.dart'
txt = f.read_text(encoding='utf-8')
OLD = "  String get version      => ar ? 'الإصدار 2.7'      : 'Version 2.7';\n"
if OLD in txt:
    txt = txt.replace(OLD, '', 1)
    f.write_text(txt, encoding='utf-8')
    print('✅ removed old version 2.7 getter')
else:
    print('-- version 2.7 getter not found (already removed?)')

# 2. home_screen.dart — fix _rng still used on line 132
f = LIB / 'screens/home_screen.dart'
txt = f.read_text(encoding='utf-8')
OLD2 = '_StarParticle(_rng));'
NEW2 = '_StarParticle(rng));'
if OLD2 in txt:
    txt = txt.replace(OLD2, NEW2)
    f.write_text(txt, encoding='utf-8')
    print('✅ fixed _rng → rng in _StarParticle call')
else:
    print('-- _rng in StarParticle not found (already fixed?)')
