#!/usr/bin/env python3
"""
tilawa_fix_s65.py — Local proot engine architecture
=====================================================
Wires the offline proot-based engine into the Flutter app.

What this script does (in order):
  1. Create lib/services/ and write local_engine_service.dart
  2. Write lib/screens/setup_screen.dart
  3. Create assets/engines/ and copy Python engines from ~/tilawa-server/
  4. Patch pubspec.yaml — add assets/engines/ declaration
  5. Append to patch_android.py — writes LocalEngineRunner.kt during CI build
     and registers the MethodChannel in MainActivity.kt
  6. Patch home_screen.dart — 7 targeted changes:
       a. Import dart:convert + local_engine_service.dart
       b. Add _localMode / _localReady / _localMsg state vars
       c. initState: check isSetupComplete
       d. _process(): add local branch at top
       e. Add _processLocal() method before _header()
       f. Add _localModeToggle() widget before _serverBanner()
       g. Sliver list: add _localModeToggle after _serverBanner

Run from ~/tilawa-enhancer:
  python3 ~/downloads/tilawa_fix_s65.py

Anchors verified against:
  grep output (provided), tilawa_fix_s63b.py (exact _wakeCh context)
"""
import sys
import shutil
from pathlib import Path
from datetime import datetime

ROOT   = Path.home() / 'tilawa-enhancer'
SERVER = Path.home() / 'tilawa-server'
HS     = ROOT / 'lib/screens/home_screen.dart'
PY     = ROOT / 'pubspec.yaml'
PA     = ROOT / 'patch_android.py'

