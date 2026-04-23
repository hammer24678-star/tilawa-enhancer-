#!/usr/bin/env python3
"""
patch_theme_toggle_fix.py — S32 Dark/Light toggle instant-update fix
Bug: _themeTile() uses outer `context` for colors inside ValueListenableBuilder.
     The builder's `ctx` has the NEW theme, but `context` is the stale outer one.
     Result: switch moves, colors stay wrong until next frame.
Fix: replace context→ctx for all 4 color calls inside the builder.
"""

import sys, os

TARGET = 'lib/screens/settings_screen.dart'

OLD = '''      builder: (ctx, dark, _) => Container(
        margin: const EdgeInsets.only(bottom: 18),
        decoration: BoxDecoration(
          color: _cCard(context),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _cBorder(context))),
        child: SwitchListTile(
          secondary: Icon(
            dark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
            color: const Color(0xFFD4AF37)),
          title: Text(
            s.ar ? \'الوضع الداكن\' : \'Dark Mode\',
            style: TextStyle(color: _cText(context), fontSize: 14)),
          subtitle: Text(
            dark
              ? (s.ar ? \'الوضع الحالي\' : \'Currently active\')
              : (s.ar ? \'الوضع الفاتح نشط\' : \'Light mode active\'),
            style: TextStyle(color: _cSub(context), fontSize: 11)),'''

NEW = '''      builder: (ctx, dark, _) => Container(
        margin: const EdgeInsets.only(bottom: 18),
        decoration: BoxDecoration(
          color: _cCard(ctx),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _cBorder(ctx))),
        child: SwitchListTile(
          secondary: Icon(
            dark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
            color: const Color(0xFFD4AF37)),
          title: Text(
            s.ar ? \'الوضع الداكن\' : \'Dark Mode\',
            style: TextStyle(color: _cText(ctx), fontSize: 14)),
          subtitle: Text(
            dark
              ? (s.ar ? \'الوضع الحالي\' : \'Currently active\')
              : (s.ar ? \'الوضع الفاتح نشط\' : \'Light mode active\'),
            style: TextStyle(color: _cSub(ctx), fontSize: 11)),'''

def patch(path, old, new, label):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    count = src.count(old)
    if count == 0:
        print(f'FAIL [{label}] — anchor not found')
        return False
    if count > 1:
        print(f'FAIL [{label}] — anchor matched {count} times (ambiguous)')
        return False
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src.replace(old, new, 1))
    print(f'OK   [{label}]')
    return True

if not os.path.exists(TARGET):
    print(f'ERROR: {TARGET} not found. Run from Flutter repo root.')
    sys.exit(1)

ok = patch(TARGET, OLD, NEW, '_themeTile: context→ctx for 4 color calls')
sys.exit(0 if ok else 1)
