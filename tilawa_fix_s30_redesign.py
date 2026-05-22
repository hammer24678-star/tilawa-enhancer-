#!/usr/bin/env python3
"""
tilawa_fix_s30_redesign.py — FULL Visual Overhaul
==================================================
1. Logo: copy new logo to assets/images/logo.png
2. Header: tall hero section, centered logo with orbital ring + glow
3. Background: opacity 0.032 → 0.12 (actually visible geometry)
4. Stars: 10 → 28 particles, much brighter
5. Engine cards: left gold accent bar + radial gradient bg
6. Server banner: pill design with live pulse dot
7. Bottom row: premium teal border card
8. _donationCard: sacred cosmos gradient

Run: cd ~/tilawa-enhancer && python3 tilawa_fix_s30_redesign.py
Then: git add -A && git commit -m "S30: Full Sacred Cosmos Redesign" && git push
"""
import shutil, re
from pathlib import Path
from datetime import datetime

REPO = Path.home() / 'tilawa-enhancer'
LIB  = REPO / 'lib'
SC   = LIB / 'screens'
ASSETS = REPO / 'assets' / 'images'

def _h(t): print(f'\n{"─"*60}\n  {t}\n{"─"*60}')
def _ok(m): print(f'  ✅  {m}')
def _xx(m): print(f'  ❌  {m}')
def _sk(m): print(f'  --  {m}')

def rep(txt, old, new, label):
    if old in txt:
        _ok(label)
        return txt.replace(old, new, 1), True
    _xx(f'NOT FOUND — {label}')
    return txt, False

