#!/usr/bin/env python3
"""
patch_s31.py — Session 31 comprehensive UI polish

Fixes:
  F1. Welcome screen: add "Show Tutorial" in settings → resets seen_welcome
  F2. Engine card colors: gold engines (v8.0+) show muted gold when unselected
  F3. Add v8.7 engine to Flutter list with full description
  F4. Light / Dark mode toggle (new ThemeNotifier + toggle in settings)
  F5. Welcome screen: redesigned with better animations + 3 pages
  F6. main.dart: read isDark pref on launch
"""

from pathlib import Path
import sys

REPO     = Path(".")
HOME     = REPO / "lib/screens/home_screen.dart"
SETTINGS = REPO / "lib/screens/settings_screen.dart"
WELCOME  = REPO / "lib/screens/welcome_screen.dart"
MAIN     = REPO / "lib/main.dart"
LANG     = REPO / "lib/state/lang_provider.dart"

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"
errors = 0

def patch(path: Path, old: str, new: str, label: str) -> bool:
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] not found — {label}"); errors += 1; return False
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}"); return False
    n = text.count(old)
    if n > 1:
        print(f"{WARN} [{path.name}] anchor not unique ({n}×) — {label}"); errors += 1; return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True

def already(path: Path, marker: str, label: str) -> bool:
    if path.exists() and marker in path.read_text(encoding="utf-8"):
        print(f"{SKIP} [{path.name}] already applied — {label}")
        return True
    return False

# ═══════════════════════════════════════════════════════════════════════════
print("\n[F1] Settings — Show Tutorial reset button")
# ═══════════════════════════════════════════════════════════════════════════

if not already(SETTINGS, "// S31-F1", "F1: tutorial reset button"):
    patch(SETTINGS,
        "import 'package:flutter/material.dart';\n"
        "import 'package:url_launcher/url_launcher.dart';\n"
        "import '../state/lang_provider.dart';",
        "import 'package:flutter/material.dart';\n"
        "import 'package:shared_preferences/shared_preferences.dart'; // S31-F1\n"
        "import 'package:url_launcher/url_launcher.dart';\n"
        "import '../state/lang_provider.dart';\n"
        "import 'welcome_screen.dart'; // S31-F1",
        "F1-import: shared_prefs + welcome in settings")

if not already(SETTINGS, "// S31-F1-btn", "F1: tutorial tile in settings body"):
    patch(SETTINGS,
        "          // ── Target info ────────────────────────────────────────────────────\n"
        "          Container(",
        "          // ── S31-F1: Show Tutorial button ───────────────────────────────────\n"
        "          _tutorialTile(context, s),\n"
        "          const SizedBox(height: 4),\n"
        "          // ── Target info ────────────────────────────────────────────────────\n"
        "          Container(",
        "F1: tutorial tile inserted in settings body")

# Add _tutorialTile method — insert before the last closing } of the class
if not already(SETTINGS, "Widget _tutorialTile", "F1: _tutorialTile method"):
    patch(SETTINGS,
        "  Widget _langPill(",
        "  // S31-F1-btn\n"
        "  Widget _tutorialTile(BuildContext context, S s) => Container(\n"
        "    margin: const EdgeInsets.only(bottom: 18),\n"
        "    decoration: BoxDecoration(\n"
        "      color: const Color(0xFF161B22),\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      border: Border.all(color: const Color(0xFF21262D))),\n"
        "    child: ListTile(\n"
        "      leading: const Icon(Icons.play_lesson_rounded,\n"
        "        color: Color(0xFFD4AF37)),\n"
        "      title: Text(\n"
        "        s.ar ? 'عرض شاشة الترحيب' : 'Show Welcome Screen',\n"
        "        style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 14)),\n"
        "      subtitle: Text(\n"
        "        s.ar ? 'عرض دليل البداية مرة أخرى' : 'Re-show the onboarding guide',\n"
        "        style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),\n"
        "      trailing: const Icon(Icons.arrow_forward_ios_rounded,\n"
        "        size: 14, color: Color(0xFF484F58)),\n"
        "      onTap: () async {\n"
        "        final prefs = await SharedPreferences.getInstance();\n"
        "        await prefs.remove('seen_welcome');\n"
        "        if (!context.mounted) return;\n"
        "        Navigator.of(context).pushReplacement(\n"
        "          PageRouteBuilder(\n"
        "            pageBuilder: (_, __, ___) => const WelcomeScreen(),\n"
        "            transitionsBuilder: (_, anim, __, child) =>\n"
        "                FadeTransition(opacity: anim, child: child),\n"
        "            transitionDuration: const Duration(milliseconds: 400),\n"
        "          ));\n"
        "      },\n"
        "    ));\n"
        "\n"
        "  Widget _langPill(",
        "F1: _tutorialTile method added")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[F2] Engine card colors — gold engines muted gold when unselected")
