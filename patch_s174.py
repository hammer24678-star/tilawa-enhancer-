#!/usr/bin/env python3
"""
patch_s174.py — S174: Bug fixes

B1  patch_android.py (_LOCAL_RUNNER_KT)
        E2a: runEngine dispatch passes aggressive          [S173 missed CI]
        E2b: runEngine signature adds aggressive param     [S173 missed CI]
        E2c: append --aggressive to safaa cmd              [S173 missed CI]
B2  patch_android.py (_LOCAL_RUNNER_KT) + local_engine_service.dart
        runProotCmd: Kotlin returned null immediately; audio editor always
        got {'rc':0,'out':''} even on failure.
        Fix: run blocking inside coroutine, call result.success(rc,out) at end.
B3  local_engine_service.dart
        runProotCmd missing inputPath/outputPath params.
        Without them, proot never adds bind mounts → user audio files
        outside cacheDir are inaccessible inside proot (محرر الصوت).
B4  home_screen.dart
        _aggressive not persisted via SharedPreferences — resets to false
        on every app restart.
B5  patch_android.py (_LOCAL_RUNNER_KT)
        Dead variable `val refMp3` in runEngine.
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent

def fail(msg):
    print(f'  FAIL  {msg}'); sys.exit(1)

def patch(path, old, new, tag):
    p = Path(path)
    if not p.exists(): fail(f'{path} not found')
    src = p.read_text(encoding='utf-8')
    if old not in src:
        # check if already applied
        key = new.strip()[:60]
        if key in src:
            print(f'  SKIP  {tag} (already applied)'); return
        fail(f'{tag}: anchor not found in {path}')
    if new.strip() in src:
        print(f'  SKIP  {tag} (already applied)'); return
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

STAMP = Path('.patch_s174_done')
if STAMP.exists():
    print('patch_s174: already applied — delete .patch_s174_done to re-run'); sys.exit(0)

print('\n── S174: Bug fixes ─────────────────────────────────────────────────────────')

PA = 'patch_android.py'
DART_SVC = 'lib/services/local_engine_service.dart'
HOME = 'lib/screens/home_screen.dart'

# ════════════════════════════════════════════════════════════════════════════════
# B1-E2a — runEngine dispatch in _LOCAL_RUNNER_KT must pass aggressive
# ════════════════════════════════════════════════════════════════════════════════
patch(PA,
    '''                    scope.launch {
                        runEngine(a["engineId"] as String, a["inputPath"] as String)
                    }''',
    '''                    scope.launch {
                        runEngine(a["engineId"] as String, a["inputPath"] as String,
                            (a["aggressive"] as? Boolean) ?: false)  // S173
                    }''',
    'B1-E2a: runEngine dispatch passes aggressive (patch_android.py)')

# ════════════════════════════════════════════════════════════════════════════════
# B1-E2b — runEngine signature
# ════════════════════════════════════════════════════════════════════════════════
patch(PA,
    '    private suspend fun runEngine(engineId: String, inputPath: String) =',
    '    private suspend fun runEngine(engineId: String, inputPath: String,\n'
    '            aggressive: Boolean = false) =  // S173',
    'B1-E2b: runEngine signature adds aggressive (patch_android.py)')

# ════════════════════════════════════════════════════════════════════════════════
# B1-E2c — append --aggressive before ProcessBuilder
# ════════════════════════════════════════════════════════════════════════════════
patch(PA,
    '            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {\n'
    '                environment()["HOME"] = "/root"',
    '            // S173: --aggressive flag for الصفاء v4 only\n'
    '            if (script.startsWith("engine_safaa_v4") && aggressive) {\n'
    '                cmd += listOf("--aggressive")\n'
    '            }\n'
    '\n'
    '            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {\n'
    '                environment()["HOME"] = "/root"',
    'B1-E2c: append --aggressive to safaa cmd (patch_android.py)')

# ════════════════════════════════════════════════════════════════════════════════
# B2 — runProotCmd: replace fire-and-forget events with result.success(rc,out)
# ════════════════════════════════════════════════════════════════════════════════
patch(PA,
    '                "runProotCmd" -> {  // S172b: fixed events + file binds\n'
    '                    result.success(null)\n'
    '                    val a       = call.arguments as Map<*, *>\n'
    '                    val cmd     = (a["cmd"] as? String) ?: ""\n'
    '                    val inFile  = (a["inputPath"] as? String) ?: ""\n'
    '                    val outFile = (a["outputPath"] as? String) ?: ""\n'
    '                    val tmMin   = (a["timeoutMin"] as? Int) ?: 10\n'
    '                    scope.launch {\n'
    '                        val extra = mutableListOf<String>()\n'
    '                        listOf(inFile, outFile).forEach { p ->\n'
    '                            if (p.isNotEmpty()) {\n'
    '                                val dir = File(p).parent ?: return@forEach\n'
    '                                extra += listOf("-b", "$dir:$dir")\n'
    '                            }\n'
    '                        }\n'
    '                        extra += listOf("-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}")\n'
    '                        context.getExternalFilesDir(null)?.absolutePath?.let { ed ->\n'
    '                            extra += listOf("-b", "$ed:$ed") }\n'
    '                        val (rc, out) = runProotWithBinds(listOf("/bin/sh", "-c", cmd), extra, tmMin)\n'
    '                        if (rc == 0) {\n'
    '                            ui { channel?.invokeMethod("engineDone",\n'
    '                                mapOf("done" to true, "path" to outFile, "json" to out)) }\n'
    '                        } else {\n'
    '                            ui { channel?.invokeMethod("engineError",\n'
    '                                mapOf("msg" to "ffmpeg rc=$rc: ${out.takeLast(300)}")) }\n'
    '                        }\n'
    '                    }\n'
    '                }',
    '                "runProotCmd" -> {  // S172b+S174-B2: returns real rc/out via result.success\n'
    '                    val a       = call.arguments as Map<*, *>\n'
    '                    val cmd     = (a["cmd"] as? String) ?: ""\n'
    '                    val inFile  = (a["inputPath"] as? String) ?: ""\n'
    '                    val outFile = (a["outputPath"] as? String) ?: ""\n'
    '                    val tmMin   = (a["timeoutMin"] as? Int) ?: 10\n'
    '                    scope.launch {\n'
    '                        val extra = mutableListOf<String>()\n'
    '                        listOf(inFile, outFile).forEach { p ->\n'
    '                            if (p.isNotEmpty()) {\n'
    '                                val dir = File(p).parent ?: return@forEach\n'
    '                                extra += listOf("-b", "$dir:$dir")\n'
    '                            }\n'
    '                        }\n'
    '                        extra += listOf("-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}")\n'
    '                        context.getExternalFilesDir(null)?.absolutePath?.let { ed ->\n'
    '                            extra += listOf("-b", "$ed:$ed") }\n'
    '                        val (rc, out) = runProotWithBinds(listOf("/bin/sh", "-c", cmd), extra, tmMin)\n'
    '                        ui { result.success(mapOf("rc" to rc, "out" to out)) }  // S174-B2\n'
    '                    }\n'
    '                }',
    'B2: runProotCmd returns real result (patch_android.py)')

# ════════════════════════════════════════════════════════════════════════════════
# B3 — local_engine_service.dart: add inputPath/outputPath to runProotCmd
# ════════════════════════════════════════════════════════════════════════════════
patch(DART_SVC,
    '  // S161: run an arbitrary shell command via proot (for AudioLab editor)\n'
    '  static Future<Map<String, dynamic>> runProotCmd(\n'
    '    String cmd, {int timeoutMin = 10}) async {\n'
    '    try {\n'
    '      final r = await _ch.invokeMethod<Map>(\'runProotCmd\',\n'
    '          {\'cmd\': cmd, \'timeoutMin\': timeoutMin});\n'
    '      return Map<String, dynamic>.from(r ?? {\'rc\': 0, \'out\': \'\'});\n'
    '    } catch (e) {\n'
    '      return {\'rc\': -1, \'out\': e.toString()};\n'
    '    }\n'
    '  }',
    '  // S161: run an arbitrary shell command via proot (for AudioLab editor)\n'
    '  // S174-B3: inputPath/outputPath trigger extra proot bind mounts so\n'
    '  //          user audio files outside cacheDir are accessible inside proot.\n'
    '  static Future<Map<String, dynamic>> runProotCmd(\n'
    '    String cmd, {\n'
    '    String inputPath  = \'\',  // S174-B3: adds -b bind for file\'s parent dir\n'
    '    String outputPath = \'\',  // S174-B3\n'
    '    int timeoutMin = 10,\n'
    '  }) async {\n'
    '    try {\n'
    '      final r = await _ch.invokeMethod<Map>(\'runProotCmd\', {\n'
    '        \'cmd\':        cmd,\n'
    '        \'inputPath\':  inputPath,\n'
    '        \'outputPath\': outputPath,\n'
    '        \'timeoutMin\': timeoutMin,\n'
    '      });\n'
    '      return Map<String, dynamic>.from(r ?? {\'rc\': 0, \'out\': \'\'});\n'
    '    } catch (e) {\n'
    '      return {\'rc\': -1, \'out\': e.toString()};\n'
    '    }\n'
    '  }',
    'B3: runProotCmd adds inputPath/outputPath (local_engine_service.dart)')

# ════════════════════════════════════════════════════════════════════════════════
# B4 — home_screen.dart: persist _aggressive in SharedPreferences
# ════════════════════════════════════════════════════════════════════════════════
# B4a — load on initState
patch(HOME,
    "    SharedPreferences.getInstance().then((p){if(mounted)setState(()=>_localMode=p.getBool(\"local_mode\")??false);});",
    "    SharedPreferences.getInstance().then((p){if(mounted)setState(()=>_localMode=p.getBool(\"local_mode\")??false);});\n"
    "    SharedPreferences.getInstance().then((p){if(mounted)setState(()=>_aggressive=p.getBool(\"aggressive_mode\")??false);});  // S174-B4",
    'B4a: load _aggressive from SharedPreferences on init')

# B4b — save on toggle change
patch(HOME,
    "            onChanged: _busy ? null : (v) {\n"
    "              setState(() => _aggressive = v);\n"
    "            },",
    "            onChanged: _busy ? null : (v) {\n"
    "              setState(() => _aggressive = v);\n"
    "              SharedPreferences.getInstance().then((p) => p.setBool('aggressive_mode', v));  // S174-B4\n"
    "            },",
    'B4b: save _aggressive to SharedPreferences on toggle')

# ════════════════════════════════════════════════════════════════════════════════
# B5 — remove dead variable `val refMp3` in patch_android.py _LOCAL_RUNNER_KT
# ════════════════════════════════════════════════════════════════════════════════
patch(PA,
    '            val refMp3 = File(refAudioDir, "ref_araf_1425h.mp3")\n'
    '            val inParent  = cacheDir.absolutePath',
    '            val inParent  = cacheDir.absolutePath  // S174-B5: removed dead refMp3 var',
    'B5: remove dead val refMp3 (patch_android.py)')

STAMP.write_text('S174\n')
print('\n✅  patch_s174 done')
print('   git add patch_android.py lib/services/local_engine_service.dart lib/screens/home_screen.dart')
print('   git commit -m "S174: B1 aggressive-to-CI, B2 runProotCmd returns real result, B3 proot binds, B4 persist aggressive, B5 dead var"')
print('   git push')
