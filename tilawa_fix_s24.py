#!/usr/bin/env python3
"""
tilawa_fix_s24.py  -- Session 24 Server Overhaul
=================================================
Changes applied in this session:

  ENGINE:
    + engine_v8.1 added   (Android-Hardened, fixed SPECTRAL_BIAS + /tmp)
    - engine_v7.5 removed (superseded by v8.1)
    - engine_v7.6 removed (superseded by v8.1)

  FIXES:
    FIX score parsing     -- all engines now report real score (was stuck at 90)
    FIX /download_chunk   -- BUG 7: route documented but never implemented
    FIX JOBS memory leak  -- BUG 8: dict grew unbounded, now pruned at 200
    NEW /ping endpoint    -- fast Flutter wake detection
    FIX gunicorn --preload -- reduces cold-start / connection delay
    FIX README            -- engine list updated

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s24.py
"""

import os, sys, shutil, subprocess, urllib.request, json, time
from pathlib import Path
from datetime import datetime

# ── helpers (same pattern as S23) ─────────────────────────────────────────────
_log = []

def _h1(t):
    bar = "=" * 64
    print(f"\n{bar}\n  {t}\n{bar}")

def _h2(t): print(f"\n  -- {t}")
def _ok(m):   print(f"     OK  {m}")
def _warn(m): print(f"     !!  {m}")
def _err(m):  print(f"     XX  {m}")

def _rec(sid, label, ok):
    _log.append((sid, label, "[OK] PASS" if ok else "[XX] FAIL"))
    return ok

def _read(p):     return Path(p).read_text(encoding="utf-8")
def _write(p, t): Path(p).write_text(t, encoding="utf-8")

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
        _err("  Nearby context check failed -- see diff below:")
        return text, False
    if c > 1:
        _warn(f"Anchor found {c}x -- using first only -- {label}")
    _ok(f"Replaced -- {label}")
    return text.replace(old, new, 1), True