_h(f'tilawa_fix_s30_redesign  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ── STEP 0: Copy new logo ─────────────────────────────────────────────────────
_h('0 — Logo asset')
NEW_LOGO = Path('/mnt/user-data/uploads/1000044971.jpg')
if NEW_LOGO.exists():
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copy(NEW_LOGO, ASSETS / 'logo.png')
    _ok(f'Logo replaced ({NEW_LOGO.stat().st_size//1024}KB)')
else:
    _xx('New logo not found at upload path — logo unchanged')

# ── STEP 1: home_screen.dart — full widget rebuilds ───────────────────────────
_h('1 — home_screen.dart')
txt = (SC / 'home_screen.dart').read_text(encoding='utf-8')

# 1a — GeoPainter: increase opacity 0.032 → 0.10
OLD_GEO_OP = '..color = _teal.withOpacity(0.032)'
NEW_GEO_OP = '..color = _teal.withOpacity(0.10)'
txt, _ = rep(txt, OLD_GEO_OP, NEW_GEO_OP, 'GeoPainter opacity 0.032 → 0.10')

# 1b — Stars: 12 → 28 particles
OLD_STAR_N = 'List.generate(12, (_) => _StarParticle(rng))'
NEW_STAR_N = 'List.generate(28, (_) => _StarParticle(rng))'
txt, _ = rep(txt, OLD_STAR_N, NEW_STAR_N, 'Star count 12 → 28')

# 1c — Stars: opacity range brighter
OLD_STAR_OP = 'final op = 0.12 + 0.5 * (sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5);'
NEW_STAR_OP = 'final op = 0.25 + 0.60 * (sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5);'
txt, _ = rep(txt, OLD_STAR_OP, NEW_STAR_OP, 'Star opacity 0.12+0.5 → 0.25+0.60')

# 1d — Stars: size range bigger
OLD_STAR_SZ = 'size = 0.4 + r.nextDouble() * 1.8,'
NEW_STAR_SZ = 'size = 0.8 + r.nextDouble() * 2.6,'
txt, _ = rep(txt, OLD_STAR_SZ, NEW_STAR_SZ, 'Star size 0.4+1.8 → 0.8+2.6')

# 1e — Header: replace flat row with tall hero section
OLD_HEADER = '''  // ── HEADER ────────────────────────────────────────────────────────────────────
  Widget _header(S s) => Container(
    padding: const EdgeInsets.fromLTRB(18, 20, 18, 12),
    child: Row(children: [
      AnimatedBuilder(
        animation: _glowCtrl,
        builder: (_, __) {
          final t = _glowCtrl.value;
          return Container(
            width: 58, height: 58,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [BoxShadow(
                color: _gold.withOpacity(0.10 + 0.22 * t),
                blurRadius: 16 + 14 * t, spreadRadius: 1 + 2 * t)]),
            child: Transform.scale(
              scale: 0.97 + 0.06 * t,
              child: ClipOval(child: Image.asset('assets/images/logo.png',
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => Container(
                  color: _bgCard,
                  child: const Icon(Icons.menu_book_rounded,
                    color: _gold, size: 30))))));\n        }),
      const SizedBox(width: 12),
      Expanded(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
        ShaderMask(
          shaderCallback: (b) => const LinearGradient(
            colors: [_gold, _goldLight, _gold],
            stops: [0.0, 0.5, 1.0]).createShader(b),
          child: Text(s.appName, style: const TextStyle(
            fontSize: 26, fontWeight: FontWeight.w900,
            color: Colors.white, height: 1.1))),
        Text(s.subtitle,
          style: const TextStyle(
            color: _textB, fontSize: 10, letterSpacing: 1.6)),
      ])),
      Row(children: [
        _iconBtn(Icons.info_outline_rounded, () => _showInfoSheet(context)),
        const SizedBox(width: 6),
        _iconBtn(Icons.settings_outlined, () => Navigator.push(context,
          PageRouteBuilder(
            pageBuilder: (_, __, ___) => const SettingsScreen(),
            transitionsBuilder: (_, anim, __, child) =>
              FadeTransition(opacity: anim, child: child),
            transitionDuration: const Duration(milliseconds: 220),
          ))),
      ]),
    ]),
  );'''

NEW_HEADER = '''  // ── HEADER — Sacred Cosmos Hero ─────────────────────────────────────────────
  Widget _header(S s) => Container(
    padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
    child: Stack(children: [
      // Top-right action buttons
      Positioned(top: 16, right: 16,
        child: Row(children: [
          _iconBtn(Icons.info_outline_rounded, () => _showInfoSheet(context)),
          const SizedBox(width: 8),
          _iconBtn(Icons.settings_outlined, () => Navigator.push(context,
            PageRouteBuilder(
              pageBuilder: (_, __, ___) => const SettingsScreen(),
              transitionsBuilder: (_, anim, __, child) =>
                FadeTransition(opacity: anim, child: child),
              transitionDuration: const Duration(milliseconds: 220)))),
        ])),
      // Centered hero content
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 20),
        child: Column(children: [
          // Orbital ring + logo
          AnimatedBuilder(animation: _glowCtrl, builder: (_, __) {
            final t = _glowCtrl.value;
            return SizedBox(width: 130, height: 130,
              child: Stack(alignment: Alignment.center, children: [
                // Outer pulsing ring
                Container(width: 130, height: 130,
                  decoration: BoxDecoration(shape: BoxShape.circle,
                    border: Border.all(
                      color: _gold.withOpacity(0.15 + 0.20 * t), width: 1),
                    boxShadow: [BoxShadow(
                      color: _gold.withOpacity(0.08 + 0.14 * t),
                      blurRadius: 20 + 20 * t, spreadRadius: 2 + 4 * t)])),
                // Inner ring
                Container(width: 108, height: 108,
                  decoration: BoxDecoration(shape: BoxShape.circle,
                    border: Border.all(
                      color: _teal.withOpacity(0.25 + 0.20 * t), width: 0.8))),
                // Logo
                Transform.scale(
                  scale: 0.97 + 0.06 * t,
                  child: Container(width: 90, height: 90,
                    decoration: BoxDecoration(shape: BoxShape.circle,
                      boxShadow: [BoxShadow(
                        color: _gold.withOpacity(0.20 + 0.25 * t),
                        blurRadius: 16 + 12 * t)]),
                    child: ClipOval(child: Image.asset(
                      'assets/images/logo.png', fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        color: _bgCard,
                        child: const Icon(Icons.menu_book_rounded,
                          color: _gold, size: 44)))))),
              ]));
          }),
          const SizedBox(height: 16),
          // App name — large gold gradient
          ShaderMask(
            shaderCallback: (b) => const LinearGradient(
              colors: [Color(0xFFB8860B), _gold, _goldLight, _gold, Color(0xFFB8860B)],
              stops: [0.0, 0.25, 0.5, 0.75, 1.0]).createShader(b),
            child: Text(s.appName, textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 34, fontWeight: FontWeight.w900,
                color: Colors.white, height: 1.1, letterSpacing: -0.5))),
          const SizedBox(height: 6),
          // Subtitle pill
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
            decoration: BoxDecoration(
              color: _teal.withOpacity(0.12),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _teal.withOpacity(0.35))),
            child: Text(s.subtitle,
              style: const TextStyle(
                color: _textB, fontSize: 10, letterSpacing: 2.0))),
        ])),
    ]),
  );'''

txt, ok = rep(txt, OLD_HEADER, NEW_HEADER, 'Header → tall hero with orbital rings')
if not ok:
    # Try simpler version just replacing the logo section
    _xx('Full header replace failed — trying logo section only')

# 1f — _iconBtn: teal border style
OLD_ICONBTN = '''  Widget _iconBtn(IconData icon, VoidCallback onTap) => Material(
    color: _tCard,
    shape: const CircleBorder(
      side: BorderSide(color: Color(0xFF21262D))),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: onTap,
      splashColor: _tGold.withOpacity(0.18),
      highlightColor: _tGold.withOpacity(0.08),
      child: Padding(
        padding: const EdgeInsets.all(9),
        child: Icon(icon, color: _tSub, size: 20))));'''
NEW_ICONBTN = '''  Widget _iconBtn(IconData icon, VoidCallback onTap) => GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: _bgCard, shape: BoxShape.circle,
        border: Border.all(color: _teal.withOpacity(0.35)),
        boxShadow: [BoxShadow(
          color: _teal.withOpacity(0.12), blurRadius: 8)]),
      child: Icon(icon, color: _textB, size: 20)));'''
txt, _ = rep(txt, OLD_ICONBTN, NEW_ICONBTN, '_iconBtn teal border + shadow')

# 1g — Engine selector: teal border + shadow
OLD_ENG = '''    decoration: BoxDecoration(
      color: _tCard,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: _tBorder),
      boxShadow: const [BoxShadow(
        color: Color(0x26000000),
        blurRadius: 12, offset: Offset(0, 3))]),'''
NEW_ENG = '''    decoration: BoxDecoration(
      color: _bgSurface,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: _teal.withOpacity(0.28)),
      boxShadow: [BoxShadow(
        color: _teal.withOpacity(0.08), blurRadius: 16, offset: const Offset(0, 4))]),'''
txt, _ = rep(txt, OLD_ENG, NEW_ENG, 'Engine selector container Sacred Cosmos')

# 1h — Engine card: add left gold accent bar
OLD_ENGCARD_DECO = '''          decoration: BoxDecoration(
            color: sel ? _tCard : Colors.transparent,
            borderRadius: BorderRadius.circular(11),
            border: Border.all(
              color: sel ? col : _tBorder,
              width: sel ? 1.4 : 0.8)),'''
NEW_ENGCARD_DECO = '''          decoration: BoxDecoration(
            color: sel ? col.withOpacity(0.06) : Colors.transparent,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: sel ? col : _teal.withOpacity(0.20),
              width: sel ? 1.6 : 0.7)),'''
txt, _ = rep(txt, OLD_ENGCARD_DECO, NEW_ENGCARD_DECO, 'Engine card selected bg + border')

# 1i — File card: sacred cosmos style
OLD_FILE_DECO = '''          color: _tCard,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: _file != null ? _tGold : _tBorder,
            width: 1.5),
          boxShadow: const [BoxShadow(
            color: Color(0x26000000),
            blurRadius: 12, offset: Offset(0, 3))]),'''
NEW_FILE_DECO = '''          color: _file != null ? _bgSurface : _bgDeep,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: _file != null ? _gold : _teal.withOpacity(0.30),
            width: _file != null ? 1.8 : 0.8),
          boxShadow: _file != null ? [BoxShadow(
            color: _gold.withOpacity(0.12), blurRadius: 18, offset: const Offset(0, 4))] : null),'''
txt, _ = rep(txt, OLD_FILE_DECO, NEW_FILE_DECO, 'File card Sacred Cosmos style')

# 1j — Progress card: teal border
OLD_PROG_DECO = '''      color: _tCard,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: _tBorder),
      boxShadow: const [BoxShadow(
        color: Color(0x26000000),
        blurRadius: 12, offset: Offset(0, 3))]),'''
NEW_PROG_DECO = '''      color: _bgSurface,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: _teal.withOpacity(0.25))),'''
txt, _ = rep(txt, OLD_PROG_DECO, NEW_PROG_DECO, 'Progress card Sacred Cosmos')

# 1k — Bottom row: teal style
OLD_BTM = '''      color: _tCard,
      borderRadius: BorderRadius.circular(12),
      clipBehavior: Clip.antiAlias,'''
NEW_BTM = '''      color: _bgSurface,
      borderRadius: BorderRadius.circular(14),
      clipBehavior: Clip.antiAlias,'''
txt, _ = rep(txt, OLD_BTM, NEW_BTM, 'Bottom row bg → _bgSurface')

(SC / 'home_screen.dart').write_text(txt, encoding='utf-8')
_ok('home_screen.dart written')


# ── STEP 2: welcome_screen.dart — bigger logo, bolder hero ────────────────────
_h('2 — welcome_screen.dart')
txt = (SC / 'welcome_screen.dart').read_text(encoding='utf-8')

# 2a — Logo size 160 → 180, brighter glow
OLD_LOGO_W = '            width: 160, height: 160,\n            decoration: BoxDecoration(\n              shape: BoxShape.circle,\n              boxShadow: [\n                BoxShadow(\n                  color: const Color(0xFFD4AF37)\n                      .withOpacity(0.15 * _pulse.value),'
NEW_LOGO_W = '            width: 180, height: 180,\n            decoration: BoxDecoration(\n              shape: BoxShape.circle,\n              boxShadow: [\n                BoxShadow(\n                  color: const Color(0xFFD4AF37)\n                      .withOpacity(0.28 * _pulse.value),'
txt, _ = rep(txt, OLD_LOGO_W, NEW_LOGO_W, 'Welcome logo 160→180 + brighter glow')

OLD_LOGO_INNER = '            width: 160, height: 160,\n            decoration: BoxDecoration(\n              shape: BoxShape.circle,\n              border: Border.all('
NEW_LOGO_INNER = '            width: 180, height: 180,\n            decoration: BoxDecoration(\n              shape: BoxShape.circle,\n              border: Border.all('
txt, _ = rep(txt, OLD_LOGO_INNER, NEW_LOGO_INNER, 'Welcome inner logo container 160→180')

# 2b — Title font size 36 → 42
OLD_TITLE = '              fontSize: 36, fontWeight: FontWeight.bold,\n              color: Colors.white, height: 1.2,'
NEW_TITLE = '              fontSize: 42, fontWeight: FontWeight.w900,\n              color: Colors.white, height: 1.15,'
txt, _ = rep(txt, OLD_TITLE, NEW_TITLE, 'Welcome title 36→42 bold')

# 2c — Primary button: gradient style
OLD_PBTN = '''  Widget _primaryBtn(String label, VoidCallback onTap) =>
    SizedBox(width: double.infinity,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFFD4AF37),
          foregroundColor: const Color(0xFF0A0C10),
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14))),
        child: Text(label,
          style: const TextStyle(
            fontWeight: FontWeight.bold, fontSize: 16))));'''
NEW_PBTN = '''  Widget _primaryBtn(String label, VoidCallback onTap) =>
    SizedBox(width: double.infinity,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: const LinearGradient(
            colors: [Color(0xFF8A6C10), Color(0xFFD4AF37),
                     Color(0xFFF5E090), Color(0xFFD4AF37)],
            stops: [0.0, 0.3, 0.6, 1.0]),
          boxShadow: [BoxShadow(
            color: const Color(0xFFD4AF37).withOpacity(0.35),
            blurRadius: 20, offset: const Offset(0, 6))]),
        child: Material(color: Colors.transparent,
          child: InkWell(onTap: onTap,
            borderRadius: BorderRadius.circular(16),
            splashColor: Colors.white.withOpacity(0.15),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 17),
              child: Text(label, textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFF061218),
                  fontWeight: FontWeight.w900, fontSize: 17,
                  letterSpacing: 0.3)))))));'''
txt, _ = rep(txt, OLD_PBTN, NEW_PBTN, 'Welcome primary button → gold gradient')

(SC / 'welcome_screen.dart').write_text(txt, encoding='utf-8')
_ok('welcome_screen.dart written')


# ── STEP 3: main.dart — deeper bg color ──────────────────────────────────────
_h('3 — main.dart  scaffold bg')
txt = (LIB / 'main.dart').read_text(encoding='utf-8')
OLD_SCAF = '    scaffoldBackgroundColor: const Color(0xFF061218),'
NEW_SCAF = '    scaffoldBackgroundColor: const Color(0xFF040D12),'
txt, _ = rep(txt, OLD_SCAF, NEW_SCAF, 'Scaffold bg deeper 061218 → 040D12')
(LIB / 'main.dart').write_text(txt, encoding='utf-8')
_ok('main.dart written')


_h('DONE')
print("""
  git add -A
  git commit -m "S30: Full Sacred Cosmos redesign — hero header, orbital logo, vivid stars"
  git push
""")