# ═══════════════════════════════════════════════════════════════════════════

if not already(HOME, "// S31-F2", "F2: engine card gold tint unselected"):
    patch(HOME,
        "              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [\n"
        "                Text('≥${e.score.toInt()}', style: TextStyle(\n"
        "                  color: sel ? col : const Color(0xFF484F58),\n"
        "                  fontWeight: FontWeight.w800, fontSize: 15)),\n"
        "                Text('/100', style: const TextStyle(\n"
        "                  color: Color(0xFF484F58), fontSize: 8)),\n"
        "              ]),",
        "              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [\n"
        "                Text('≥${e.score.toInt()}', style: TextStyle(\n"
        "                  // S31-F2: gold engines → muted gold when unselected\n"
        "                  color: sel ? col\n"
        "                    : (e.colorCode == 'gold'\n"
        "                        ? const Color(0xFF6B5A2A)\n"
        "                        : const Color(0xFF484F58)),\n"
        "                  fontWeight: FontWeight.w800, fontSize: 15)),\n"
        "                Text('/100', style: TextStyle(\n"
        "                  color: sel ? col.withOpacity(0.45) : const Color(0xFF484F58),\n"
        "                  fontSize: 8)),\n"
        "              ]),",
        "F2: score color gold tint when unselected")

# Also tint the version id text for gold engines
if not already(HOME, "// S31-F2b", "F2b: version id gold tint"):
    patch(HOME,
        "                Row(children: [\n"
        "                  Text(e.id, style: TextStyle(\n"
        "                    color: sel ? col : const Color(0xFFC9D1D9),\n"
        "                    fontWeight: FontWeight.bold, fontSize: 13)),",
        "                Row(children: [\n"
        "                  Text(e.id, style: TextStyle(\n"
        "                    // S31-F2b\n"
        "                    color: sel ? col\n"
        "                      : (e.colorCode == 'gold'\n"
        "                          ? const Color(0xFF8B7535)\n"
        "                          : const Color(0xFFC9D1D9)),\n"
        "                    fontWeight: FontWeight.bold, fontSize: 13)),",
        "F2b: version id text gold tint for gold engines")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[F3] Add v8.7 engine to Flutter list")
# ═══════════════════════════════════════════════════════════════════════════

