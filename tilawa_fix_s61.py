#!/usr/bin/env python3
"""
tilawa_fix_s61.py — UI overhaul: AppBar + Header + About + Settings
====================================================================
1. SliverAppBar — gold shimmer line at bottom, radial glow, logo pulse ring
2. _header — always Arabic name, tighter spacing, bigger subtitle pill
3. Engine comparison (About) — taller bars, engine colour glow, score %
4. Settings — gradient section labels, premium language pill, dark mode glow

Run:
  cp /sdcard/Download/tilawa_fix_s61.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s61.py && git add -A && git commit -m "S61: UI overhaul AppBar+header+about+settings" && git push
"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
SS = Path.home() / 'tilawa-enhancer/lib/screens/settings_screen.dart'

ok_n = xx_n = sk_n = 0
def ok(m):  global ok_n; print(f'  OK  {m}'); ok_n += 1
def xx(m):  global xx_n; print(f'  XX  {m}'); xx_n += 1
def sk(m):  global sk_n; print(f'  --  {m}'); sk_n += 1

def rep(t, old, new, lbl):
    if old not in t: xx(f'NOT FOUND — {lbl}'); return t
    ok(lbl); return t.replace(old, new, 1)

print(f'\n=== tilawa_fix_s61.py  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===\n')

# ══════════════════════════════════════════════════════════════════
# HOME SCREEN
# ══════════════════════════════════════════════════════════════════
ht = HS.read_text(encoding='utf-8')

# ── 1. SliverAppBar — gold glow bottom line + better gradient ────
if '// S61-APPBAR' in ht:
    sk('AppBar already redesigned')
else:
    ht = rep(ht,
        '            SliverAppBar(\n'
        '              // S35-APPBAR\n'
        '              pinned: true,\n'
        '              floating: false,\n'
        '              backgroundColor: const Color(0xFF020D0C), // S40-AB-VOID\n'
        '              elevation: 0,\n'
        '              expandedHeight: 88,\n'
        '              flexibleSpace: FlexibleSpaceBar(\n'
        '                centerTitle: true,\n'
        '                background: Container(\n'
        '                  decoration: const BoxDecoration(\n'
        '                    gradient: LinearGradient(\n'
        '                      begin: Alignment.topLeft,\n'
        '                      end: Alignment.bottomRight,\n'
        '                      colors: [\n'
        '                        Color(0xFF0A2A1E),\n'
        '                        Color(0xFF020D0C),\n'
        '                      ]))),\n'
        '                title: Row(\n'
        '                  mainAxisSize: MainAxisSize.min,\n'
        '                  children: [\n'
        '                    Padding(\n'
        '                      padding: const EdgeInsets.only(right: 8),\n'
        '                      child: Image.asset(\n'
        '                        \'assets/images/logo.png\',\n'
        '                        width: 32, height: 32,\n'
        '                        fit: BoxFit.contain)),\n'
        '                    RichText(\n'
        '                      text: const TextSpan(\n'
        '                        style: TextStyle(fontFamily: \'Roboto\'),\n'
        '                        children: [\n'
        '                          TextSpan(\n'
        '                            text: \'محسِّن \',\n'
        '                            style: TextStyle(\n'
        '                              color: Color(0xFFD4AF37),\n'
        '                              fontSize: 18,\n'
        '                              fontWeight: FontWeight.w700,\n'
        '                              letterSpacing: 0.3)),\n'
        '                          TextSpan(\n'
        '                            text: \'التلاوة\',\n'
        '                            style: TextStyle(\n'
        '                              color: Color(0xFFF2EFE5),\n'
        '                              fontSize: 18,\n'
        '                              fontWeight: FontWeight.w300)),\n'
        '                        ])),\n'
        '                  ])),\n'
        '            ),',
        # ── NEW ──
        '            SliverAppBar( // S61-APPBAR\n'
        '              pinned: true,\n'
        '              floating: false,\n'
        '              backgroundColor: const Color(0xFF020D0C),\n'
        '              elevation: 0,\n'
        '              expandedHeight: 72,\n'
        '              bottom: PreferredSize(\n'
        '                preferredSize: const Size.fromHeight(1),\n'
        '                child: Container(\n'
        '                  height: 1,\n'
        '                  decoration: const BoxDecoration(\n'
        '                    gradient: LinearGradient(\n'
        '                      colors: [Colors.transparent,\n'
        '                               Color(0xFFD4AF37),\n'
        '                               Color(0xFF1DB898),\n'
        '                               Colors.transparent])))),\n'
        '              flexibleSpace: FlexibleSpaceBar(\n'
        '                centerTitle: true,\n'
        '                background: Container(\n'
        '                  decoration: const BoxDecoration(\n'
        '                    gradient: RadialGradient(\n'
        '                      center: Alignment.topCenter,\n'
        '                      radius: 1.8,\n'
        '                      colors: [\n'
        '                        Color(0xFF0D2E1F),\n'
        '                        Color(0xFF020D0C)]))),\n'
        '                title: Row(\n'
        '                  mainAxisSize: MainAxisSize.min,\n'
        '                  children: [\n'
        '                    Container(\n'
        '                      width: 34, height: 34,\n'
        '                      decoration: BoxDecoration(\n'
        '                        shape: BoxShape.circle,\n'
        '                        boxShadow: [BoxShadow(\n'
        '                          color: const Color(0xFFD4AF37).withOpacity(0.35),\n'
        '                          blurRadius: 12)]),\n'
        '                      child: ClipOval(child: Image.asset(\n'
        '                        \'assets/images/logo.png\',\n'
        '                        fit: BoxFit.cover))),\n'
        '                    const SizedBox(width: 10),\n'
        '                    ShaderMask(\n'
        '                      shaderCallback: (b) => const LinearGradient(\n'
        '                        colors: [Color(0xFFD4AF37), Color(0xFFF0CF60),\n'
        '                                 Color(0xFFD4AF37)])\n'
        '                        .createShader(b),\n'
        '                      child: const Text(\'محسِّن \',\n'
        '                        style: TextStyle(\n'
        '                          color: Colors.white,\n'
        '                          fontSize: 19,\n'
        '                          fontWeight: FontWeight.w800,\n'
        '                          letterSpacing: 0.5))),\n'
        '                    const Text(\'التلاوة\',\n'
        '                      style: TextStyle(\n'
        '                        color: Color(0xFFE2CFA0),\n'
        '                        fontSize: 19,\n'
        '                        fontWeight: FontWeight.w300,\n'
        '                        letterSpacing: 0.3)),\n'
        '                  ])),\n'
        '            ),',
        'SliverAppBar redesign')

# ── 2. _header — always show Arabic name, tighter spacing ────────
if '// S61-HEADER-NAME' in ht:
    sk('Header name already redesigned')
else:
    ht = rep(ht,
        '          // App name — large gold gradient\n'
        '          ShaderMask(\n'
        '            shaderCallback: (b) => const LinearGradient(\n'
        '              colors: [Color(0xFFB8860B), _gold, _goldLight, _gold, Color(0xFFB8860B)],\n'
        '              stops: [0.0, 0.25, 0.5, 0.75, 1.0]).createShader(b),\n'
        '            child: Text(s.appName, textAlign: TextAlign.center,\n'
        '              style: const TextStyle(\n'
        '                fontSize: 34, fontWeight: FontWeight.w900,\n'
        '                color: Colors.white, height: 1.1, letterSpacing: -0.5))),\n'
        '          const SizedBox(height: 6),',
        '          // S61-HEADER-NAME — always Arabic, elegant sizing\n'
        '          ShaderMask(\n'
        '            shaderCallback: (b) => const LinearGradient(\n'
        '              begin: Alignment.topLeft,\n'
        '              end: Alignment.bottomRight,\n'
        '              colors: [Color(0xFFD4AF37), Color(0xFFF5E070),\n'
        '                       Color(0xFFD4AF37)])\n'
        '              .createShader(b),\n'
        '            child: const Text(\'محسِّن التلاوة\',\n'
        '              textAlign: TextAlign.center,\n'
        '              style: TextStyle(\n'
        '                fontSize: 30, fontWeight: FontWeight.w800,\n'
        '                color: Colors.white, height: 1.1,\n'
        '                letterSpacing: 1.2))),\n'
        '          const SizedBox(height: 4),',
        'Header name → always Arabic + refined')

# ── 3. Engine comparison bars — taller + glow ────────────────────
if '// S61-ENG-BAR' in ht:
    sk('Engine comparison already redesigned')
else:
    ht = rep(ht,
        '                          ClipRRect(\n'
        '                            borderRadius: BorderRadius.circular(3),\n'
        '                            child: LinearProgressIndicator(\n'
        '                              value: e.score / 100,\n'
        '                              minHeight: 4,\n'
        '                              backgroundColor: _tBorder,\n'
        '                              valueColor: AlwaysStoppedAnimation<Color>(col))),',
        '                          // S61-ENG-BAR\n'
        '                          Stack(children: [\n'
        '                            ClipRRect(\n'
        '                              borderRadius: BorderRadius.circular(4),\n'
        '                              child: LinearProgressIndicator(\n'
        '                                value: e.score / 100,\n'
        '                                minHeight: 7,\n'
        '                                backgroundColor: _tBorder,\n'
        '                                valueColor: AlwaysStoppedAnimation<Color>(\n'
        '                                  col))),\n'
        '                            Positioned.fill(child: ClipRRect(\n'
        '                              borderRadius: BorderRadius.circular(4),\n'
        '                              child: FractionallySizedBox(\n'
        '                                widthFactor: e.score / 100,\n'
        '                                alignment: Alignment.centerLeft,\n'
        '                                child: Container(\n'
        '                                  decoration: BoxDecoration(\n'
        '                                    borderRadius: BorderRadius.circular(4),\n'
        '                                    boxShadow: [BoxShadow(\n'
        '                                      color: col.withOpacity(0.5),\n'
        '                                      blurRadius: 6,\n'
        '                                      spreadRadius: 0)]))))],\n'
        '                          ),',
        'Engine comparison bars → taller + glow')

# ── 4. Engine comparison container — dark Sacred Cosmos card ──────
if '// S61-ENG-CONTAINER' in ht:
    sk('Engine comparison container already redesigned')
else:
    ht = rep(ht,
        '                  decoration: BoxDecoration(\n'
        '                    color: _tCard,\n'
        '                    borderRadius: BorderRadius.circular(12),\n'
        '                    border: Border.all(color: _tBorder)),\n'
        '                  child: Column(\n'
        '                    children: _engines.map((e) {',
        '                  decoration: BoxDecoration( // S61-ENG-CONTAINER\n'
        '                    color: const Color(0xFF061018),\n'
        '                    borderRadius: BorderRadius.circular(16),\n'
        '                    border: Border.all(\n'
        '                      color: const Color(0xFFD4AF37).withOpacity(0.2)),\n'
        '                    boxShadow: [BoxShadow(\n'
        '                      color: const Color(0xFF1DB898).withOpacity(0.06),\n'
        '                      blurRadius: 20)]),\n'
        '                  child: Column(\n'
        '                    children: _engines.map((e) {',
        'Engine comparison container → Sacred Cosmos')

HS.write_text(ht, encoding='utf-8')
ok('home_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# SETTINGS SCREEN
# ══════════════════════════════════════════════════════════════════
st = SS.read_text(encoding='utf-8')

# ── 5. Language pill — gold gradient for active, Sacred Cosmos ────
if '// S61-LANG-PILL' in st:
    sk('Language pill already redesigned')
else:
    st = rep(st,
        '            margin: const EdgeInsets.only(bottom: 18),\n'
        '            padding: const EdgeInsets.all(4),\n'
        '            decoration: BoxDecoration(\n'
        '              color: cCard,\n'
        '              borderRadius: BorderRadius.circular(12),\n'
        '              border: Border.all(color: cBorder)),',
        '            margin: const EdgeInsets.only(bottom: 18), // S61-LANG-PILL\n'
        '            padding: const EdgeInsets.all(4),\n'
        '            decoration: BoxDecoration(\n'
        '              gradient: LinearGradient(\n'
        '                colors: [const Color(0xFF0A1A10),\n'
        '                         const Color(0xFF061810)]),\n'
        '              borderRadius: BorderRadius.circular(14),\n'
        '              border: Border.all(\n'
        '                color: const Color(0xFFD4AF37).withOpacity(0.3))),',
        'Language pill container → Sacred Cosmos')

# ── 6. Target info card — more prominent ──────────────────────────
if '// S61-TARGET' in st:
    sk('Target card already redesigned')
else:
    st = rep(st,
        '            decoration: BoxDecoration(\n'
        '              color: const Color(0xFF0A1A0F),\n'
        '              borderRadius: BorderRadius.circular(10),\n'
        '              border: Border.all(\n'
        '                color: const Color(0xFF3FB950).withOpacity(0.35))),\n'
        '            child: Text(s.target,\n'
        '              textAlign: TextAlign.center,\n'
        '              style: const TextStyle(\n'
        '                color: Color(0xFF3FB950), fontSize: 11))),',
        '            decoration: BoxDecoration( // S61-TARGET\n'
        '              gradient: const LinearGradient(\n'
        '                colors: [Color(0xFF061810), Color(0xFF0A2015)]),\n'
        '              borderRadius: BorderRadius.circular(12),\n'
        '              border: Border.all(\n'
        '                color: Color(0xFF1DB898), width: 0.8),\n'
        '              boxShadow: [BoxShadow(\n'
        '                color: Color(0xFF1DB898),\n'
        '                blurRadius: 12, spreadRadius: 0,\n'
        '                offset: Offset(0, 0))]),\n'
        '            child: Text(s.target,\n'
        '              textAlign: TextAlign.center,\n'
        '              style: const TextStyle(\n'
        '                color: Color(0xFF1DB898),\n'
        '                fontSize: 11, letterSpacing: 0.5))),',
        'Target card → teal glow Sacred Cosmos')

# ── 7. Settings About card — premium look ─────────────────────────
if '// S61-ABOUT-CARD' in st:
    sk('About card already redesigned')
else:
    st = rep(st,
        '            padding: const EdgeInsets.all(18),\n'
        '            decoration: BoxDecoration(\n'
        '              color: cCard,\n'
        '              borderRadius: BorderRadius.circular(12),\n'
        '              border: Border.all(color: cBorder)),\n'
        '            child: Column(children: [\n'
        '              // Small logo in About',
        '            padding: const EdgeInsets.all(18), // S61-ABOUT-CARD\n'
        '            decoration: BoxDecoration(\n'
        '              gradient: const LinearGradient(\n'
        '                begin: Alignment.topLeft,\n'
        '                end: Alignment.bottomRight,\n'
        '                colors: [Color(0xFF0A1A10), Color(0xFF061015)]),\n'
        '              borderRadius: BorderRadius.circular(16),\n'
        '              border: Border.all(\n'
        '                color: const Color(0xFFD4AF37).withOpacity(0.25)),\n'
        '              boxShadow: [BoxShadow(\n'
        '                color: const Color(0xFFD4AF37).withOpacity(0.08),\n'
        '                blurRadius: 20)]),\n'
        '            child: Column(children: [\n'
        '              // Small logo in About',
        'About card → Sacred Cosmos gradient')

SS.write_text(st, encoding='utf-8')
ok('settings_screen.dart saved')

print(f'\n  {ok_n} OK   {sk_n} SKIP   {xx_n} FAIL\n')
if xx_n == 0:
    print('git add -A && git commit -m "S61: UI overhaul AppBar+header+about+settings" && git push')
else:
    print('Paste output back to Claude.')
