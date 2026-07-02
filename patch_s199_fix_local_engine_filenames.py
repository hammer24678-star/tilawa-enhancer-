#!/usr/bin/env python3
"""
patch_s199_fix_local_engine_filenames.py — S199

Local-mode bugs found by diffing LocalEngineRunner.kt's engine map/extraction
list against the actual files bundled in assets/engines/ (per the repo dump's
ASSETS listing). assets/engines/ contains: bayan_ve_v2fix.py,
engine_isteidad_v21.py, engine_itiqan_v6_official.py, engine_safaa_v3_fixed.py,
engine_safaa_v4.py, hakim_gen_v2.py, idrak_text_v2.py, ihyaa_ve.py,
miraat_ref_v2.py, naqaa_v1_tested.py, noor_v5.py — note there is NO
engine_tajalli_v1.py, true_engine_itiqan_v2_fixed.py, or engine_ihya_v3.py.

  BUG-1  (CRITICAL — won't compile) extractEngines()'s file list has a `//`
         comment placed mid-line, which comments out the rest of that
         physical line in Kotlin — silently eating the comma and the next
         two list entries (engine_v100.py, engine_v90.py). The result is two
         adjacent string literals with no comma between them: a syntax
         error.

  BUG-2  (CRITICAL — silently broken at runtime) v11.0 "الصفاء/Safaa" is the
         app's DEFAULT engine (`_engine = 'v11.0'` in home_screen.dart) and
         is localOnly — it can ONLY run through the local proot path, never
         the server. Its mapped script, engine_tajalli_v1.py, does not
         exist in assets, so local processing with the default engine has
         always failed (the file is never extracted, then proot fails to
         exec a script that was never copied). Fixed to point at the real
         file, engine_safaa_v4.py (same one S172/S149 already established
         as the live Safaa engine elsewhere in this codebase).

  BUG-3  Same problem for v11.1 "الإتقان/Itiqan" (also localOnly) — mapped
         to true_engine_itiqan_v2_fixed.py, which doesn't exist. Fixed to
         engine_itiqan_v6_official.py, the real bundled file.

  BUG-4  v11.3 "الإحياء/Ihya" — mapped to engine_ihya_v3.py, which doesn't
         exist; the real bundled file is ihyaa_ve.py. (Not currently
         reachable from the engine picker UI, but fixed for consistency and
         because patch_android.py's own template has the identical bug.)

  BUG-5  Same three filename fixes applied to patch_android.py's embedded
         MAIN_ACTIVITY_KT / LocalEngineRunner.kt template strings, so a
         future full regen via patch_android.py doesn't reintroduce any of
         this.

NOT touched: v10.0/v9.0/v8.5/v8.0/v7.0 map to engine_v100.py etc., which also
don't exist — but these engines are explicitly server-only (no localOnly
flag) and home_screen.dart's _process() already redirects them to v11.0
before ever calling the local engine, so they're unreachable dead code, not
a live bug. Left alone to minimize risk.

Usage:  python3 patch_s199_fix_local_engine_filenames.py /path/to/tilawa-enhancer
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
if not (REPO / 'lib').exists():
    print(f'ERROR: lib/ not found in {REPO}')
    sys.exit(1)

STAMP = REPO / '.patch_s199_fix_local_engine_filenames_done'
if STAMP.exists():
    print('patch_s199 already applied — delete .patch_s199_fix_local_engine_filenames_done to re-run')
    sys.exit(0)

def patch(path, old, new, tag, required=False):
    p = REPO / path
    if not p.exists():
        print(f'  SKIP  {tag} (file missing)'); return
    src = p.read_text(encoding='utf-8')
    if new.strip() in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        if required:
            print(f'  FAIL  {tag}: anchor not found'); sys.exit(1)
        print(f'  WARN  {tag}: anchor not found — skipped'); return
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

print(f'\n── S199  [repo: {REPO}] ──\n')

LE = 'android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt'
PA = 'patch_android.py'

# ── BUG-2/3/4: live LocalEngineRunner.kt — runEngine() script map ──────────
patch(LE,
    "                \"v11.0\" to \"engine_tajalli_v1.py\",\n"
    "                \"v11.1\" to \"true_engine_itiqan_v2_fixed.py\",\n"
    "                \"v11.2\" to \"engine_isteidad_v21.py\",\n"
    "                \"v11.3\" to \"engine_ihya_v3.py\",  // S195-BUG8: الإحياء local\n",

    "                \"v11.0\" to \"engine_safaa_v4.py\",  // S199-BUG-2: tajalli file never existed\n"
    "                \"v11.1\" to \"engine_itiqan_v6_official.py\",  // S199-BUG-3: ditto\n"
    "                \"v11.2\" to \"engine_isteidad_v21.py\",\n"
    "                \"v11.3\" to \"ihyaa_ve.py\",  // S199-BUG-4: real bundled filename\n",
    'BUG-2/3/4/LE: fix v11.0/v11.1/v11.3 script filenames in runEngine()',
    required=True)

patch(LE,
    "            )[engineId] ?: \"engine_tajalli_v1.py\"\n",
    "            )[engineId] ?: \"engine_safaa_v4.py\"  // S199: match BUG-2 fix\n",
    'BUG-2b/LE: fix fallback default script filename',
    required=True)

# ── BUG-1+2+3+4: live LocalEngineRunner.kt — extractEngines() list ─────────
patch(LE,
    "        listOf(\"engine_tajalli_v1.py\",\"true_engine_itiqan_v2_fixed.py\",\n"
    "               \"engine_isteidad_v21.py\",\"idrak_text_v2.py\",\"miraat_ref_v2.py\",\"hakim_gen_v2.py\",\"naqaa_v1_tested.py\",\"bayan_ve_v2fix.py\",\n"
    "               \"noor_v5.py\",\"engine_ihya_v3.py\"  // S195-BUG8,\"engine_v100.py\",\"engine_v90.py\",\n"
    "               \"engine_v85.py\",\"engine_v80.py\",\"engine_v70.py\").forEach { name ->\n",

    "        listOf(\"engine_safaa_v4.py\",\"engine_itiqan_v6_official.py\",  // S199-BUG-1/2/3: fixed names + missing comma\n"
    "               \"engine_isteidad_v21.py\",\"idrak_text_v2.py\",\"miraat_ref_v2.py\",\"hakim_gen_v2.py\",\"naqaa_v1_tested.py\",\"bayan_ve_v2fix.py\",\n"
    "               \"noor_v5.py\",\"ihyaa_ve.py\",\"engine_v100.py\",\"engine_v90.py\",  // S199-BUG-4: ihya real filename\n"
    "               \"engine_v85.py\",\"engine_v80.py\",\"engine_v70.py\").forEach { name ->\n",
    'BUG-1/LE: fix extractEngines() missing comma + wrong filenames',
    required=True)

# ── BUG-4/5: patch_android.py template — v11.3 mapping ─────────────────────
patch(PA,
    "                \"v11.3\" to \"engine_ihya_v3.py\",  // S196-BUG-F: الإحياء local\n",
    "                \"v11.3\" to \"ihyaa_ve.py\",  // S199-BUG-5: real bundled filename, not engine_ihya_v3.py\n",
    'BUG-5a/PA: fix v11.3 script filename in template',
    required=True)

# ── BUG-5: patch_android.py template — extractEngines() ihya entry ─────────
patch(PA,
    "               \"noor_v5.py\",\"engine_ihya_v3.py\").forEach { name ->  // S156 / S196-BUG-E\n",
    "               \"noor_v5.py\",\"ihyaa_ve.py\").forEach { name ->  // S156 / S199-BUG-5: real filename\n",
    'BUG-5b/PA: fix extractEngines() ihya filename in template',
    required=True)

# ──────────────────────────────────────────────────────────────────────────
STAMP.write_text('S199\n')
print('\n✅  patch_s199 done')
print()
print('  git add android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt patch_android.py')
print('  git commit -m "S199: fix local-mode engine filename mismatches (Safaa/Itiqan/Ihya never existed) + Kotlin syntax error in extractEngines()"')
print('  git push')
print()
print('  NOTE: native Android code — needs a full rebuild, not a hot reload.')