if not already(HOME, "'v8.7'", "F3: v8.7 engine entry"):
    patch(HOME,
        "    _EngineData(\n"
        "      'v8.5', '\u062a\u0642\u064a\u064a\u0645 \u0635\u0627\u062f\u0642', 'Honest Ceiling', 99.0,",
        "    _EngineData(\n"
        "      'v8.7', '\u0633\u0642\u0641 \u0645\u062f\u0631\u0648\u0633', 'Studied Ceiling', 99.0,\n"
        "      '', 'gold',\n"
        "      ['Bitrate Floor', 'Phrase 3s Min', 'Do-No-Harm Fix', 'LUFS \u00b118dB', 'LRA Sliding', 'Joint \u00b118dB'],\n"
        "      'إصلاح 6 أخطاء حرجة من v8.5: حد أدنى لمعدل البت يمنع تصنيف الملفات الهادئة خطأً، لا يُشغِّل تقدير LRA إلا لمقاطع أطول من 3 ثوانٍ، مقارنة Do-No-Harm بـ Crest القابل للتحقيق، نطاق قطع LUFS ±18dB، نافذة انزلاق وسيطة لـ LRA، نطاق ±18dB للكسب المشترك.',\n"
        "      '6 critical fixes from v8.5: bitrate floor stops quiet-file misclassification, phrase LRA requires 3s minimum, Do-No-Harm compares to achievable Crest, ±18dB LUFS trim range, sliding window median for LRA, ±18dB joint gain range.',\n"
        "    ),\n"
        "    _EngineData(\n"
        "      'v8.5', '\u062a\u0642\u064a\u064a\u0645 \u0635\u0627\u062f\u0642', 'Honest Ceiling', 99.0,",
        "F3: v8.7 added between v8.5 and v9.0 section")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[F4] Light/Dark mode — ThemeNotifier + main.dart + toggle in settings")
# ═══════════════════════════════════════════════════════════════════════════

# 1. Read isDark pref in main()
if not already(MAIN, "// S31-F4", "F4: isDark pref in main()"):
    patch(MAIN,
        "  final langAr = prefs.getBool('lang_ar') ?? true;\n"
        "  final seenWelcome = prefs.getBool('seen_welcome') ?? false;\n"
        "\n"
        "  runApp(TilawaApp(langAr: langAr, seenWelcome: seenWelcome));",
        "  final langAr      = prefs.getBool('lang_ar')      ?? true;\n"
        "  final seenWelcome = prefs.getBool('seen_welcome')  ?? false;\n"
        "  final isDark      = prefs.getBool('is_dark')       ?? true; // S31-F4\n"
        "\n"
        "  runApp(TilawaApp(\n"
        "    langAr: langAr, seenWelcome: seenWelcome, isDark: isDark));",
        "F4: isDark pref read in main()")

# 2. Add isDark to TilawaApp constructor
if not already(MAIN, "final bool isDark;", "F4: isDark field in TilawaApp"):
    patch(MAIN,
        "  final bool seenWelcome;\n"
        "  const TilawaApp({super.key, required this.langAr, required this.seenWelcome});",
        "  final bool seenWelcome;\n"
        "  final bool isDark;\n"
        "  const TilawaApp({super.key,\n"
        "    required this.langAr,\n"
        "    required this.seenWelcome,\n"
        "    required this.isDark, // S31-F4\n"
        "  });",
        "F4: isDark field added to TilawaApp")

# 3. Add _themeNotifier to _TilawaAppState
if not already(MAIN, "_themeNotifier", "F4: _themeNotifier in state"):
    patch(MAIN,
        "  late final ValueNotifier<bool> _langNotifier;\n"
        "\n"
        "  @override\n"
        "  void initState() {\n"
        "    super.initState();\n"
        "    // Created ONCE here — never again until the widget is destroyed.\n"
        "    _langNotifier = ValueNotifier<bool>(widget.langAr);\n"
        "  }\n"
        "\n"
        "  @override\n"
        "  void dispose() {\n"
        "    _langNotifier.dispose(); // properly released\n"
        "    super.dispose();\n"
        "  }",
        "  late final ValueNotifier<bool> _langNotifier;\n"
        "  late final ValueNotifier<bool> _themeNotifier; // S31-F4: true = dark\n"
        "\n"
        "  @override\n"
        "  void initState() {\n"
        "    super.initState();\n"
        "    _langNotifier  = ValueNotifier<bool>(widget.langAr);\n"
        "    _themeNotifier = ValueNotifier<bool>(widget.isDark);\n"
        "  }\n"
        "\n"
        "  @override\n"
        "  void dispose() {\n"
        "    _langNotifier.dispose();\n"
        "    _themeNotifier.dispose(); // S31-F4\n"
        "    super.dispose();\n"
        "  }",
        "F4: _themeNotifier added to state")