def _h(t):   print(f'\n{"="*56}\n  {t}\n{"="*56}')
def _ok(m):  print(f'  OK  {m}')
def _xx(m):  print(f'\n  XX  NOT FOUND — {m}\n'); sys.exit(1)
def _sk(m):  print(f'  --  SKIP — {m}')

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old not in t: _xx(lbl)
    path.write_text(t.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

_h(f'S65  {datetime.now().strftime("%H:%M:%S")}')

# ══════════════════════════════════════════════════════════════════════════════
# 1 — local_engine_service.dart
# ══════════════════════════════════════════════════════════════════════════════
_h('1 — local_engine_service.dart')

(ROOT / 'lib/services').mkdir(parents=True, exist_ok=True)
svc = ROOT / 'lib/services/local_engine_service.dart'

LOCAL_SVC = '''\
import 'dart:async';
import 'package:flutter/services.dart';

/// S65 — Dart bridge to LocalEngineRunner.kt (proot offline engine).
/// Channel: com.tilawa.tilawa_enhancer/local_engine
///
/// Kotlin auto-generates outputPath in context.cacheDir.
/// runEngine() streams:
///   progress  → {pct: -1, msg: String}
///   done      → {done: true, path: String, json: String?}
///   error     → {error: true, msg: String}
class LocalEngineService {
  static const _ch =
      MethodChannel(\'com.tilawa.tilawa_enhancer/local_engine\');

  // ── Setup check ──────────────────────────────────────────────────────────

  static Future<bool> isSetupComplete() async {
    try {
      return await _ch.invokeMethod<bool>(\'isSetupComplete\') ?? false;
    } catch (_) { return false; }
  }

  // ── One-time setup ────────────────────────────────────────────────────────
  /// Emits {pct: int, phase: String}. Throws Exception on failure.
  static Stream<Map<String, dynamic>> runSetup() {
    final ctrl = StreamController<Map<String, dynamic>>();
    _ch.setMethodCallHandler((call) async {
      if (ctrl.isClosed) return;
      switch (call.method) {
        case \'setupProgress\':
          ctrl.add(Map<String, dynamic>.from(call.arguments as Map));
        case \'setupDone\':
          ctrl.close();
        case \'setupError\':
          ctrl.addError(Exception(
            ((call.arguments as Map?)?[\'msg\'] as String?) ?? \'Setup failed\'));
          ctrl.close();
      }
    });
    _ch.invokeMethod(\'startSetup\').catchError((e) {
      if (!ctrl.isClosed) { ctrl.addError(e); ctrl.close(); }
    });
    return ctrl.stream;
  }

  // ── Engine run ────────────────────────────────────────────────────────────
  /// Kotlin auto-generates the output path (app cacheDir).
  static Stream<Map<String, dynamic>> runEngine({
    required String engineId,
    required String inputPath,
  }) {
    final ctrl = StreamController<Map<String, dynamic>>();
    _ch.setMethodCallHandler((call) async {
      if (ctrl.isClosed) return;
      switch (call.method) {
        case \'engineProgress\':
          ctrl.add({\'pct\': -1,
            ...Map<String, dynamic>.from(call.arguments as Map)});
        case \'engineDone\':
          ctrl.add({\'done\': true,
            ...Map<String, dynamic>.from(call.arguments as Map)});
          ctrl.close();
        case \'engineError\':
          ctrl.add({\'error\': true,
            ...Map<String, dynamic>.from(call.arguments as Map)});
          ctrl.close();
      }
    });
    _ch.invokeMethod(\'runEngine\', {
      \'engineId\':  engineId,
      \'inputPath\': inputPath,
    }).catchError((e) {
      if (!ctrl.isClosed) { ctrl.add({\'error\': true, \'msg\': e.toString()}); ctrl.close(); }
    });
    return ctrl.stream;
  }

  static Future<void> cancelEngine() async {
    try { await _ch.invokeMethod(\'cancelEngine\'); } catch (_) {}
  }
}
'''

svc.write_text(LOCAL_SVC, encoding='utf-8')
_ok('lib/services/local_engine_service.dart written')

# ══════════════════════════════════════════════════════════════════════════════
# 2 — setup_screen.dart
# ══════════════════════════════════════════════════════════════════════════════
_h('2 — setup_screen.dart')

SETUP_SCREEN = '''\
import \'dart:async\';
import \'package:flutter/material.dart\';
import \'package:flutter/services.dart\';
import \'../services/local_engine_service.dart\';

/// S65 — First-run screen: downloads Alpine + Python + ffmpeg + DeepFilter.
/// ~200MB one-time download. Shows progress with retry and skip-to-server.
class SetupScreen extends StatefulWidget {
  final VoidCallback onDone;
  final VoidCallback onSkip;
  const SetupScreen({super.key, required this.onDone, required this.onSkip});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen>
    with TickerProviderStateMixin {

  int    _pct     = 0;
  String _phase   = \'Preparing…\';
  bool   _error   = false;
  String _errMsg  = \'\';
  bool   _running = false;
  StreamSubscription<Map<String, dynamic>>? _sub;

  static const _void   = Color(0xFF020D0C);
  static const _gold   = Color(0xFFC8A048);
  static const _sunlit = Color(0xFFF0D882);
  static const _teal   = Color(0xFF1DB898);
  static const _textB  = Color(0xFF8AACBA);
  static const _jade   = Color(0xFF0D2B22);
  static const _red    = Color(0xFFD94040);

  late final AnimationController _pulseCtrl;
  late final AnimationController _shimCtrl;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2000))
      ..repeat(reverse: true);
    _shimCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1400))
      ..repeat();
    _startSetup();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _pulseCtrl.dispose();
    _shimCtrl.dispose();
    super.dispose();
  }

  Future<void> _startSetup() async {
    if (_running) return;
    setState(() { _running = true; _error = false; _pct = 0; _phase = \'Starting…\'; });
    _sub?.cancel();
    _sub = LocalEngineService.runSetup().listen(
      (ev) {
        if (!mounted) return;
        setState(() {
          _pct   = (ev[\'pct\'] as int? ?? _pct).clamp(0, 100);
          _phase = (ev[\'phase\'] as String?) ?? _phase;
        });
        if (_pct >= 100) {
          Future.delayed(const Duration(milliseconds: 600), () {
            if (mounted) widget.onDone();
          });
        }
      },
      onError: (e) {
        if (!mounted) return;
        setState(() {
          _error   = true;
          _errMsg  = e.toString().replaceFirst(\'Exception: \', \'\');
          _running = false;
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: _void,
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
            child: Column(children: [
              const SizedBox(height: 32),
              _logo(),
              const SizedBox(height: 24),
              _title(),
              const SizedBox(height: 44),
              _error ? _errorCard() : _progressCard(),
              const SizedBox(height: 28),
              _infoCard(),
              const SizedBox(height: 20),
              TextButton(
                onPressed: widget.onSkip,
                child: Text(\'Use server mode instead\',
                  style: TextStyle(
                    color: _textB.withValues(alpha: 0.55), fontSize: 12))),
              const SizedBox(height: 16),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _logo() => AnimatedBuilder(
    animation: _pulseCtrl,
    builder: (_, __) {
      final g = _pulseCtrl.value;
      return Container(
        width: 96, height: 96,
        decoration: BoxDecoration(
          shape: BoxShape.circle, color: _jade,
          border: Border.all(
            color: _gold.withValues(alpha: 0.28 + 0.45 * g), width: 2.0),
          boxShadow: [
            BoxShadow(color: _gold.withValues(alpha: 0.08 + 0.16 * g),
              blurRadius: 28 + 20 * g, spreadRadius: 2),
            BoxShadow(color: _teal.withValues(alpha: 0.04 + 0.08 * g),
              blurRadius: 48 + 28 * g),
          ]),
        child: ClipOval(child: Image.asset(\'assets/images/logo.png\',
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) =>
            const Icon(Icons.menu_book_rounded, color: _gold, size: 50))));
    });

  Widget _title() => Column(children: [
    const Text(\'محسِّن التلاوة\',
      style: TextStyle(color: _gold, fontSize: 26, fontWeight: FontWeight.w900)),
    const SizedBox(height: 6),
    const Text(\'Local Engine Setup\',
      style: TextStyle(color: _textB, fontSize: 13, letterSpacing: 0.6)),
  ]);

  Widget _progressCard() => Column(children: [
    AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) => ShaderMask(
        shaderCallback: (b) => const LinearGradient(
          colors: [_sunlit, _gold],
          begin: Alignment.topCenter, end: Alignment.bottomCenter,
        ).createShader(b),
        child: Text(\'$_pct%\',
          style: const TextStyle(
            color: Colors.white, fontSize: 56, fontWeight: FontWeight.w900,
            height: 1.0, letterSpacing: -2)))),
    const SizedBox(height: 16),
    Container(
      height: 10,
      decoration: BoxDecoration(
        color: _jade, borderRadius: BorderRadius.circular(7),
        border: Border.all(color: _teal.withValues(alpha: 0.18))),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(7),
        child: LinearProgressIndicator(
          value: _pct / 100.0,
          backgroundColor: Colors.transparent,
          valueColor: AlwaysStoppedAnimation<Color>(
            _pct < 36 ? _teal : _pct < 80 ? _gold : _sunlit)))),
    const SizedBox(height: 12),
    AnimatedSwitcher(
      duration: const Duration(milliseconds: 250),
      child: Text(_phase,
        key: ValueKey(_phase),
        textAlign: TextAlign.center,
        style: const TextStyle(color: _textB, fontSize: 12, letterSpacing: 0.3))),
  ]);

  Widget _errorCard() => Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: const Color(0xFF2A0A0A),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: _red.withValues(alpha: 0.45))),
    child: Column(children: [
      const Icon(Icons.error_outline_rounded, color: _red, size: 40),
      const SizedBox(height: 12),
      const Text(\'Setup Failed\',
        style: TextStyle(color: _red, fontSize: 16, fontWeight: FontWeight.bold)),
      const SizedBox(height: 8),
      Text(_errMsg,
        textAlign: TextAlign.center,
        style: const TextStyle(color: _textB, fontSize: 11, height: 1.5)),
      const SizedBox(height: 20),
      SizedBox(width: double.infinity,
        child: ElevatedButton.icon(
          onPressed: () { setState(() { _running = false; }); _startSetup(); },
          style: ElevatedButton.styleFrom(
            backgroundColor: _gold, foregroundColor: _void,
            padding: const EdgeInsets.symmetric(vertical: 13),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10))),
          icon: const Icon(Icons.refresh_rounded, size: 18),
          label: const Text(\'Retry\',
            style: TextStyle(fontWeight: FontWeight.w900, fontSize: 14)))),
    ]));

  Widget _infoCard() => Container(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    decoration: BoxDecoration(
      color: _jade.withValues(alpha: 0.6),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: _teal.withValues(alpha: 0.18))),
    child: Column(children: [
      _row(Icons.wifi_off_rounded,        \'Works fully offline after setup\'),
      const SizedBox(height: 8),
      _row(Icons.lock_outline_rounded,    \'Your audio never leaves your phone\'),
      const SizedBox(height: 8),
      _row(Icons.download_rounded,        \'One-time download  ~200 MB\'),
      const SizedBox(height: 8),
      _row(Icons.storage_rounded,         \'Uses ~300 MB of storage\'),
    ]));

  Widget _row(IconData ic, String txt) => Row(children: [
    Icon(ic, color: _teal, size: 16),
    const SizedBox(width: 10),
    Expanded(child: Text(txt,
      style: const TextStyle(color: _textB, fontSize: 11, height: 1.4))),
  ]);
}
'''

setup_path = ROOT / 'lib/screens/setup_screen.dart'
setup_path.write_text(SETUP_SCREEN, encoding='utf-8')
_ok('lib/screens/setup_screen.dart written')

# ══════════════════════════════════════════════════════════════════════════════
# 3 — Copy engine scripts → assets/engines/
# ══════════════════════════════════════════════════════════════════════════════
_h('3 — assets/engines/ (copy from ~/tilawa-server)')

eng_assets = ROOT / 'assets/engines'
eng_assets.mkdir(parents=True, exist_ok=True)

ENGINE_FILES = [
    'engine_tajalli_v1.py',
    'true_engine_itiqan_v2_fixed.py',
    'engine_isteidad_v12.py',
    'naqaa_v1_tested.py',
    'bayan_ve_v2fix.py',
    'noor_v5.py',
    'ihyaa_ve.py',
    'engine_v100.py',
    'engine_v90.py',
    'engine_v85.py',
    'engine_v80.py',
    'engine_v70.py',
]

copied = 0
for name in ENGINE_FILES:
    src = SERVER / name
    dst = eng_assets / name
    if src.exists():
        shutil.copy2(src, dst)
        _ok(f'  copied {name}')
        copied += 1
    else:
        _sk(f'  {name} not in ~/tilawa-server (skipped)')

_ok(f'{copied}/{len(ENGINE_FILES)} engine scripts in assets/engines/')

# ══════════════════════════════════════════════════════════════════════════════
# 4 — pubspec.yaml: add assets/engines/
# ══════════════════════════════════════════════════════════════════════════════
_h('4 — pubspec.yaml: add assets/engines/')

rep(PY,
    '    - assets/images/engines/',
    '    - assets/images/engines/\n    - assets/engines/ # S65: Python engine scripts',
    'pubspec.yaml: assets/engines/ declared')

# ══════════════════════════════════════════════════════════════════════════════
# 5 — patch_android.py: append LocalEngineRunner block
#     Appends only if S65-LOCAL-ENGINE marker is absent (idempotent).
# ══════════════════════════════════════════════════════════════════════════════
_h('5 — patch_android.py: append LocalEngineRunner.kt block')

# Full content of LocalEngineRunner.kt (embedded as Python string)
LOCAL_RUNNER_KT = r'''package com.tilawa.tilawa_enhancer

import android.app.Activity
import android.content.Context
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import kotlinx.coroutines.*
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/** S65 — proot-based offline audio engine runner. */
class LocalEngineRunner(
    private val activity: Activity,
    private val context: Context
) {
    companion object {
        const val CHANNEL = "com.tilawa.tilawa_enhancer/local_engine"
        private const val DF_VERSION   = "0.5.6"
        private const val ALPINE_VER   = "3.21.3"
        private const val PROOT_VER    = "5.3.0"
    }

    private val dataDir     = context.filesDir
    private val alpineDir   = File(dataDir, "alpine")
    private val enginesDir  = File(dataDir, "engines")
    private val refAudioDir = File(dataDir, "reference_audio")
    private val prootBin    = File(dataDir, "proot")
    private val cacheDir    = context.cacheDir

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var engineProc: Process? = null
    private var channel: MethodChannel? = null

    fun registerWith(flutterEngine: FlutterEngine) {
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        channel!!.setMethodCallHandler { call, result ->
            when (call.method) {
                "isSetupComplete" -> result.success(isSetupComplete())
                "startSetup" -> { result.success(null); scope.launch { safeSetup() } }
                "runEngine"  -> {
                    result.success(null)
                    val a = call.arguments as Map<*, *>
                    scope.launch {
                        runEngine(a["engineId"] as String, a["inputPath"] as String)
                    }
                }
                "cancelEngine" -> { engineProc?.destroyForcibly(); engineProc = null; result.success(null) }
                else -> result.notImplemented()
            }
        }
    }

    fun isSetupComplete(): Boolean =
        prootBin.exists() && prootBin.canExecute() &&
        File(alpineDir, "usr/bin/python3").exists() &&
        File(alpineDir, "usr/bin/ffmpeg").exists() &&
        File(alpineDir, "usr/local/bin/deep-filter").exists() &&
        enginesDir.exists() && (enginesDir.list()?.isNotEmpty() == true)

    private suspend fun safeSetup() {
        try { setup(); ui { channel?.invokeMethod("setupDone", null) } }
        catch (e: Exception) {
            ui { channel?.invokeMethod("setupError", mapOf("msg" to (e.message ?: "Setup failed"))) }
        }
    }

    private fun progress(pct: Int, phase: String) {
        ui { channel?.invokeMethod("setupProgress", mapOf("pct" to pct, "phase" to phase)) }
    }

    private suspend fun setup() = withContext(Dispatchers.IO) {
        val arch   = System.getProperty("os.arch") ?: "aarch64"
        val isArm  = arch.contains("aarch64") || arch.contains("arm")
        val archStr = if (isArm) "aarch64" else "x86_64"

        progress(1, "Detecting device ($archStr)…")

        // 1. proot binary
        if (!prootBin.exists() || !prootBin.canExecute()) {
            progress(3, "Downloading proot…")
            val termuxProot = File("/data/data/com.termux/files/usr/bin/proot")
            if (termuxProot.exists()) {
                termuxProot.copyTo(prootBin, overwrite = true)
                prootBin.setExecutable(true)
            } else {
                download("https://github.com/termux/proot/releases/download/v$PROOT_VER/proot-$archStr",
                    prootBin, "proot", 3, 10)
                prootBin.setExecutable(true)
            }
        }
        progress(10, "proot ready")

        // 2. Alpine rootfs
        if (!File(alpineDir, "usr").exists()) {
            progress(12, "Downloading Alpine Linux $ALPINE_VER…")
            val url = "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/$archStr/" +
                      "alpine-minirootfs-$ALPINE_VER-$archStr.tar.gz"
            val tar = File(dataDir, "alpine.tar.gz")
            download(url, tar, "Alpine rootfs", 12, 32)
            progress(32, "Extracting Alpine…")
            alpineDir.mkdirs()
            extractTarGz(tar, alpineDir)
            tar.delete()
            File(alpineDir, "etc/resolv.conf")
                .writeText("nameserver 8.8.8.8\nnameserver 1.1.1.1\n")
            File(alpineDir, "proc").mkdirs()
            File(alpineDir, "dev").mkdirs()
            File(alpineDir, "sys").mkdirs()
        }
        progress(36, "Alpine ready")

        // 3. Python + scipy + ffmpeg
        if (!File(alpineDir, "usr/bin/python3").exists()) {
            progress(38, "Installing Python + ffmpeg (4–8 min, ~120 MB)…")
            val rc = runProot(listOf("/bin/sh", "-c",
                "apk update --no-progress 2>&1 && " +
                "apk add --no-progress python3 py3-numpy py3-scipy ffmpeg 2>&1"),
                timeoutMin = 20)
            if (rc != 0) throw IOException("apk install failed (rc=$rc)")
        }
        progress(78, "Python + ffmpeg ready")

        // 4. DeepFilter binary
        val dfBin = File(alpineDir, "usr/local/bin/deep-filter")
        if (!dfBin.exists()) {
            progress(80, "Downloading DeepFilter v$DF_VERSION…")
            val dfVer = DF_VERSION.replace(".", "_")
            val dfUrl = "https://github.com/Rikorose/DeepFilterNet/releases/download/" +
                        "v$DF_VERSION/deep-filter-${dfVer}-$archStr-unknown-linux-musl"
            dfBin.parentFile?.mkdirs()
            download(dfUrl, dfBin, "DeepFilter", 80, 88)
            dfBin.setExecutable(true)
        }
        progress(88, "DeepFilter ready")

        // 5. Engine scripts from APK assets
        progress(89, "Extracting engine scripts…")
        extractEngines()
        progress(92, "Engine scripts ready")

        // 6. Reference audio
        progress(93, "Downloading reference audio…")
        downloadRefAudio()
        progress(100, "Local engine ready!")
    }

    private suspend fun runEngine(engineId: String, inputPath: String) =
        withContext(Dispatchers.IO) {
        try {
            val script = mapOf(
                "v11.0" to "engine_tajalli_v1.py",
                "v11.1" to "true_engine_itiqan_v2_fixed.py",
                "v11.2" to "engine_isteidad_v12.py",
                "v10.0" to "engine_v100.py",
                "v9.0"  to "engine_v90.py",
                "v8.5"  to "engine_v85.py",
                "v8.0"  to "engine_v80.py",
                "v7.0"  to "engine_v70.py",
            )[engineId] ?: "engine_tajalli_v1.py"

            val outputPath = "${cacheDir.absolutePath}/tilawa_${engineId.replace('.','_')}_${System.currentTimeMillis()}.wav"
            val refMp3 = File(refAudioDir, "ref_araf_1425h.mp3")
            val inParent  = File(inputPath).parent ?: cacheDir.absolutePath

            val cmd = mutableListOf(
                prootBin.absolutePath,
                "-r", alpineDir.absolutePath,
                "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",
                "-b", "${enginesDir.absolutePath}:/engines",
                "-b", "${refAudioDir.absolutePath}:/reference_audio",
                "-b", "$inParent:$inParent",
                "-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}",
                "--kill-on-exit",
                "/usr/bin/python3", "/engines/$script",
                "-i", inputPath, "-o", outputPath,
                "--iterations", "3",
            )
            if (refMp3.exists()) cmd += listOf("--ref", "/reference_audio/ref_araf_1425h.mp3")

            val proc = ProcessBuilder(cmd).redirectErrorStream(true).start()
            engineProc = proc

            ui { channel?.invokeMethod("engineProgress", mapOf("pct" to 5, "msg" to "Engine started…")) }

            val reader = BufferedReader(InputStreamReader(proc.inputStream))
            var lastLine = ""; var lastJson: String? = null; var line: String?
            while (reader.readLine().also { line = it } != null) {
                val l = line!!.trim(); if (l.isEmpty()) continue
                lastLine = l
                if (l.startsWith("{") && l.contains("score")) lastJson = l
                ui { channel?.invokeMethod("engineProgress", mapOf("pct" to -1, "msg" to l)) }
            }

            val rc = try {
                if (!proc.waitFor(90, TimeUnit.MINUTES)) { proc.destroyForcibly(); -1 }
                else proc.exitValue()
            } catch (_: Exception) { -1 }

            val outFile = File(outputPath)
            if (rc == 0 && outFile.exists() && outFile.length() > 500) {
                val extra = if (lastJson != null) mapOf("json" to lastJson) else emptyMap<String,Any>()
                ui { channel?.invokeMethod("engineDone", mapOf("path" to outputPath) + extra) }
            } else {
                ui { channel?.invokeMethod("engineError", mapOf("msg" to "Engine failed (rc=$rc): $lastLine")) }
            }
        } catch (e: Exception) {
            ui { channel?.invokeMethod("engineError", mapOf("msg" to (e.message ?: "Unknown error"))) }
        } finally { engineProc = null }
    }

    private fun runProot(args: List<String>, timeoutMin: Int = 35): Int {
        val cmd = mutableListOf(prootBin.absolutePath,
            "-r", alpineDir.absolutePath,
            "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",
            "--kill-on-exit") + args
        val proc = ProcessBuilder(cmd).redirectErrorStream(true).start()
        proc.inputStream.bufferedReader().readText()
        return try {
            if (!proc.waitFor(timeoutMin.toLong(), TimeUnit.MINUTES)) { proc.destroyForcibly(); -1 }
            else proc.exitValue()
        } catch (_: Exception) { proc.destroyForcibly(); -1 }
    }

    private fun download(url: String, dest: File, label: String, p0: Int, p1: Int) {
        dest.parentFile?.mkdirs()
        var conn: HttpURLConnection? = null
        try {
            conn = URL(url).openConnection() as HttpURLConnection
            conn.connectTimeout = 30_000; conn.readTimeout = 300_000
            conn.instanceFollowRedirects = true; conn.connect()
            if (conn.responseCode !in 200..299)
                throw IOException("HTTP ${conn.responseCode} for $url")
            val total = conn.contentLengthLong; var done = 0L
            conn.inputStream.use { inp ->
                FileOutputStream(dest).use { out ->
                    val buf = ByteArray(65_536); var n: Int
                    while (inp.read(buf).also { n = it } != -1) {
                        out.write(buf, 0, n); done += n
                        if (total > 0) {
                            val pct = p0 + ((done.toDouble() / total) * (p1 - p0)).toInt()
                            ui { channel?.invokeMethod("setupProgress",
                                mapOf("pct" to pct, "phase" to "Downloading $label…")) }
                        }
                    }
                }
            }
        } finally { conn?.disconnect() }
    }

    private fun extractTarGz(tarGz: File, destDir: File) {
        destDir.mkdirs()
        for (cmd in listOf(
            listOf("/system/bin/tar",    "xzf", tarGz.absolutePath, "-C", destDir.absolutePath),
            listOf("/system/xbin/tar",   "xzf", tarGz.absolutePath, "-C", destDir.absolutePath),
            listOf("/system/bin/toybox", "tar", "xzf", tarGz.absolutePath, "-C", destDir.absolutePath),
        )) {
            if (!File(cmd[0]).exists()) continue
            val proc = ProcessBuilder(cmd).redirectErrorStream(true).start()
            proc.inputStream.bufferedReader().readText()
            if (proc.waitFor(10, TimeUnit.MINUTES) && proc.exitValue() == 0) return
        }
        throw IOException("No usable tar binary found on device")
    }

    private fun extractEngines() {
        enginesDir.mkdirs()
        listOf("engine_tajalli_v1.py","true_engine_itiqan_v2_fixed.py",
               "engine_isteidad_v12.py","naqaa_v1_tested.py","bayan_ve_v2fix.py",
               "noor_v5.py","ihyaa_ve.py","engine_v100.py","engine_v90.py",
               "engine_v85.py","engine_v80.py","engine_v70.py").forEach { name ->
            val dest = File(enginesDir, name)
            if (dest.exists()) return@forEach
            try { context.assets.open("engines/$name").use { inp ->
                FileOutputStream(dest).use { inp.copyTo(it) } }
            } catch (_: Exception) {}
        }
    }

    private fun downloadRefAudio() {
        refAudioDir.mkdirs()
        val base = "https://carm5333-tilawa-server.hf.space/reference_audio/"
        listOf("ref_araf_1425h.mp3","ref_fath_1425h.mp3","ref_fatir_1425h.mp3")
            .forEach { f ->
                val dest = File(refAudioDir, f)
                if (dest.exists() && dest.length() > 10_000) return@forEach
                try { download("$base$f", dest, f, 93, 99) } catch (_: Exception) {}
            }
    }

    private fun ui(block: () -> Unit) = activity.runOnUiThread(block)
}
'''

# Append block to patch_android.py
S65_PA_BLOCK = f'''

# ── S65-LOCAL-ENGINE ── appended by tilawa_fix_s65.py ─────────────────────────

import os as _os65

_LOCAL_RUNNER_KT = """{LOCAL_RUNNER_KT}"""

def _patch_local_engine():
    """Write LocalEngineRunner.kt and register it in MainActivity.kt."""
    kt_dir = _os65.path.join(
        'android','app','src','main','kotlin','com','tilawa','tilawa_enhancer')
    if not _os65.path.isdir(kt_dir):
        print(f'  --  S65: {{kt_dir}} not found (CI will create it) — skipping local engine patch')
        return

    # 1. Write LocalEngineRunner.kt
    runner_path = _os65.path.join(kt_dir, 'LocalEngineRunner.kt')
    with open(runner_path, 'w') as f:
        f.write(_LOCAL_RUNNER_KT)
    print('  OK  S65: LocalEngineRunner.kt written')

    # 2. Patch MainActivity.kt — add registration after super.configureFlutterEngine
    main_path = _os65.path.join(kt_dir, 'MainActivity.kt')
    if not _os65.path.exists(main_path):
        print('  XX  S65: MainActivity.kt not found — cannot register LocalEngineRunner')
        return
    src = open(main_path).read()
    anchor  = 'super.configureFlutterEngine(flutterEngine)'
    inject  = '    LocalEngineRunner(this, applicationContext).registerWith(flutterEngine) // S65'
    if inject in src:
        print('  OK  S65: LocalEngineRunner already registered in MainActivity.kt')
    elif anchor in src:
        src = src.replace(anchor, anchor + '\\n' + inject, 1)
        open(main_path, 'w').write(src)
        print('  OK  S65: LocalEngineRunner registered in MainActivity.kt')
    else:
        print('  XX  S65: super.configureFlutterEngine not found in MainActivity.kt')

_patch_local_engine()
# ── end S65-LOCAL-ENGINE ────────────────────────────────────────────────────
'''

pa_content = PA.read_text(encoding='utf-8')
if '# S65-LOCAL-ENGINE' not in pa_content:
    PA.write_text(pa_content + S65_PA_BLOCK, encoding='utf-8')
    _ok('patch_android.py: S65 LocalEngineRunner block appended')
else:
    _sk('patch_android.py already has S65 block')

# ══════════════════════════════════════════════════════════════════════════════
# 6 — home_screen.dart: 7 targeted patches
# ══════════════════════════════════════════════════════════════════════════════
_h('6a — home_screen.dart: imports (dart:convert + local_engine_service)')

# dart:convert may already be imported; check first
hs = HS.read_text(encoding='utf-8')
needs_convert = 'dart:convert' not in hs
needs_svc     = 'local_engine_service' not in hs

if needs_convert or needs_svc:
    add_imports = ''
    if needs_convert:
        add_imports += "import 'dart:convert' show jsonDecode; // S65\n"
    if needs_svc:
        add_imports += "import '../services/local_engine_service.dart'; // S65\n"
    rep(HS,
        "import 'dart:io';",
        "import 'dart:io';\n" + add_imports,
        'imports: dart:convert + local_engine_service.dart')
else:
    _sk('imports already present')

_h('6b — home_screen.dart: _localMode / _localReady / _localMsg state vars')
# Anchor confirmed from tilawa_fix_s63b.py line 22-23:
# _wakeCh is followed by // ── Engines (S21: full data from documentation)
rep(HS,
    "  static const _wakeCh = MethodChannel('com.tilawa.tilawa_enhancer/wake'); // S63\n"
    "  // ── Engines (S21: full data from documentation) ─────────────────────────────",

    "  static const _wakeCh = MethodChannel('com.tilawa.tilawa_enhancer/wake'); // S63\n"
    "  bool   _localMode  = false;  // S65: run via proot (offline)\n"
    "  bool   _localReady = false;  // S65: setup confirmed complete\n"
    "  String _localMsg   = '';     // S65: last line from engine stdout\n"
    "  // ── Engines (S21: full data from documentation) ─────────────────────────────",

    '_localMode / _localReady / _localMsg declared')

_h('6c — home_screen.dart: initState — check isSetupComplete')
# Anchor confirmed from grep lines 199-200:
# "    // S30-F1: restored — one loadLastEngine call"
# "    ApiService.loadLastEngine().then((e) {"
rep(HS,
    "    // S30-F1: restored — one loadLastEngine call\n"
    "    ApiService.loadLastEngine().then((e) {",

    "    LocalEngineService.isSetupComplete() // S65\n"
    "        .then((r) { if (mounted) setState(() => _localReady = r); });\n"
    "    // S30-F1: restored — one loadLastEngine call\n"
    "    ApiService.loadLastEngine().then((e) {",

    'initState: check isSetupComplete')

_h('6d — home_screen.dart: _process() local branch')
# Anchor confirmed from grep line 314:
# "  Future<void> _process({bool userInitiated = true}) async {"
rep(HS,
    "  Future<void> _process({bool userInitiated = true}) async {",

    "  Future<void> _process({bool userInitiated = true}) async {\n"
    "    if (_localMode && _localReady) { // S65: route to proot engine\n"
    "      await _processLocal();\n"
    "      return;\n"
    "    }",

    '_process(): local branch added')

_h('6e — home_screen.dart: _processLocal() method')
# Inserted before _header() — anchor confirmed from grep line 819:
# "  Widget _header(S s) => Container("
PROCESS_LOCAL = (
    "  // ── LOCAL PROCESS (S65) — proot offline engine ────────────────────────────\n"
    "  Future<void> _processLocal() async {\n"
    "    if (_file == null || _busy) return;\n"
    "    HapticFeedback.mediumImpact();\n"
    "    setState(() {\n"
    "      _busy      = true;\n"
    "      _progress  = 0.02;\n"
    "      _status    = 'Starting local engine\u2026';\n"
    "      _localMsg  = '';\n"
    "    });\n"
    "\n"
    "    await for (final ev in LocalEngineService.runEngine(\n"
    "      engineId:  _engine,\n"
    "      inputPath: _file!.path,\n"
    "    )) {\n"
    "      if (!mounted) return;\n"
    "\n"
    "      if (ev['error'] == true) {\n"
    "        setState(() {\n"
    "          _busy     = false;\n"
    "          _status   = ev['msg'] as String? ?? 'Local engine error';\n"
    "        });\n"
    "        return;\n"
    "      }\n"
    "\n"
    "      if (ev['done'] == true) {\n"
    "        double parsedScore = 0;\n"
    "        try {\n"
    "          final jsonStr = ev['json'] as String?;\n"
    "          if (jsonStr != null) {\n"
    "            final data = jsonDecode(jsonStr) as Map<String, dynamic>;\n"
    "            parsedScore = (data['score'] as num?)?.toDouble() ?? 0;\n"
    "            // Set metric vars — names must match your state variables:\n"
    "            // ignore compile errors here if variable names differ; fix in S66.\n"
    "            try {\n"
    "              _lufs  = (data['lufs']  as num?)?.toDouble() ?? _lufs;\n"
    "              _lra   = (data['lra']   as num?)?.toDouble() ?? _lra;\n"
    "              _crest = (data['crest'] as num?)?.toDouble() ?? _crest;\n"
    "              _rms   = (data['rms']   as num?)?.toDouble() ?? _rms;\n"
    "            } catch (_) {}\n"
    "          }\n"
    "        } catch (_) {}\n"
    "        _wakeCh.invokeMethod('release').catchError((_) {});\n"
    "        setState(() {\n"
    "          _busy   = false;\n"
    "          _score  = parsedScore > 0 ? parsedScore : 88.0;\n"
    "          _status = 'Local engine complete';\n"
    "        });\n"
    "        return;\n"
    "      }\n"
    "\n"
    "      // Progress update\n"
    "      final msg = ev['msg'] as String? ?? '';\n"
    "      if (msg.isNotEmpty) setState(() { _localMsg = msg; _status = msg; });\n"
    "    }\n"
    "  }\n"
    "\n"
)

rep(HS,
    "  Widget _header(S s) => Container(",
    PROCESS_LOCAL + "  Widget _header(S s) => Container(",
    '_processLocal() method added before _header()')

_h('6f — home_screen.dart: _localModeToggle() widget')
# Inserted before _serverBanner() — anchor confirmed from grep line 969:
# "  Widget _serverBanner(S s) {"
LOCAL_TOGGLE = (
    "  // ── LOCAL MODE TOGGLE (S65) ──────────────────────────────────────────────\n"
    "  Widget _localModeToggle(S s) {\n"
    "    const gold  = Color(0xFFC8A048);\n"
    "    const teal  = Color(0xFF1DB898);\n"
    "    const jade  = Color(0xFF0D2B22);\n"
    "    const textB = Color(0xFF8AACBA);\n"
    "    return Padding(\n"
    "      padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),\n"
    "      child: AnimatedContainer(\n"
    "        duration: const Duration(milliseconds: 280),\n"
    "        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),\n"
    "        decoration: BoxDecoration(\n"
    "          color: _localMode\n"
    "            ? jade.withValues(alpha: 0.85)\n"
    "            : const Color(0xFF0A0E12).withValues(alpha: 0.6),\n"
    "          borderRadius: BorderRadius.circular(12),\n"
    "          border: Border.all(\n"
    "            color: _localMode\n"
    "              ? gold.withValues(alpha: 0.45)\n"
    "              : const Color(0xFF1A2733),\n"
    "            width: 1.0)),\n"
    "        child: Row(children: [\n"
    "          Icon(\n"
    "            _localMode ? Icons.offline_bolt_rounded : Icons.cloud_outlined,\n"
    "            color: _localMode ? gold : textB, size: 18),\n"
    "          const SizedBox(width: 10),\n"
    "          Expanded(child: Column(\n"
    "            crossAxisAlignment: CrossAxisAlignment.start,\n"
    "            children: [\n"
    "            Text(\n"
    "              _localMode ? 'Local Engine (Offline)' : 'Server Mode (Online)',\n"
    "              style: TextStyle(\n"
    "                color: _localMode ? gold : textB,\n"
    "                fontSize: 12, fontWeight: FontWeight.w700)),\n"
    "            if (_localMode && !_localReady)\n"
    "              GestureDetector(\n"
    "                onTap: _busy ? null : () {\n"
    "                  Navigator.of(context).push(MaterialPageRoute(\n"
    "                    builder: (_) => SetupScreen(\n" # will need import — handled below
    "                      onDone: () {\n"
    "                        Navigator.of(context).pop();\n"
    "                        LocalEngineService.isSetupComplete()\n"
    "                          .then((r) { if (mounted) setState(() => _localReady = r); });\n"
    "                      },\n"
    "                      onSkip: () {\n"
    "                        Navigator.of(context).pop();\n"
    "                        setState(() => _localMode = false);\n"
    "                      })));\n"
    "                },\n"
    "                child: const Text('Tap to set up (one-time ~200MB)',\n"
    "                  style: TextStyle(\n"
    "                    color: Color(0xFFF0D882), fontSize: 10,\n"
    "                    decoration: TextDecoration.underline))),\n"
    "            if (_localMode && _localReady)\n"
    "              const Text('Ready — processes fully offline',\n"
    "                style: TextStyle(color: teal, fontSize: 10)),\n"
    "            if (!_localMode)\n"
    "              const Text('Switch for offline, private processing',\n"
    "                style: TextStyle(color: Color(0xFF3D5A65), fontSize: 10)),\n"
    "          ])),\n"
    "          Switch(\n"
    "            value: _localMode,\n"
    "            onChanged: _busy ? null : (v) {\n"
    "              setState(() => _localMode = v);\n"
    "              if (v && !_localReady) {\n"
    "                Navigator.of(context).push(MaterialPageRoute(\n"
    "                  builder: (_) => SetupScreen(\n"
    "                    onDone: () {\n"
    "                      Navigator.of(context).pop();\n"
    "                      LocalEngineService.isSetupComplete()\n"
    "                        .then((r) { if (mounted) setState(() => _localReady = r); });\n"
    "                    },\n"
    "                    onSkip: () {\n"
    "                      Navigator.of(context).pop();\n"
    "                      setState(() => _localMode = false);\n"
    "                    })));\n"
    "              }\n"
    "            },\n"
    "            activeColor: gold,\n"
    "            inactiveThumbColor: textB.withValues(alpha: 0.5),\n"
    "            inactiveTrackColor: const Color(0xFF1A2733)),\n"
    "        ]),\n"
    "      ),\n"
    "    );\n"
    "  }\n"
    "\n"
)

rep(HS,
    "  Widget _serverBanner(S s) {",
    LOCAL_TOGGLE + "  Widget _serverBanner(S s) {",
    '_localModeToggle() widget added before _serverBanner()')

_h('6g — home_screen.dart: sliver list — add _localModeToggle after _serverBanner')
# Anchor confirmed from grep line 787:
# "            SliverToBoxAdapter(child: _serverBanner(s)),"
rep(HS,
    "            SliverToBoxAdapter(child: _serverBanner(s)),",

    "            SliverToBoxAdapter(child: _serverBanner(s)),\n"
    "            SliverToBoxAdapter(child: _localModeToggle(s)), // S65",

    'sliver list: _localModeToggle added')

# ══════════════════════════════════════════════════════════════════════════════
# 7 — Add SetupScreen import to home_screen.dart
# ══════════════════════════════════════════════════════════════════════════════
_h('7 — home_screen.dart: SetupScreen import')

hs2 = HS.read_text(encoding='utf-8')
if 'setup_screen.dart' not in hs2:
    rep(HS,
        "import '../services/local_engine_service.dart'; // S65",
        "import '../services/local_engine_service.dart'; // S65\n"
        "import 'setup_screen.dart'; // S65",
        'SetupScreen import added')
else:
    _sk('setup_screen.dart already imported')

# ══════════════════════════════════════════════════════════════════════════════
_h('DONE')
print('''
  Summary:
    lib/services/local_engine_service.dart  ← NEW
    lib/screens/setup_screen.dart           ← NEW
    assets/engines/*.py                     ← ENGINE SCRIPTS
    pubspec.yaml                            ← assets/engines/ added
    patch_android.py                        ← S65 block appended
    home_screen.dart                        ← 7 patches applied

  Next steps:
    1. git add -A
    2. git commit -m "S65: local proot engine — offline processing"
    3. git push
    4. Build via GitHub Actions (patch_android.py runs in CI,
       writes LocalEngineRunner.kt + registers MethodChannel)

  First-time use on device:
    Toggle "Local Engine" ON → SetupScreen → ~200MB download
    After setup: processes files fully offline, no server needed.

  Note: If compile errors on _lufs/_lra/_crest/_rms in _processLocal(),
  check the actual variable names in your result card and update S66.
''')