def _run(cmd, cwd=None, label="", timeout=180):
    r = subprocess.run(cmd, shell=True, cwd=str(cwd or HF_CLONE),
                       capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    ok  = r.returncode == 0
    ((_ok if ok else _err)(label or cmd))
    if not ok and out:
        for line in out.splitlines()[-6:]:
            print(f"        {line}")
    return ok, out

def _require(cond, msg):
    if not cond:
        _err(f"FATAL: {msg}")
        _print_summary()
        sys.exit(1)

def _health(label="health check"):
    _h2(label)
    try:
        req = urllib.request.Request(SERVER + "/", headers={"User-Agent": "s24"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        _ok(f"status: {data.get('status')}  "
            f"engines: {data.get('engines')}  "
            f"refs: {data.get('refs')}")
        return True
    except Exception as e:
        _warn(f"Health check failed: {e}")
        return False

def _print_summary():
    _h1("SUMMARY")
    print(f"\n  {'Step':<8}  {'Label':<52}  Result")
    print(f"  {'----':<8}  {'------':<52}  ------")
    for sid, label, result in _log:
        print(f"  {sid:<8}  {label:<52}  {result}")

# ── config ─────────────────────────────────────────────────────────────────────
HF_URL   = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
HF_CLONE = Path.home() / "tilawa-hf-clone"
SERVER   = "https://carm5333-tilawa-server.hf.space"
V81_SRC  = Path.home() / "tilawa-enhancer" / "engine_v81.py"
TS       = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP   = HF_CLONE / f".fix_backups/{TS}"

_h1("STARTING S24  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ======================================================================
#  STEP 1 -- Clone + verify
# ======================================================================
_h1("STEP 1 -- Clone HF Space + verify state")

_h2("1.1  Remove stale clone + fresh clone (skip LFS blobs)")
if HF_CLONE.exists():
    shutil.rmtree(HF_CLONE)
    _ok(f"Removed stale {HF_CLONE}")
ok11, _ = _run(f"GIT_LFS_SKIP_SMUDGE=1 git clone {HF_URL} {HF_CLONE}",
               cwd=Path.home(), label="git clone HF Space")
_rec("1.1", "HF Space cloned", ok11)
_require(ok11, "Clone failed -- check network / HF token")

_h2("1.2  Verify files present")
expected = ["app.py", "Dockerfile", "gunicorn.conf.py", "README.md",
            "engine_v70.py", "engine_v75.py", "engine_v76.py",
            "engine_v80.py", "requirements.txt"]
all_ok = True
for f in expected:
    p = HF_CLONE / f
    e = p.exists()
    sz = p.stat().st_size if e else 0
    ((_ok if e else _err)(f"{f}  ({sz:,} bytes)"))
    if not e: all_ok = False
_rec("1.2", "Expected files present", all_ok)
_require(all_ok, "Missing files in clone")

_h2("1.3  Verify engine_v81.py source available")
v81_ok = V81_SRC.exists()
((_ok if v81_ok else _err)(f"engine_v81.py  ({V81_SRC.stat().st_size:,} bytes)" if v81_ok else f"NOT FOUND: {V81_SRC}"))
_rec("1.3", "engine_v81.py source available", v81_ok)
_require(v81_ok, f"engine_v81.py not found at {V81_SRC}")

_h2("1.4  Backup originals")
BACKUP.mkdir(parents=True, exist_ok=True)
for f in ["app.py", "Dockerfile", "README.md"]:
    shutil.copy2(HF_CLONE / f, BACKUP / f)
_ok(f"Backups in {BACKUP}")
_rec("1.4", "Originals backed up", True)


# ======================================================================
#  STEP 2 -- Patch app.py
# ======================================================================
_h1("STEP 2 -- Patch app.py")

APP = HF_CLONE / "app.py"
app = _read(APP)
_ok(f"app.py read: {len(app):,} chars")

# ── 2.1 Docstring ──────────────────────────────────────────────────────
_h2("2.1  Update docstring (v2 -> v3)")
OLD_DOC = '''\
"""
tilawa-server app.py \u2014 v2 with chunked upload support
Handles files up to 300MB by splitting into 8MB chunks

Endpoints:
  GET  /                           \u2014 health check
  POST /upload                     \u2014 small files <10MB (legacy)
  POST /upload_start               \u2014 start chunked session \u2192 {job_id}
  POST /upload_chunk               \u2014 upload one chunk {job_id, index, total}
  POST /upload_finalize            \u2014 merge chunks + start engine {job_id, engine}
  GET  /status/<job_id>            \u2014 poll progress
  GET  /download/<job_id>          \u2014 stream output file
  GET  /download_chunk/<job_id>    \u2014 chunked download {offset, size}
  GET  /history                    \u2014 last 50 jobs
"""'''
NEW_DOC = '''\
"""
tilawa-server app.py \u2014 v3 (S24 overhaul)
Engines: v8.1 (Android-Hardened), v8.0 (Calibrated Precision), v7.0 (Stable Classic)

Endpoints:
  GET  /                           \u2014 health check + engine status
  GET  /ping                       \u2014 lightweight keepalive (S24)
  POST /upload                     \u2014 small files <10MB (legacy)
  POST /upload_start               \u2014 start chunked session \u2192 {job_id}
  POST /upload_chunk               \u2014 upload one chunk {job_id, index, total}
  POST /upload_finalize            \u2014 merge chunks + start engine {job_id, engine}
  GET  /status/<job_id>            \u2014 poll progress
  GET  /download/<job_id>          \u2014 stream output file
  GET  /download_chunk/<job_id>    \u2014 chunked download {offset, size}
  GET  /history                    \u2014 last 50 jobs
"""'''
app, ok21 = _replace_once(app, OLD_DOC, NEW_DOC, "docstring v2 -> v3")
_rec("2.1", "Docstring updated", ok21)

# ── 2.2 ENGINE_SCRIPTS: remove v7.5/v7.6, add v8.1 ───────────────────
_h2("2.2  ENGINE_SCRIPTS: remove v7.5+v7.6, add v8.1")
OLD_ENG = '''\
ENGINE_SCRIPTS = {
    "v8.0": BASE / "engine_v80.py",
    "v7.6": BASE / "engine_v76.py",
    "v7.5": BASE / "engine_v75.py",
    "v7.0": BASE / "engine_v70.py",
}'''
NEW_ENG = '''\
# S24: v8.1 added (Android-Hardened); v7.5 + v7.6 removed
ENGINE_SCRIPTS = {
    "v8.1": BASE / "engine_v81.py",
    "v8.0": BASE / "engine_v80.py",
    "v7.0": BASE / "engine_v70.py",
}'''
app, ok22 = _replace_once(app, OLD_ENG, NEW_ENG, "ENGINE_SCRIPTS dict")
_rec("2.2", "ENGINE_SCRIPTS updated", ok22)

# ── 2.3 Remove broken score elif block ────────────────────────────────
# The star/score elif was in a chain where earlier elif branches
# (Pass 1/2/3/4) would consume the line before the score elif was
# reached.  All four history entries showing score=90 confirms the
# hardcoded fallback was firing, not the parser.
_h2("2.3  Remove score elif (broken -- replaced by standalone /100 scan)")
OLD_SCORE_ELIF = (
    '                elif "\\u2605" in line or "\\u2b50" in line or "Score" in line.lower():\n'
    '                    job["progress"] = 95; job["label"] = "\u062d\u0633\u0627\u0628 \u0627\u0644\u0646\u062a\u064a\u062c\u0629..."\n'
    '                    import re as _re\n'
    '                    m = _re.search(r"(\\d+\\.?\\d*)/100", line) or \\\n'
    '                        _re.search(r"Score:\\s*(\\d+\\.?\\d*)", line)\n'
    '                    if m:\n'
    '                        try: job["score"] = float(m.group(1))\n'
    '                        except: pass\n'
    '                elif "LUFS=" in line:\n'
)
NEW_SCORE_ELIF = '                elif "LUFS=" in line:\n'
app, ok23 = _replace_once(app, OLD_SCORE_ELIF, NEW_SCORE_ELIF,
                           "remove star/score elif block")
_rec("2.3", "Score elif removed", ok23)

# ── 2.4 Add standalone /100 scan after LUFS block ─────────────────────
_h2("2.4  Add standalone /100 score scan (catches all engine formats)")
OLD_LUFS_BLOCK = (
    '                elif "LUFS=" in line:\n'
    '                    for part in line.split():\n'
    '                        try:\n'
    '                            if "LUFS=" in part:   job["lufs"]  = part.split("=")[1]\n'
    '                            elif "RMS=" in part:  job["rms"]   = part.split("=")[1]\n'
    '                            elif "Crest=" in part: job["crest"] = part.split("=")[1]\n'
    '                            elif "LRA=" in part:  job["lra"]   = part.split("=")[1]\n'
    '                        except: pass\n'
    '            proc.wait()\n'
)
NEW_LUFS_BLOCK = (
    '                elif "LUFS=" in line:\n'
    '                    for part in line.split():\n'
    '                        try:\n'
    '                            if "LUFS=" in part:   job["lufs"]  = part.split("=")[1]\n'
    '                            elif "RMS=" in part:  job["rms"]   = part.split("=")[1]\n'
    '                            elif "Crest=" in part: job["crest"] = part.split("=")[1]\n'
    '                            elif "LRA=" in part:  job["lra"]   = part.split("=")[1]\n'
    '                        except: pass\n'
    '                # S24 BUG-SCORE: standalone /100 scan -- runs on every line\n'
    '                # independent of elif chain; catches v80/v81 score in any format\n'
    '                if "/100" in line:\n'
    '                    import re as _re\n'
    '                    _m = _re.search(r"(\\d{2,3}\\.?\\d*)\\s*/\\s*100", line)\n'
    '                    if _m:\n'
    '                        try:\n'
    '                            _s = float(_m.group(1))\n'
    '                            if 50.0 <= _s <= 100.0:\n'
    '                                job["score"] = _s\n'
    '                                job["progress"] = 95\n'
    '                                job["label"] = "\u062d\u0633\u0627\u0628 \u0627\u0644\u0646\u062a\u064a\u062c\u0629..."\n'
    '                        except: pass\n'
    '            proc.wait()\n'
)
app, ok24 = _replace_once(app, OLD_LUFS_BLOCK, NEW_LUFS_BLOCK,
                           "add standalone /100 scan after LUFS block")
_rec("2.4", "Standalone /100 scan added", ok24)

# ── 2.5 Add _prune_jobs() function (BUG 8) ────────────────────────────
_h2("2.5  Add _prune_jobs() function (BUG 8 -- memory leak)")
OLD_STATUS_HDR = (
    '# \u2500\u2500 Status \u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '@app.route("/status/<job_id>")'
)
NEW_STATUS_HDR = (
    '# S24 BUG8: prune JOBS dict to prevent unbounded memory growth\n'
    'def _prune_jobs():\n'
    '    """Remove oldest done/error jobs once JOBS exceeds 200 entries."""\n'
    '    if len(JOBS) <= 200:\n'
    '        return\n'
    '    removable = [jid for jid, j in list(JOBS.items())\n'
    '                 if j.get("status") in ("done", "error")]\n'
    '    for jid in removable[:-100]:\n'
    '        JOBS.pop(jid, None)\n'
    '\n'
    '# \u2500\u2500 Status \u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '@app.route("/status/<job_id>")'
)
app, ok25 = _replace_once(app, OLD_STATUS_HDR, NEW_STATUS_HDR,
                           "_prune_jobs function before status route")
_rec("2.5", "_prune_jobs() function added", ok25)

# ── 2.6 Call _prune_jobs() in success block ───────────────────────────
_h2("2.6  Add _prune_jobs() call in success block")
OLD_HIST_CALL = (
    '        _add_history(job)\n'
    '\n'
    '    # Cleanup input\n'
)
NEW_HIST_CALL = (
    '        _add_history(job)\n'
    '        _prune_jobs()  # S24 BUG8\n'
    '\n'
    '    # Cleanup input\n'
)
app, ok26 = _replace_once(app, OLD_HIST_CALL, NEW_HIST_CALL,
                           "_prune_jobs call in success block")
_rec("2.6", "_prune_jobs() call added", ok26)

# ── 2.7 Add /download_chunk + /ping routes (BUG 7) ────────────────────
_h2("2.7  Add /download_chunk + /ping routes (BUG 7)")
OLD_HISTORY_ROUTE = (
    '# \u2500\u2500 History \u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '@app.route("/history")\n'
    'def history():\n'
    '    return jsonify({"jobs": HISTORY})'
)
NEW_HISTORY_ROUTE = (
    '# \u2500\u2500 Chunked Download \u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '# S24 BUG7: route was in docstring since v2 but never implemented\n'
    '@app.route("/download_chunk/<job_id>")\n'
    'def download_chunk(job_id):\n'
    '    job = JOBS.get(job_id)\n'
    '    if not job or job["status"] != "done":\n'
    '        return jsonify({"error": "not ready"}), 404\n'
    '    path = Path(job["out_path"])\n'
    '    if not path.exists():\n'
    '        return jsonify({"error": "file missing"}), 404\n'
    '    offset    = int(request.args.get("offset", 0))\n'
    '    size      = int(request.args.get("size", CHUNK_SIZE))\n'
    '    file_size = path.stat().st_size\n'
    '    with open(path, "rb") as f:\n'
    '        f.seek(offset)\n'
    '        data = f.read(size)\n'
    '    return Response(data, headers={\n'
    '        "Content-Type":   "audio/mpeg",\n'
    '        "Content-Length": str(len(data)),\n'
    '        "X-File-Size":    str(file_size),\n'
    '        "X-Offset":       str(offset),\n'
    '    })\n'
    '\n'
    '# \u2500\u2500 Ping \u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '# S24: fast endpoint for Flutter wake detection (no heavy DB scan)\n'
    '@app.route("/ping")\n'
    'def ping():\n'
    '    return jsonify({"ok": True, "t": time.time()})\n'
    '\n'
    '# \u2500\u2500 History \u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500'
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '@app.route("/history")\n'
    'def history():\n'
    '    return jsonify({"jobs": HISTORY})'
)
app, ok27 = _replace_once(app, OLD_HISTORY_ROUTE, NEW_HISTORY_ROUTE,
                           "/download_chunk + /ping routes before /history")
_rec("2.7", "/download_chunk + /ping routes added", ok27)

# ── Write app.py ──────────────────────────────────────────────────────
_h2("2.8  Write patched app.py")
_write(APP, app)
_ok(f"app.py written ({len(app):,} chars)")
_rec("2.8", "app.py written", True)


# ======================================================================
#  STEP 3 -- Verify all app.py patches
# ======================================================================
_h1("STEP 3 -- Verify all app.py patches")
app_v = _read(APP)

checks = [
    ("v8.1 in ENGINE_SCRIPTS",      '"v8.1": BASE / "engine_v81.py"' in app_v),
    ("v8.0 in ENGINE_SCRIPTS",      '"v8.0": BASE / "engine_v80.py"' in app_v),
    ("v7.0 in ENGINE_SCRIPTS",      '"v7.0": BASE / "engine_v70.py"' in app_v),
    ("v7.5 REMOVED",                '"v7.5"' not in app_v),
    ("v7.6 REMOVED",                '"v7.6"' not in app_v),
    ("docstring v3 present",        "v3 (S24 overhaul)" in app_v),
    ("/ping endpoint",              'def ping()' in app_v),
    ("score elif REMOVED",          '"\\u2605" in line' not in app_v),
    ("/100 standalone scan",        "BUG-SCORE" in app_v),
    ("/download_chunk route",       'def download_chunk' in app_v),
    ("_prune_jobs function",        'def _prune_jobs' in app_v),
    ("_prune_jobs called",          '_prune_jobs()  # S24 BUG8' in app_v),
    ("S24 comment marker",          "S24" in app_v),
]

all_pass = True
for label, cond in checks:
    ((_ok if cond else _err)(label))
    if not cond: all_pass = False

_rec("3.1", "app.py verification", all_pass)
_require(all_pass, "app.py verification failed -- check patches above")


# ======================================================================
#  STEP 4 -- Patch Dockerfile (--preload for faster cold start)
# ======================================================================
_h1("STEP 4 -- Patch Dockerfile: add --preload (faster cold start)")
DF = HF_CLONE / "Dockerfile"
df = _read(DF)

_h2("4.1  Add --preload to gunicorn CMD")
OLD_CMD = (
    'CMD ["gunicorn", "app:app", \\\n'
    '     "--bind", "0.0.0.0:7860", \\\n'
    '     "--timeout", "2400", \\\n'
    '     "--workers", "1", \\\n'
    '     "--keep-alive", "5"]'
)
NEW_CMD = (
    '# S24: --preload loads app before accepting connections (reduces cold-start)\n'
    'CMD ["gunicorn", "app:app", \\\n'
    '     "--bind", "0.0.0.0:7860", \\\n'
    '     "--timeout", "2400", \\\n'
    '     "--workers", "1", \\\n'
    '     "--preload", \\\n'
    '     "--keep-alive", "5"]'
)
df, ok41 = _replace_once(df, OLD_CMD, NEW_CMD, "add --preload to gunicorn CMD")
_write(DF, df)
_ok(f"Dockerfile written ({len(df):,} chars)")
_rec("4.1", "Dockerfile --preload added", ok41)

_h2("4.2  Verify Dockerfile")
df_v = _read(DF)
ok42 = "--preload" in df_v and "S24" in df_v
((_ok if ok42 else _err)("--preload present"))
_rec("4.2", "Dockerfile verified", ok42)


# ======================================================================
#  STEP 5 -- Patch README.md
# ======================================================================
_h1("STEP 5 -- Update README.md")
RM = HF_CLONE / "README.md"
rm = _read(RM)

_h2("5.1  Update engine list in README")
OLD_ENG_LINE = "Flask API serving engines v7.0, v7.5, v7.6"
NEW_ENG_LINE = (
    "Flask API serving engines v8.1 (Android-Hardened), "
    "v8.0 (Calibrated Precision), v7.0 (Stable Classic)"
)
rm, ok51 = _replace_once(rm, OLD_ENG_LINE, NEW_ENG_LINE, "engine list in README")
_write(RM, rm)
_ok(f"README.md written ({len(rm):,} chars)")
_rec("5.1", "README engine list updated", ok51)


# ======================================================================
#  STEP 6 -- Copy engine_v81.py into clone
# ======================================================================
_h1("STEP 6 -- Copy engine_v81.py into HF clone")

_h2("6.1  Copy engine_v81.py")
V81_DEST = HF_CLONE / "engine_v81.py"
shutil.copy2(V81_SRC, V81_DEST)
sz81 = V81_DEST.stat().st_size
ok61 = V81_DEST.exists() and sz81 > 50000
((_ok if ok61 else _err)(f"engine_v81.py copied ({sz81:,} bytes)"))
_rec("6.1", "engine_v81.py copied", ok61)
_require(ok61, "engine_v81.py copy failed or too small")


# ======================================================================
#  STEP 7 -- Git operations
# ======================================================================
_h1("STEP 7 -- Git operations")

_h2("7.1  Git identity")
ok71a, _ = _run('git config user.email "fix@s24"', label="git config email")
ok71b, _ = _run('git config user.name "S24-Fix"',  label="git config name")
_rec("7.1", "Git identity set", ok71a and ok71b)

_h2("7.2  Stage new/modified files")
ok72a, _ = _run('git add app.py',          label="git add app.py")
ok72b, _ = _run('git add Dockerfile',      label="git add Dockerfile")
ok72c, _ = _run('git add README.md',       label="git add README.md")
ok72d, _ = _run('git add engine_v81.py',   label="git add engine_v81.py")
_rec("7.2", "New/modified files staged", ok72a and ok72b and ok72c and ok72d)

_h2("7.3  Remove engine_v75.py + engine_v76.py")
ok73a, _ = _run('git rm engine_v75.py',    label="git rm engine_v75.py")
ok73b, _ = _run('git rm engine_v76.py',    label="git rm engine_v76.py")
_rec("7.3", "v7.5 + v7.6 removed from repo", ok73a and ok73b)
_require(ok73a and ok73b, "git rm failed -- engines may not exist")

_h2("7.4  Confirm staged diff")
ok74, diff_stat = _run('git diff --cached --stat', label="git diff --cached --stat")
_ok(diff_stat)
v81_staged = "engine_v81.py" in diff_stat
v75_gone   = "engine_v75.py" in diff_stat
v76_gone   = "engine_v76.py" in diff_stat
app_staged = "app.py"        in diff_stat
((_ok if v81_staged else _err)("engine_v81.py in staged diff"))
((_ok if v75_gone   else _err)("engine_v75.py in staged diff (deletion)"))
((_ok if v76_gone   else _err)("engine_v76.py in staged diff (deletion)"))
((_ok if app_staged else _err)("app.py in staged diff"))
_rec("7.4", "Staged diff correct", v81_staged and v75_gone and v76_gone and app_staged)

_h2("7.5  Commit")
msg = (
    "fix: S24 add v8.1 + rm v7.5/v7.6 + "
    "score-parse + /ping + /download_chunk + "
    "JOBS-prune + gunicorn-preload"
)
ok75, _ = _run(f'git commit -m "{msg}"', label="git commit")
_rec("7.5", "Committed", ok75)
_require(ok75, "git commit failed")

_h2("7.6  Push to HuggingFace")
ok76, push_out = _run('git push', label="git push HF", timeout=120)
_rec("7.6", "Pushed to HF", ok76)
_require(ok76, "git push failed")


# ======================================================================
#  STEP 8 -- Post-push verification
# ======================================================================
_h1("STEP 8 -- Post-push verification")

_h2("8.1  Git log -- confirm S24 commit is there")
ok81, log_out = _run('git log --oneline -5', label="git log")
for line in log_out.splitlines():
    _ok(f"  {line}")
_rec("8.1", "Git log checked", ok81)

_h2("8.2  Check live server (HF rebuilds ~2 min after push)")
_warn("HF rebuilds after push. Checking current state...")
healthy = _health("live health check")
if not healthy:
    _warn("Server may still be rebuilding. Wait 2 min then:")
    _warn(f"  curl -s {SERVER}/")
_rec("8.2", "Live health check", healthy)

_h2("8.3  Cleanup clone")
shutil.rmtree(HF_CLONE)
_ok(f"Removed {HF_CLONE}")
_rec("8.3", "Clone cleaned up", True)


# ======================================================================
#  FINAL SUMMARY
# ======================================================================
_h1("S24 SUMMARY")
print(f"\n  {'Step':<6}  {'Label':<54}  Result")
print(f"  {'----':<6}  {'------':<54}  ------")
for sid, label, result in _log:
    print(f"  {sid:<6}  {label:<54}  {result}")

fails = [x for x in _log if "FAIL" in x[2]]
print(f"""
  ================================================================
  S24 {'COMPLETE' if not fails else f'FAILED ({len(fails)} failures -- see above)'}

  Applied:
    + engine_v8.1 added (Android-Hardened, fixed SPECTRAL_BIAS + /tmp)
    - engine_v7.5 removed
    - engine_v7.6 removed
    FIX score parsing  -- standalone /100 scan catches all engine formats
    FIX /download_chunk -- BUG 7 resolved (route now implemented)
    FIX JOBS pruning   -- BUG 8 resolved (capped at 200, oldest removed)
    NEW /ping endpoint -- fast Flutter wake detection
    FIX --preload      -- gunicorn loads app before first request (less lag)
    FIX README         -- engine list accurate

  Flutter app changes needed:
    1. Add v8.1 engine card (replace v7.5 + v7.6)
    2. Change wake URL to /ping instead of full health check

  After HF rebuild (~2 min), verify:
    curl -s {SERVER}/
    Expected: engines has v8.1+v8.0+v7.0, status=ok

  Next known issue:
    BUG 2: reference audio still LFS stubs (132 bytes)
           Real fix = migrate to own server (Hetzner)
  ================================================================
""")

if fails:
    sys.exit(1)