# 4. Wrap MaterialApp with theme support
if not already(MAIN, "ThemeProvider", "F4: ThemeProvider wrap"):
    patch(MAIN,
        "    return LangProvider(\n"
        "      notifier: _langNotifier,\n"
        "      child: ValueListenableBuilder<bool>(\n"
        "        valueListenable: _langNotifier,\n"
        "        builder: (context, _, __) {\n"
        "          final s = S(ar: _langNotifier.value);\n"
        "          return MaterialApp(\n"
        "            title: s.appName,\n"
        "            debugShowCheckedModeBanner: false,\n"
        "            theme: ThemeData(\n"
        "              colorScheme: const ColorScheme.dark(\n"
        "                primary: Color(0xFFD4AF37),\n"
        "                surface: Color(0xFF161B22),\n"
        "              ),\n"
        "              useMaterial3: true,\n"
        "              scaffoldBackgroundColor: const Color(0xFF0A0C10),\n"
        "              appBarTheme: const AppBarTheme(\n"
        "                backgroundColor: Color(0xFF0A0C10),\n"
        "                foregroundColor: Color(0xFFD4AF37),\n"
        "                elevation: 0,\n"
        "              ),\n"
        "            ),\n"
        "            home: widget.seenWelcome ? const HomeScreen() : const WelcomeScreen(),\n"
        "          );\n"
        "        },\n"
        "      ),\n"
        "    );",
        "    return ThemeProvider( // S31-F4\n"
        "      notifier: _themeNotifier,\n"
        "      child: LangProvider(\n"
        "        notifier: _langNotifier,\n"
        "        child: ValueListenableBuilder<bool>(\n"
        "          valueListenable: _langNotifier,\n"
        "          builder: (context, _lang, __) {\n"
        "            return ValueListenableBuilder<bool>(\n"
        "              valueListenable: _themeNotifier,\n"
        "              builder: (context, isDark, __) {\n"
        "                final s = S(ar: _langNotifier.value);\n"
        "                return MaterialApp(\n"
        "                  title: s.appName,\n"
        "                  debugShowCheckedModeBanner: false,\n"
        "                  themeMode: isDark ? ThemeMode.dark : ThemeMode.light,\n"
        "                  darkTheme: _buildDarkTheme(),\n"
        "                  theme: _buildLightTheme(),\n"
        "                  home: widget.seenWelcome\n"
        "                      ? const HomeScreen()\n"
        "                      : const WelcomeScreen(),\n"
        "                );\n"
        "              },\n"
        "            );\n"
        "          },\n"
        "        ),\n"
        "      ),\n"
        "    );",
        "F4: ThemeProvider wrap + dual theme MaterialApp")

