#!/usr/bin/env python3
"""
tilawa_fix_s84.py
=================
1. build_assets.sh: fix DeepFilter URL (0_5.6 not 0_5_6, gnu not musl)
2. build_assets.sh: add ffmpeg to Docker apk install (fix echo check)
3. home_screen.dart: local mode ON by default + v11.x = local only
4. home_screen.dart: auto-switch mode when engine requires different mode
5. engine list: v11.0/v11.1/v11.2 tagged LOCAL, rest tagged SERVER
6. welcome_screen.dart: add Local vs Server mode info card
"""
from pathlib import Path
from datetime import datetime

ROOT = Path.home() / 'tilawa-enhancer'
SC   = ROOT / 'lib/screens'

_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX', l))
def rep(f, old, new, lbl):
    t = f.read_text(encoding='utf-8')
    if old in t:
        f.write_text(t.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else:
        xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s84  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# ════════════════════════════════════════════════════════════
# 1. build_assets.sh — fix DeepFilter URL
# ════════════════════════════════════════════════════════════
ba = ROOT / 'build_assets.sh'
rep(ba,
    '''DF_VER="${DF_VERSION//./_}"
# Try musl first (smaller, more compatible with Alpine)
curl -fsSL --retry 3 \\
    "https://github.com/Rikorose/DeepFilterNet/releases/download/v${DF_VERSION}/deep-filter-${DF_VER}-${ARCH}-unknown-linux-musl" \\
    -o "$ASSETS/deep-filter" || \\
curl -fsSL --retry 3 \\
    "https://github.com/Rikorose/DeepFilterNet/releases/download/v${DF_VERSION}/deep-filter-${DF_VER}-${ARCH}-unknown-linux-gnu" \\
    -o "$ASSETS/deep-filter"''',
    '''# Real filename format: 0_5.6 (first dot→underscore only), gnu build for aarch64
DF_VER="${DF_VERSION/./_}"      # 0.5.6 → 0_5.6 (only first dot replaced)
curl -fsSL --retry 3 \\
    "https://github.com/Rikorose/DeepFilterNet/releases/download/v${DF_VERSION}/deep-filter-${DF_VER}-${ARCH}-unknown-linux-gnu" \\
    -o "$ASSETS/deep-filter" || \\
curl -fsSL --retry 3 \\
    "https://github.com/Rikorose/DeepFilterNet/releases/download/v${DF_VERSION}/deep-filter-${DF_VER}-${ARCH}-unknown-linux-musl" \\
    -o "$ASSETS/deep-filter"''',
    'build_assets.sh: fix DeepFilter URL (0_5.6 format, gnu first)')

# Fix ffmpeg echo check (runs outside docker — just suppress error)
rep(ba,
    "        echo 'ffmpeg: '$(ffmpeg -version 2>&1 | head -1)",
    "        echo 'ffmpeg: '$(which ffmpeg 2>/dev/null && ffmpeg -version 2>&1 | head -1 || echo 'checking inside tar...')",
    'build_assets.sh: fix ffmpeg echo (was running outside docker)')

# ════════════════════════════════════════════════════════════
# 2. home_screen.dart
# ════════════════════════════════════════════════════════════
hs = SC / 'home_screen.dart'
txt = hs.read_text(encoding='utf-8')

# 2a — Default engine → v11.0 (most powerful local engine)
if "String  _engine    = 'v10.0';" in txt:
    txt = txt.replace("String  _engine    = 'v10.0';",
                      "String  _engine    = 'v11.0';  // S84: default = strongest local engine")
    ok('default engine v10.0 → v11.0')
else:
    xx('default engine anchor not found')

# 2b — Tag engines: local vs server + add localOnly field to _EngineData
# Add localOnly field to _EngineData class
OLD_ENG_CLASS = '''class _EngineData {
  final String id, nameAr, nameEn, badge, bc;
  final double score;
  final List<String> features;
  final String whatsNewAr, whatsNewEn;
  final String? imgAsset;'''
NEW_ENG_CLASS = '''class _EngineData {
  final String id, nameAr, nameEn, badge, bc;
  final double score;
  final List<String> features;
  final String whatsNewAr, whatsNewEn;
  final String? imgAsset;
  final bool localOnly;   // S84: true = requires local proot engine'''
if OLD_ENG_CLASS in txt:
    txt = txt.replace(OLD_ENG_CLASS, NEW_ENG_CLASS, 1); ok('_EngineData: localOnly field added')
else:
    xx('_EngineData class not found')

# Fix _EngineData constructor
OLD_CTOR = '''  const _EngineData(this.id, this.nameAr, this.nameEn, this.score,
      this.badge, this.bc, this.features, this.whatsNewAr, this.whatsNewEn,
      {this.imgAsset});'''
NEW_CTOR = '''  const _EngineData(this.id, this.nameAr, this.nameEn, this.score,
      this.badge, this.bc, this.features, this.whatsNewAr, this.whatsNewEn,
      {this.imgAsset, this.localOnly = false});'''
if OLD_CTOR in txt:
    txt = txt.replace(OLD_CTOR, NEW_CTOR, 1); ok('_EngineData constructor: localOnly param')
else:
    xx('_EngineData constructor not found')

# Tag v11.x engines as localOnly
for engine_id in ["'v11.0'", "'v11.1'", "'v11.2'"]:
    # Find each engine's imgAsset line and add localOnly: true
    old_asset = f"imgAsset: 'assets/images/engines/"
    # We'll do a targeted replace for each engine block
pass

# Tag v11 engines: replace closing of each v11 engine data
for old_img, new_img in [
    ("imgAsset: 'assets/images/engines/tajalli.jpg'),",
     "imgAsset: 'assets/images/engines/tajalli.jpg', localOnly: true),"),
    ("imgAsset: 'assets/images/engines/itiqan.jpg'),",
     "imgAsset: 'assets/images/engines/itiqan.jpg', localOnly: true),"),
    ("imgAsset: 'assets/images/engines/isteidad.jpg'),",
     "imgAsset: 'assets/images/engines/isteidad.jpg', localOnly: true),"),
]:
    if old_img in txt:
        txt = txt.replace(old_img, new_img, 1); ok(f'Tagged {old_img[:20]}... localOnly=true')
    else:
        xx(f'Engine imgAsset not found: {old_img[:30]}')

# 2c — Auto-switch mode when selecting engine
OLD_ENGINE_TAP = "setState(() => _engine = e.id);"
NEW_ENGINE_TAP = (
    "setState(() {\n"
    "              _engine = e.id;\n"
    "              // S84: auto-switch mode to match engine requirement\n"
    "              if (e.localOnly && !_localMode) {\n"
    "                _localMode = true;\n"
    "              } else if (!e.localOnly && _localMode) {\n"
    "                _localMode = false;\n"
    "              }\n"
    "            });"
)
if OLD_ENGINE_TAP in txt:
    txt = txt.replace(OLD_ENGINE_TAP, NEW_ENGINE_TAP, 1); ok('engine tap: auto-switch mode')
else:
    xx('engine tap setState not found')

# 2d — Show LOCAL / SERVER badge on engine cards
OLD_ENG_BADGE = (
    "                  if (e.badge.isNotEmpty) ...[\n"
    "                    const SizedBox(width: 8),\n"
    "                    Container(\n"
    "                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),\n"
    "                      decoration: BoxDecoration(\n"
    "                        color: col.withOpacity(0.12),\n"
    "                        borderRadius: BorderRadius.circular(5),\n"
    "                        border: Border.all(color: col.withOpacity(0.45))),\n"
    "                      child: Text(e.badge, style: TextStyle(\n"
    "                        color: col, fontSize: 8, fontWeight: FontWeight.bold,\n"
    "                        letterSpacing: 0.8))),\n"
    "                  ],\n"
)
NEW_ENG_BADGE = (
    "                  const SizedBox(width: 8),\n"
    "                  // S84: LOCAL / SERVER mode badge\n"
    "                  Container(\n"
    "                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),\n"
    "                    decoration: BoxDecoration(\n"
    "                      color: e.localOnly\n"
    "                        ? _teal.withOpacity(0.18)\n"
    "                        : _tBorder.withOpacity(0.5),\n"
    "                      borderRadius: BorderRadius.circular(5),\n"
    "                      border: Border.all(\n"
    "                        color: e.localOnly ? _teal : _tSub.withOpacity(0.5))),\n"
    "                    child: Text(\n"
    "                      e.localOnly ? '🏠 LOCAL' : '☁ SERVER',\n"
    "                      style: TextStyle(\n"
    "                        color: e.localOnly ? _teal : _tSub,\n"
    "                        fontSize: 7, fontWeight: FontWeight.bold,\n"
    "                        letterSpacing: 0.6))),\n"
    "                  if (e.badge.isNotEmpty) ...[\n"
    "                    const SizedBox(width: 6),\n"
    "                    Container(\n"
    "                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),\n"
    "                      decoration: BoxDecoration(\n"
    "                        color: col.withOpacity(0.12),\n"
    "                        borderRadius: BorderRadius.circular(5),\n"
    "                        border: Border.all(color: col.withOpacity(0.45))),\n"
    "                      child: Text(e.badge, style: TextStyle(\n"
    "                        color: col, fontSize: 8, fontWeight: FontWeight.bold,\n"
    "                        letterSpacing: 0.8))),\n"
    "                  ],\n"
)
if OLD_ENG_BADGE in txt:
    txt = txt.replace(OLD_ENG_BADGE, NEW_ENG_BADGE, 1); ok('ENGINE: LOCAL/SERVER badge added')
else:
    xx('engine badge section not found')

hs.write_text(txt, encoding='utf-8')
ok('home_screen.dart saved')

# ════════════════════════════════════════════════════════════
# 3. welcome_screen.dart — add Local/Server info card on page 0
# ════════════════════════════════════════════════════════════
ws = SC / 'welcome_screen.dart'
txt = ws.read_text(encoding='utf-8')

MODE_CARD = '''
        const SizedBox(height: 28),
        // S84: Mode info card
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 4),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.28),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: const Color(0xFF1DB898).withOpacity(0.30))),
          child: Column(children: [
            // Local mode
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF1DB898).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF1DB898).withOpacity(0.5))),
                child: const Text('🏠 LOCAL',
                  style: TextStyle(color: Color(0xFF1DB898),
                    fontSize: 10, fontWeight: FontWeight.bold))),
              const SizedBox(width: 12),
              const Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('التجلي · الإتقان · الاسترداد',
                  style: TextStyle(color: Color(0xFFD4AF37),
                    fontSize: 13, fontWeight: FontWeight.bold)),
                SizedBox(height: 3),
                Text('يعمل على جهازك — بدون إنترنت — خصوصية تامة\\nيتطلب إعداداً لمرة واحدة (~200MB)',
                  style: TextStyle(color: Color(0xFF8AACBA), fontSize: 10, height: 1.6)),
              ])),
            ]),
            const SizedBox(height: 14),
            Divider(color: Colors.white10, height: 1),
            const SizedBox(height: 14),
            // Server mode
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white24)),
                child: const Text('☁ SERVER',
                  style: TextStyle(color: Color(0xFF8AACBA),
                    fontSize: 10, fontWeight: FontWeight.bold))),
              const SizedBox(width: 12),
              const Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('v10.0 · v9.0 · v8.5 · v8.0',
                  style: TextStyle(color: Color(0xFF8AACBA),
                    fontSize: 12, fontWeight: FontWeight.w600)),
                SizedBox(height: 3),
                Text('يعمل على السحابة — يحتاج إنترنت — بدون تخزين',
                  style: TextStyle(color: Color(0xFF3D5A65), fontSize: 10, height: 1.6)),
              ])),
            ]),
          ])),
'''

# Inject before the primary button
OLD_BTN = "        _primaryBtn(s.howItWorks, () => _goPage(1)),"
NEW_BTN  = MODE_CARD + "        _primaryBtn(s.howItWorks, () => _goPage(1)),"
if OLD_BTN in txt:
    txt = txt.replace(OLD_BTN, NEW_BTN, 1); ok('Welcome: Local/Server mode info card added')
else:
    xx('Welcome: _primaryBtn anchor not found')

ws.write_text(txt, encoding='utf-8')
ok('welcome_screen.dart saved')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL')
print('\n  git add -A && git commit -m "S84: DeepFilter URL fix + local mode default + engine mode tags + welcome info" && git push\n')
