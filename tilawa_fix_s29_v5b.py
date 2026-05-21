#!/usr/bin/env python3
"""tilawa_fix_s29_v5b — fix welcome_screen ShaderMask using regex"""
import re
from pathlib import Path
from datetime import datetime

SC = Path.home() / 'tilawa-enhancer/lib/screens'
txt = (SC / 'welcome_screen.dart').read_text(encoding='utf-8')

# Show lines 128-148 so we see the exact broken text
lines = txt.splitlines()
print('=== welcome_screen.dart lines 128-150 ===')
for i, l in enumerate(lines[127:150], start=128):
    print(f'{i:4d}  {repr(l)}')

# Fix: find any ShaderMask block in _page0 that is missing its closing paren
# Pattern: ShaderMask( ... child: Text(s.appName, ... )),
# followed immediately by SizedBox or Text (no closing paren for ShaderMask itself)
pattern = re.compile(
    r'(        ShaderMask\(\s*\n)'           # ShaderMask opening
    r'(\s+shaderCallback[^\n]+\n)'           # shaderCallback line
    r'(\s+colors[^\n]+\n)'                   # colors line
    r'(\s+stops[^\n]+\n)'                    # stops line
    r'(\s+child: Text\(s\.appName,\s*\n)'    # child: Text
    r'(\s+textAlign[^\n]+\n)'               # textAlign
    r'(\s+style: const TextStyle\(\s*\n)'   # style
    r'(\s+fontSize[^\n]+\n)'               # fontSize
    r'(\s+color: Color\(0xFF[0-9A-Fa-f]+\)[^\n]+\n)'  # color
    r'(\s+letterSpacing[^\n]+\)\)\),?\n)'  # letterSpacing — may or may not have closing
    r'(\s+const SizedBox)',                  # next widget
    re.DOTALL
)

m = pattern.search(txt)
if m:
    print('\n=== MATCH FOUND — fixing ===')
    old = m.group(0)
    print(f'OLD:\n{old}')
    new = (
        '        ShaderMask(\n'
        '          shaderCallback: (b) => const LinearGradient(\n'
        '            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60), Color(0xFFD4AF37)],\n'
        '            stops: [0.0, 0.5, 1.0]).createShader(b),\n'
        '          child: Text(s.appName,\n'
        '            textAlign: TextAlign.center,\n'
        '            style: const TextStyle(\n'
        '              fontSize: 36, fontWeight: FontWeight.bold,\n'
        '              color: Colors.white, height: 1.2,\n'
        '              letterSpacing: -0.5))),\n'
        '          const SizedBox'
    )
    txt = txt.replace(old, new, 1)
    print(f'NEW:\n{new}')
    (SC / 'welcome_screen.dart').write_text(txt, encoding='utf-8')
    print('\n✅ welcome_screen.dart fixed')
else:
    print('\n=== NO MATCH — printing full _page0 section ===')
    start = txt.find('Widget _page0')
    end   = txt.find('Widget _page1')
    print(txt[start:end])