# 5. Add theme builder methods + ThemeProvider class after TilawaApp
if not already(MAIN, "ThemeData _buildDarkTheme", "F4: theme builder methods"):
    patch(MAIN,
        "// ── FIX F1: TilawaApp must be StatefulWidget",
        "// ── S31-F4: Theme helpers & ThemeProvider ─────────────────────────────────────\n"
        "ThemeData _buildDarkTheme() => ThemeData(\n"
        "  colorScheme: const ColorScheme.dark(\n"
        "    primary: Color(0xFFD4AF37),\n"
        "    surface: Color(0xFF161B22),\n"
        "    onSurface: Color(0xFFC9D1D9),\n"
        "    background: Color(0xFF0A0C10),\n"
        "  ),\n"
        "  useMaterial3: true,\n"
        "  scaffoldBackgroundColor: const Color(0xFF0A0C10),\n"
        "  appBarTheme: const AppBarTheme(\n"
        "    backgroundColor: Color(0xFF0A0C10),\n"
        "    foregroundColor: Color(0xFFD4AF37),\n"
        "    elevation: 0,\n"
        "  ),\n"
        ");\n"
        "\n"
        "ThemeData _buildLightTheme() => ThemeData(\n"
        "  colorScheme: const ColorScheme.light(\n"
        "    primary: Color(0xFFB8941F),   // deeper gold for light bg\n"
        "    surface: Color(0xFFF3EED9),   // warm parchment\n"
        "    onSurface: Color(0xFF1A1400),\n"
        "    background: Color(0xFFFAF7EE),\n"
        "  ),\n"
        "  useMaterial3: true,\n"
        "  scaffoldBackgroundColor: const Color(0xFFFAF7EE),\n"
        "  cardColor: const Color(0xFFF3EED9),\n"
        "  appBarTheme: const AppBarTheme(\n"
        "    backgroundColor: Color(0xFFFAF7EE),\n"
        "    foregroundColor: Color(0xFFB8941F),\n"
        "    elevation: 0,\n"
        "  ),\n"
        ");\n"
        "\n"
        "// InheritedWidget so any screen can read and toggle the theme\n"
        "class ThemeProvider extends InheritedNotifier<ValueNotifier<bool>> {\n"
        "  const ThemeProvider({\n"
        "    super.key,\n"
        "    required ValueNotifier<bool> notifier,\n"
        "    required super.child,\n"
        "  }) : super(notifier: notifier);\n"
        "\n"
        "  static ValueNotifier<bool> of(BuildContext ctx) =>\n"
        "      ctx.dependOnInheritedWidgetOfExactType<ThemeProvider>()!.notifier!;\n"
        "\n"
        "  static bool isDark(BuildContext ctx) => of(ctx).value;\n"
        "\n"
        "  static Future<void> toggle(BuildContext ctx) async {\n"
        "    final n = of(ctx);\n"
        "    n.value = !n.value;\n"
        "    final prefs = await SharedPreferences.getInstance();\n"
        "    await prefs.setBool('is_dark', n.value);\n"
        "  }\n"
        "}\n"
        "\n"
        "// ── FIX F1: TilawaApp must be StatefulWidget",
        "F4: ThemeProvider + _buildDarkTheme + _buildLightTheme")

# Need to add SharedPreferences import to main.dart if not already there
if not already(MAIN, "package:shared_preferences/shared_preferences.dart", "F4: shared_prefs import in main"):
    patch(MAIN,
        "import 'package:flutter/material.dart';",
        "import 'package:flutter/material.dart';\n"
        "import 'package:shared_preferences/shared_preferences.dart'; // S31-F4 (if not already)",
        "F4: shared_prefs import in main.dart")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[F4b] Settings — Dark/Light mode toggle tile")
# ═══════════════════════════════════════════════════════════════════════════

if not already(SETTINGS, "// S31-F4b", "F4b: theme toggle in settings"):
    patch(SETTINGS,
        "          // ── S31-F1: Show Tutorial button ───────────────────────────────────\n"
        "          _tutorialTile(context, s),\n"
        "          const SizedBox(height: 4),",
        "          // ── S31-F4b: Dark / Light mode toggle ─────────────────────────────\n"
        "          _themeTile(context, s),\n"
        "          const SizedBox(height: 4),\n"
        "          // ── S31-F1: Show Tutorial button ───────────────────────────────────\n"
        "          _tutorialTile(context, s),\n"
        "          const SizedBox(height: 4),",
        "F4b: theme toggle tile inserted above tutorial tile")

if not already(SETTINGS, "Widget _themeTile", "F4b: _themeTile method"):
    patch(SETTINGS,
        "  // S31-F1-btn\n"
        "  Widget _tutorialTile(",
        "  // S31-F4b\n"
        "  Widget _themeTile(BuildContext context, S s) {\n"
        "    return ValueListenableBuilder<bool>(\n"
        "      valueListenable: ThemeProvider.of(context),\n"
        "      builder: (ctx, dark, _) => Container(\n"
        "        margin: const EdgeInsets.only(bottom: 18),\n"
        "        decoration: BoxDecoration(\n"
        "          color: const Color(0xFF161B22),\n"
        "          borderRadius: BorderRadius.circular(12),\n"
        "          border: Border.all(color: const Color(0xFF21262D))),\n"
        "        child: SwitchListTile(\n"
        "          secondary: Icon(\n"
        "            dark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,\n"
        "            color: const Color(0xFFD4AF37)),\n"
        "          title: Text(\n"
        "            s.ar ? 'الوضع الداكن' : 'Dark Mode',\n"
        "            style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 14)),\n"
        "          subtitle: Text(\n"
        "            dark\n"
        "              ? (s.ar ? 'الوضع الحالي' : 'Currently active')\n"
        "              : (s.ar ? 'الوضع الفاتح نشط' : 'Light mode active'),\n"
        "            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),\n"
        "          value: dark,\n"
        "          activeColor: const Color(0xFFD4AF37),\n"
        "          onChanged: (_) => ThemeProvider.toggle(ctx),\n"
        "        ),\n"
        "      ),\n"
        "    );\n"
        "  }\n"
        "\n"
        "  // S31-F1-btn\n"
        "  Widget _tutorialTile(",
        "F4b: _themeTile method added")

# Add ThemeProvider import to settings_screen.dart
if not already(SETTINGS, "import '../main.dart'", "F4b: main.dart import in settings"):
    patch(SETTINGS,
        "import '../state/lang_provider.dart';\n"
        "import 'welcome_screen.dart'; // S31-F1",
        "import '../state/lang_provider.dart';\n"
        "import '../main.dart' show ThemeProvider; // S31-F4b\n"
        "import 'welcome_screen.dart'; // S31-F1",
        "F4b: ThemeProvider import in settings_screen")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[F5] Welcome screen redesign — 3 pages, pulse animation, gold ring")
# ═══════════════════════════════════════════════════════════════════════════

WELCOME_NEW = '''\
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../state/lang_provider.dart';
import 'home_screen.dart';

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});
  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen>
    with TickerProviderStateMixin {
  late final AnimationController _fadeCtrl;
  late final AnimationController _pulseCtrl;
  late final Animation<double> _fade;
  late final Animation<Offset> _slide;
  late final Animation<double> _pulse;
  int _page = 0;

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));
    _pulseCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2200))
      ..repeat(reverse: true);

    _fade  = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeIn);
    _slide = Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .animate(CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOutCubic));
    _pulse = Tween<double>(begin: 0.85, end: 1.15)
        .animate(CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut));

    _fadeCtrl.forward();
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    _pulseCtrl.dispose();
    super.dispose();
  }

  void _goPage(int p) {
    HapticFeedback.selectionClick();
    _fadeCtrl.reset();
    setState(() => _page = p);
    _fadeCtrl.forward();
  }

  Future<void> _finish() async {
    HapticFeedback.lightImpact();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('seen_welcome', true);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        pageBuilder: (_, __, ___) => const HomeScreen(),
        transitionsBuilder: (_, anim, __, child) =>
            FadeTransition(opacity: anim, child: child),
        transitionDuration: const Duration(milliseconds: 500),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C10),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fade,
          child: SlideTransition(
            position: _slide,
            child: _page == 0 ? _page0(s) : _page == 1 ? _page1(s) : _page2(s),
          ),
        ),
      ),
    );
  }

  // ── Page 0: Brand splash ──────────────────────────────────────────────────
  Widget _page0(S s) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 32),
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Pulsing gold ring around logo
        AnimatedBuilder(
          animation: _pulse,
          builder: (_, child) => Container(
            width: 160, height: 160,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFFD4AF37)
                      .withOpacity(0.15 * _pulse.value),
                  blurRadius: 50 * _pulse.value,
                  spreadRadius: 10 * _pulse.value),
              ],
            ),
            child: child),
          child: Container(
            width: 160, height: 160,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: const Color(0xFFD4AF37).withOpacity(0.4),
                width: 1.5)),
            child: ClipOval(
              child: Image.asset('assets/images/logo.png', fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => Container(
                  color: const Color(0xFF1A1500),
                  child: const Icon(Icons.music_note,
                    color: Color(0xFFD4AF37), size: 70))))),
        ),
        const SizedBox(height: 40),
        Text(s.appName,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 36, fontWeight: FontWeight.bold,
            color: Color(0xFFD4AF37), height: 1.2,
            letterSpacing: -0.5)),
        const SizedBox(height: 8),
        Text(s.subtitle,
          style: const TextStyle(
            color: Color(0xFF8B949E), fontSize: 11,
            letterSpacing: 3.0)),
        const SizedBox(height: 36),
        Text(s.welcomeDesc,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Color(0xFFC9D1D9), fontSize: 14, height: 1.9)),
        const SizedBox(height: 48),
        _primaryBtn(s.howItWorks, () => _goPage(1)),
        const SizedBox(height: 14),
        TextButton(
          onPressed: _finish,
          child: Text(s.welcomeStart,
            style: const TextStyle(
              color: Color(0xFF8B949E), fontSize: 13))),
        const SizedBox(height: 14),
        _langToggle(context),
        const SizedBox(height: 8),
        // Page dots
        _dots(0),
      ],
    ),
  );

  // ── Page 1: How it works ──────────────────────────────────────────────────
  Widget _page1(S s) {
    final steps = [
      (Icons.audio_file_outlined,    s.step1),
      (Icons.tune_rounded,           s.step2),
      (Icons.cloud_sync_outlined,    s.step3),
      (Icons.download_done_rounded,  s.step4),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 28),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(s.howItWorks,
            style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontSize: 26, fontWeight: FontWeight.bold)),
          const SizedBox(height: 32),
          ...steps.asMap().entries.map((entry) => Padding(
            padding: const EdgeInsets.only(bottom: 18),
            child: Row(
              textDirection: TextDirection.rtl,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 44, height: 44,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: const Color(0xFFD4AF37), width: 1.3),
                    color: const Color(0xFF1A1500)),
                  child: Icon(entry.value.$1,
                    color: const Color(0xFFD4AF37), size: 20)),
                const SizedBox(width: 14),
                Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      s.ar
                        ? 'الخطوة ${entry.key + 1}'
                        : 'Step ${entry.key + 1}',
                      textDirection: TextDirection.rtl,
                      style: const TextStyle(
                        color: Color(0xFF484F58),
                        fontSize: 9, letterSpacing: 0.5)),
                    const SizedBox(height: 2),
                    Text(entry.value.\$2,
                      textDirection: TextDirection.rtl,
                      style: const TextStyle(
                        color: Color(0xFFC9D1D9),
                        fontSize: 13, height: 1.45)),
                  ],
                )),
              ],
            ),
          )),
          const SizedBox(height: 12),
          _primaryBtn(s.ar ? 'التالي' : 'Next', () => _goPage(2)),
          const SizedBox(height: 10),
          _dots(1),
        ],
      ),
    );
  }

  // ── Page 2: Engine tiers overview ────────────────────────────────────────
  Widget _page2(S s) {
    final tiers = [
      ('v10.0', s.ar ? 'الأثيريون — الأساس' : 'Aetherion Foundation',
        s.ar ? '٢٤ إصلاحاً — NR ثنائي — L-BFGS-B'
              : '24 fixes — Two-stage NR — L-BFGS-B EQ',
        const Color(0xFFD4AF37)),
      ('v9.0',  s.ar ? 'التطور' : 'The Evolution',
        s.ar ? 'بناء كامل — مُحسِّن مشترك LUFS+LRA'
              : 'Full rewrite — joint LUFS+LRA optimizer',
        const Color(0xFFD4AF37)),
      ('v8.x',  s.ar ? 'سلسلة الدقة' : 'Precision Series',
        s.ar ? 'v8.7 · v8.5 · v8.0 — تقدم تراكمي'
              : 'v8.7 · v8.5 · v8.0 — cumulative gains',
        const Color(0xFFC9A227)),
      ('v7.0',  s.ar ? 'كلاسيكي' : 'Classic',
        s.ar ? 'البنية المُثبَّتة الأساس — STABLE'
              : 'Proven foundational architecture — STABLE',
        const Color(0xFF8B949E)),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(s.ar ? 'محركات التحسين' : 'Enhancement Engines',
            style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(s.ar
            ? 'اختر محركك من الصفحة الرئيسية'
            : 'Choose your engine from the home screen',
            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12)),
          const SizedBox(height: 24),
          ...tiers.map((t) => Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.symmetric(
              horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: t.\$4.withOpacity(0.25))),
            child: Row(children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 7, vertical: 3),
                decoration: BoxDecoration(
                  color: t.\$4.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(5)),
                child: Text(t.\$1, style: TextStyle(
                  color: t.\$4, fontSize: 10,
                  fontWeight: FontWeight.bold))),
              const SizedBox(width: 12),
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(t.\$2, style: TextStyle(
                    color: t.\$4, fontSize: 12,
                    fontWeight: FontWeight.w600)),
                  Text(t.\$3, style: const TextStyle(
                    color: Color(0xFF8B949E), fontSize: 10,
                    height: 1.4)),
                ])),
            ]))),
          const SizedBox(height: 16),
          _primaryBtn(s.welcomeStart, _finish),
          const SizedBox(height: 10),
          _dots(2),
        ],
      ),
    );
  }

  Widget _dots(int active) => Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: List.generate(3, (i) => AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      margin: const EdgeInsets.symmetric(horizontal: 4),
      width:  i == active ? 20 : 6,
      height: 6,
      decoration: BoxDecoration(
        color: i == active
          ? const Color(0xFFD4AF37)
          : const Color(0xFF30363D),
        borderRadius: BorderRadius.circular(3)))));

  Widget _primaryBtn(String label, VoidCallback onTap) =>
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
            fontWeight: FontWeight.bold, fontSize: 16))));

  Widget _langToggle(BuildContext context) {
    final langNotifier = LangProvider.of(context);
    return ValueListenableBuilder<bool>(
      valueListenable: langNotifier,
      builder: (ctx, isAr, _) => GestureDetector(
        onTap: () => LangProvider.toggle(ctx),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFF21262D))),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(isAr ? 'EN' : '\u0639',
              style: const TextStyle(
                color: Color(0xFFD4AF37),
                fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(width: 6),
            const Icon(Icons.language,
              color: Color(0xFF8B949E), size: 16),
          ]))));
  }
}
'''

if not already(WELCOME, "// S31-F5", "F5: welcome screen rewrite"):
    # Just overwrite the whole file
    WELCOME.write_text(WELCOME_NEW, encoding="utf-8")
    print(f"{OK}  [welcome_screen.dart] F5: welcome screen redesigned (3 pages, pulse, dots)")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[F6] main.dart — add import for SharedPreferences if missing")
# ═══════════════════════════════════════════════════════════════════════════
# Check if SharedPreferences is already imported (may have been added by F4)
main_text = MAIN.read_text(encoding="utf-8")
if "shared_preferences" not in main_text:
    patch(MAIN,
        "import 'package:flutter/material.dart';",
        "import 'package:flutter/material.dart';\n"
        "import 'package:shared_preferences/shared_preferences.dart';",
        "F6: shared_prefs import")
else:
    print(f"{SKIP} [main.dart] SharedPreferences already imported")

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED \033[0m")
    print()
    print("What changed:")
    print("  F1. Settings: 'Show Welcome Screen' tile resets & re-shows tutorial")
    print("  F2. Engine cards: v8.0+ unselected → muted gold (not gray)")
    print("  F3. v8.7 added to engine list with full 6-fix description")
    print("  F4. Light/Dark mode: toggle in settings, persists to prefs")
    print("  F5. Welcome screen: 3 pages, pulsing ring, page dots, engine overview")
    print()
    print("Next:")
    print("  git add lib/main.dart \\")
    print("          lib/screens/home_screen.dart \\")
    print("          lib/screens/settings_screen.dart \\")
    print("          lib/screens/welcome_screen.dart")
    print("  git commit -m 'S31: welcome redesign + engine colors + v8.7 + dark/light mode'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} FAILED \033[0m")
    sys.exit(1)
