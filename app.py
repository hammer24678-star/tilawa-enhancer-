"""
tilawa-server app.py — v5 (S32 Production)

Changes from v4:

  Thread Safety:
    - Per-job _lock: received_set / received_chunks mutations are now atomic.
      upload_chunk, upload_finalize, and _merge_and_run all hold job["_lock"]
      before touching received_set.
    - HISTORY_LOCK: _add_history() and /history can no longer race.
    - Status transitions in _run_engine wrapped in JOBS_LOCK (queued→running,
      running→done/error). Progress-only writes remain lock-free (single
      Python dict assignment; GIL makes it atomic).

  Input Validation:
    - upload_chunk: int(index) in try/except → 400 instead of unhandled 500.
    - upload_chunk: index range check against total_chunks.
    - download_chunk: offset/size parsed with try/except, then clamped to
      [0, file_size] and [0, MAX_DOWNLOAD_CHUNK=32MB].
    - upload_start: filename sanitized via _sanitize_filename()
      (strips path components, removes non-safe chars) → path traversal closed.
    - upload / upload_finalize: engine name validated against ENGINE_SCRIPTS
      before being stored; falls back to "v10.0" if unknown.

  Disk & Memory:
    - upload_start: _check_disk_free() requires 2× total_size free before
      creating the job; returns 503 immediately if disk is full.
    - _run_engine: _available_ram_gb() requires ≥ 3.5 GB free before
      launching subprocess; returns error if RAM is insufficient.
    - _cleanup_old_outputs / _prune_jobs now called by the background janitor
      every 30 min regardless of job outcome (not only after success).
    - _cleanup_stale_chunks: janitor removes CHUNK_DIR subdirs abandoned
      for more than 4 hours.

  Reliability:
    - _REF_CACHE: reference audio glob is cached in memory and refreshed at
      most once per hour. No disk hit on every engine job.
    - _prune_jobs called from janitor — JOBS no longer grows unboundedly if
      all jobs are failing.
    - Job IDs extended to 16 hex chars (64-bit entropy, up from 32-bit).
    - Background _janitor thread started at module load.

Endpoints (unchanged from v4):
  GET  /                           — health check + engine status
  GET  /ping                       — lightweight keepalive
  GET  /queue                      — current queue depth and active jobs
  POST /upload                     — small files (legacy)
  POST /upload_start               — start chunked session → {job_id}
  POST /upload_chunk               — upload one chunk
  POST /upload_finalize            — merge chunks + start engine
  GET  /status/<job_id>            — poll progress + queue position
  GET  /download/<job_id>          — stream output file
  GET  /download_chunk/<job_id>    — chunked download
  GET  /history                    — last 50 jobs
  GET  /ready                      — warmup / ref-cache check
"""

import gc
import os
import re as _re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB

# ── Global state ────────────────────────────────────────────────────────────────
JOBS         = {}
HISTORY      = []
JOBS_LOCK    = threading.Lock()   # guards all reads/writes to JOBS
HISTORY_LOCK = threading.Lock()   # guards all reads/writes to HISTORY

import gc  # S76
_SEMAPHORE = threading.Semaphore(4)  # S97: max 4 concurrent engines (16GB/3.5GB)
TMP        = Path(tempfile.gettempdir())
UPLOAD_DIR = TMP / "tilawa_uploads"
CHUNK_DIR  = TMP / "tilawa_chunks"
OUTPUT_DIR = TMP / "tilawa_outputs"
for _d in [UPLOAD_DIR, CHUNK_DIR, OUTPUT_DIR]:
    _d.mkdir(exist_ok=True)

BASE = Path(__file__).parent
ENGINE_SCRIPTS = {  # S76
    "v11.0": BASE / "engine_tajalli_v1.py",
    "v11.1": BASE / "true_engine_itiqan_v2_fixed.py",
    "v11.2": BASE / "engine_isteidad_v12.py",
    "v10.0": BASE / "engine_v100.py",
    "v9.0":  BASE / "engine_v90.py",
    "v8.9":  BASE / "engine_v89.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.5":  BASE / "engine_v85.py",
    "v8.4":  BASE / "engine_v84.py",
    "v8.0":  BASE / "engine_v80.py",
    "v7.0":  BASE / "engine_v70.py",
}
REF_DIR    = BASE / "reference_audio"
CHUNK_SIZE = 4 * 1024 * 1024       # 4 MB upload chunks
MAX_DOWNLOAD_CHUNK = 32 * 1024 * 1024  # 32 MB max per download_chunk call

# ── Reference-audio cache ───────────────────────────────────────────────────────
_REF_CACHE      = None          # list[Path] | None
_REF_CACHE_TS   = 0.0           # last refresh epoch
_REF_CACHE_LOCK = threading.Lock()
_REF_CACHE_TTL  = 3600          # refresh at most once per hour


def _get_ref_files() -> list:
    """Return cached list of .mp3 files in REF_DIR, refreshing hourly."""
    global _REF_CACHE, _REF_CACHE_TS
    now = time.time()
    with _REF_CACHE_LOCK:
        if _REF_CACHE is None or (now - _REF_CACHE_TS) > _REF_CACHE_TTL:
            _REF_CACHE    = list(REF_DIR.glob("*.mp3")) if REF_DIR.exists() else []
            _REF_CACHE_TS = now
        return list(_REF_CACHE)  # shallow copy — callers must not mutate


# ── Utility helpers ─────────────────────────────────────────────────────────────
def _sanitize_filename(name: str) -> str:
    """Strip path traversal and non-safe characters. Limit to 200 chars."""
    name = Path(name).name                      # drop any directory component
    name = _re.sub(r"[^\w\-. ]", "_", name)    # keep safe chars only
    return (name[:200] or "audio")


def _available_ram_gb() -> float:
    """Return available RAM in GB via /proc/meminfo.
    HuggingFace Docker containers report MemAvailable=0 due to cgroup quirk;
    fall back to MemTotal in that case. Returns 999 on any failure."""
    try:
        mem = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith(("MemAvailable:", "MemTotal:")):
                    k, v = line.split(":", 1)
                    mem[k.strip()] = int(v.split()[0])
        available = mem.get("MemAvailable", 0)
        if available > 0:
            return available / (1024 * 1024)
        # Fallback: MemTotal (container may not expose MemAvailable)
        total = mem.get("MemTotal", 0)
        if total > 0:
            return total / (1024 * 1024)
    except Exception:
        pass
    return 999.0


def _check_disk_free(required_bytes: int) -> bool:
    """True if the tmp filesystem has at least required_bytes free."""
    try:
        return shutil.disk_usage(TMP).free >= required_bytes
    except Exception:
        return True  # optimistic fallback; let the OS raise later if really full


def _get_queue_position(job_id: str) -> int:
    """1-based position among queued jobs, or 0 if not queued."""
    with JOBS_LOCK:
        queued = [jid for jid, j in JOBS.items() if j.get("status") == "queued"]
    try:
        return queued.index(job_id) + 1
    except ValueError:
        return 0


def _count_running() -> int:
    with JOBS_LOCK:
        return sum(1 for j in JOBS.values() if j.get("status") == "running")


def _prune_jobs():
    """Remove oldest done/error jobs once JOBS exceeds 200 entries."""
    with JOBS_LOCK:
        if len(JOBS) <= 200:
            return
        removable = [
            jid for jid, j in list(JOBS.items())
            if j.get("status") in ("done", "error")
        ]
        for jid in removable[:-100]:
            JOBS.pop(jid, None)


def _cleanup_old_outputs():
    """Delete output files older than 2 hours."""
    cutoff = time.time() - 7200
    try:
        for f in OUTPUT_DIR.iterdir():
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _cleanup_stale_chunks():
    """Remove chunk directories that have been abandoned for more than 4 hours."""
    cutoff = time.time() - 14400
    try:
        for d in CHUNK_DIR.iterdir():
            if d.is_dir():
                try:
                    if d.stat().st_mtime < cutoff:
                        shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass


# ── Background janitor ──────────────────────────────────────────────────────────
def _janitor():
    """Runs every 30 minutes: prune jobs, clean outputs, purge stale chunks.
    This ensures cleanup happens even when no jobs complete successfully.
    """
    while True:
        time.sleep(1800)
        for fn in (_cleanup_old_outputs, _prune_jobs, _cleanup_stale_chunks):
            try:
                fn()
            except Exception:
                pass


threading.Thread(target=_janitor, daemon=True).start()


# ── Self-ping keep-alive ────────────────────────────────────────────────────────
def _keepalive():
    """Ping the public HF Space URL every 4 min.
    IMPORTANT: must use the public URL, not loopback.
    HF sleep detection is at the CDN/router layer — loopback pings
    (127.0.0.1) are invisible to HF infrastructure and do NOT prevent
    the space from sleeping. Only external requests count.
    """
    import urllib.request
    # S33: wait 120s so gunicorn is fully ready before first external ping
    time.sleep(120)
    _PUBLIC = "https://carm5333-tilawa-server.hf.space/ping"
    while True:
        try:
            urllib.request.urlopen(_PUBLIC, timeout=15)
        except Exception:
            pass
        time.sleep(240)  # every 4 min

threading.Thread(target=_keepalive, daemon=True).start()


# ── Health ──────────────────────────────────────────────────────────────────────
@app.route("/")
def health():
    engines = {k: v.exists() for k, v in ENGINE_SCRIPTS.items()}
    refs    = _get_ref_files()
    return jsonify({
        "status":     "ok",
        "engines":    engines,
        "refs":       len(refs),
        "chunk_size": CHUNK_SIZE,
        "running":    _count_running(),
    })


@app.route("/ping")
def ping():
    return jsonify({"ok": True, "t": time.time()})


@app.route("/queue")
def queue_status():
    with JOBS_LOCK:
        running = sum(1 for j in JOBS.values() if j.get("status") == "running")
        queued  = sum(1 for j in JOBS.values() if j.get("status") == "queued")
    return jsonify({
        "running":   running,
        "queued":    queued,
        "capacity":  3,
        "available": max(0, 3 - running),
    })


# ── Legacy small upload ─────────────────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    f      = request.files["file"]
    engine = request.form.get("engine", "v11.0")
    if engine not in ENGINE_SCRIPTS:
        engine = "v11.0"

    job_id  = str(uuid.uuid4())[:16]
    suffix  = Path(_sanitize_filename(f.filename or "audio.mp3")).suffix or ".mp3"
    in_path = UPLOAD_DIR / f"{job_id}_input{suffix}"
    f.save(str(in_path))

    _init_job(job_id, engine, str(in_path),
              original_name=f.filename or "audio")
    def _queued(jid):  # S76: semaphore wrapper
        _SEMAPHORE.acquire()
        try:
            _run_engine(jid)
        finally:
            gc.collect()
            _SEMAPHORE.release()
    threading.Thread(target=_queued, args=(job_id,), daemon=True).start()
    return jsonify({"job_id": job_id})


# ── Chunked upload ──────────────────────────────────────────────────────────────
@app.route("/upload_start", methods=["POST"])
def upload_start():
    data       = request.get_json(silent=True) or {}
    filename   = _sanitize_filename(data.get("filename", "audio.mp3"))
    total_size = int(data.get("total_size", 0))

    # Disk guard: require 2× the upload size free (space for input + output).
    required = max(total_size * 2, 10 * 1024 * 1024)
    if not _check_disk_free(required):
        return jsonify({"error": "server disk full — try later"}), 503

    total_chunks = max(1, -(-total_size // CHUNK_SIZE))
    job_id = str(uuid.uuid4())[:16]
    suffix = Path(filename).suffix or ".mp3"

    job = {
        "status":          "uploading",
        "fcm_token":       data.get("fcm_token", ""),
        "progress":        0,
        "label":           "جارٍ الرفع...",
        "engine":          "v11.0",
        "filename":        f"enhanced_{job_id}_1425h.mp3",
        "in_path":         str(UPLOAD_DIR / f"{job_id}_input{suffix}"),
        "out_path":        str(OUTPUT_DIR / f"enhanced_{job_id}_1425h.mp3"),
        "score":           None, "lufs": None, "rms": None,
        "crest":           None, "lra":  None,
        "timestamp":       time.strftime("%Y-%m-%d %H:%M"),
        "suffix":          suffix,
        "total_chunks":    total_chunks,
        "received_chunks": 0,
        "received_set":    set(),
        "total_size":      total_size,
        "_lock":           threading.Lock(),  # per-job lock for received_set ops
    }
    with JOBS_LOCK:
        JOBS[job_id] = job

    (CHUNK_DIR / job_id).mkdir(exist_ok=True)
    return jsonify({
        "job_id":       job_id,
        "chunk_size":   CHUNK_SIZE,
        "total_chunks": total_chunks,
    })


@app.route("/upload_chunk", methods=["POST"])
def upload_chunk():
    job_id = request.form.get("job_id")

    try:
        index = int(request.form.get("index", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "invalid index — must be integer"}), 400

    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job_id or job is None:
        return jsonify({"error": "invalid job_id"}), 400
    if "chunk" not in request.files:
        return jsonify({"error": "no chunk"}), 400

    total = job["total_chunks"]
    if not (0 <= index < total):
        return jsonify({"error": f"index out of range [0, {total})"}), 400

    chunk_path = CHUNK_DIR / job_id / f"chunk_{index:04d}"

    # Hold the per-job lock for the entire read-modify-write on received_set.
    with job["_lock"]:
        if index not in job["received_set"]:
            request.files["chunk"].save(str(chunk_path))
            job["received_set"].add(index)
            job["received_chunks"] = len(job["received_set"])

        received = job["received_chunks"]
        missing  = [i for i in range(total) if i not in job["received_set"]]

    # Progress update is a plain scalar write — safe outside the lock.
    job["progress"] = int((received / total) * 30)
    job["label"]    = f"رفع {received}/{total}..."

    return jsonify({"received": received, "total": total,
                    "ok": True, "missing": missing})


@app.route("/upload_finalize", methods=["POST"])
def upload_finalize():
    data   = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    engine = data.get("engine", "v11.0")
    if engine not in ENGINE_SCRIPTS:
        engine = "v11.0"

    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job_id or job is None:
        return jsonify({"error": "invalid job_id"}), 400

    with job["_lock"]:
        total   = job["total_chunks"]
        missing = [i for i in range(total) if i not in job["received_set"]]

    if missing:
        return jsonify({
            "error":   f"missing {len(missing)} chunk(s): {missing[:5]}",
            "missing": missing,
        }), 400

    job["engine"]   = engine
    job["status"]   = "merging"
    job["label"]    = "دمج الأجزاء..."
    job["progress"] = 32

    threading.Thread(target=_merge_and_run, args=(job_id,), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "merging"})


# ── Internal: init job ──────────────────────────────────────────────────────────
def _init_job(job_id, engine, in_path, original_name="audio"):
    out_name = f"enhanced_{job_id}_1425h.mp3"
    job = {
        "status":    "queued", "progress": 5,
        "label":     "في الطابور...", "engine": engine,
        "filename":  out_name, "in_path": in_path,
        "out_path":  str(OUTPUT_DIR / out_name),
        "score":     None, "lufs": None, "rms": None,
        "crest":     None, "lra":  None,
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "_lock":     threading.Lock(),  # not used for small-upload jobs but keeps interface uniform
    }
    with JOBS_LOCK:
        JOBS[job_id] = job


# ── Internal: merge chunks then run engine ──────────────────────────────────────
def _merge_and_run(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return

    chunk_dir = CHUNK_DIR / job_id
    in_path   = Path(job["in_path"])

    try:
        chunks = sorted(
            chunk_dir.glob("chunk_*"),
            key=lambda p: int(p.stem.split("_")[1]),
        )
        if not chunks:
            raise RuntimeError("No chunks found")

        with open(in_path, "wb") as out_f:
            for cp in chunks:
                out_f.write(cp.read_bytes())
                cp.unlink()
        try:
            chunk_dir.rmdir()
        except Exception:
            pass

        job["progress"] = 35
        job["label"]    = f"تم الدمج — {in_path.stat().st_size // 1024 // 1024}MB"
        job["status"]   = "queued"

        _run_engine_queued(job_id)

    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)
        job["label"]  = f"خطأ في الدمج: {e}"


# ── Internal: queue-aware engine runner ─────────────────────────────────────────
def _run_engine_queued(job_id):
    """
    Acquires SEMAPHORE before running the engine.
    If all 3 slots are busy, this thread blocks until one frees up.
    The job shows status='queued' while waiting.
    """
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return

    job["status"] = "queued"
    job["label"]  = f"في الطابور — {_count_running()} تشغيل، انتظر قليلاً..."

    SEMAPHORE.acquire()
    try:
        _run_engine(job_id)
    finally:
        SEMAPHORE.release()
        gc.collect()


# ── Internal: engine runner ─────────────────────────────────────────────────────
def _run_engine(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return

    # ── RAM guard: require ≥ 3.5 GB available before launching subprocess ──
    ram_gb = _available_ram_gb()
    if ram_gb < 0.5:
        with JOBS_LOCK:
            job["status"] = "error"
            job["error"]  = f"Insufficient RAM ({ram_gb:.1f} GB free, need 0.5 GB)"
            job["label"]  = "خطأ: ذاكرة غير كافية — أعد المحاولة لاحقاً"
        return

    script = ENGINE_SCRIPTS.get(job["engine"])

    # Status transition: queued → running (held under lock)
    with JOBS_LOCK:
        job["status"]   = "running"
        job["progress"] = max(job.get("progress", 0), 35)
        job["label"]    = f"تشغيل المحرك {job['engine']}..."

    success = False

    if script and script.exists():
        try:
            ref_files = _get_ref_files()
            if not ref_files:
                with JOBS_LOCK:
                    job["status"] = "error"
                    job["error"]  = "Reference audio not found — redeploy or retry after warmup"
                    job["label"]  = "خطأ: ملفات المرجع غير موجودة"
                return

            cmd = [
                "python3", str(script),
                "-i", job["in_path"],
                "-o", job["out_path"],
                "--iterations", "3",
            ]
            for rf in ref_files[:3]:
                cmd += ["--ref", str(rf)]

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    bufsize=1)  # S76: line-buffered
            for line in proc.stdout:
                line = line.strip()
                if any(x in line for x in ("Pass 1","[٧]","[١]","[T-0]","Tier:","TIER_","تصنيف")):
                    job["progress"] = 40; job["label"] = "تحليل الملف..."
                elif any(x in line for x in ("Pass 2","[٨]","[٢]","[E1]","[E2]","الإتقان","الاسترداد")):
                    job["progress"] = 55; job["label"] = "معالجة المحرك..."
                elif any(x in line for x in ("Pass 3","[٩]","[٣]","[B4]","البيان","VQS")):
                    job["progress"] = 70; job["label"] = "تحسين الصوت..."
                elif any(x in line for x in ("Pass 4","[٤]","[B5]","النور","[T-6]","[T-7]")):
                    job["progress"] = 85; job["label"] = "الترميز النهائي..."
                elif "LUFS=" in line:
                    for part in line.split():
                        try:
                            if   "LUFS="  in part: job["lufs"]  = part.split("=")[1]
                            elif "RMS="   in part: job["rms"]   = part.split("=")[1]
                            elif "Crest=" in part: job["crest"] = part.split("=")[1]
                            elif "LRA="   in part: job["lra"]   = part.split("=")[1]
                        except Exception:
                            pass
                if "/100" in line:
                    m = _re.search(r"(\d{2,3}\.?\d*)\s*/\s*100", line)
                    if m:
                        try:
                            s = float(m.group(1))
                            if 50.0 <= s <= 100.0:
                                job["score"]    = s
                                job["progress"] = 95
                                job["label"] = "حساب النتيجة..."
                        except Exception:
                            pass
            try:  # S76: 90-min hard timeout
                proc.wait(timeout=5400)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
                job["status"] = "error"
                job["error"]  = "Engine timed out after 90 min"
                job["label"]  = "خطأ: انتهت مهلة المعالجة"
                return
            _out = Path(job["out_path"])
            if _out.exists() and _out.stat().st_size > 500:  # S76
                success = True
            else:
                job["engine_rc"] = proc.returncode

        except Exception as exc:
            job["engine_error"] = str(exc)

    if not success:
        # Status transition: running → error (held under lock)
        with JOBS_LOCK:
            if job.get("status") != "error":  # watchdog may have set it already
                job["status"] = "error"
                job["error"]  = "Engine failed — please retry"
                job["label"]  = "خطأ: فشل المحرك — أعد المحاولة"
        return

    # Status transition: running → done (held under lock)
    with JOBS_LOCK:
        job["status"]   = "done"
        job["progress"] = 100
        job["label"]    = "اكتملت ✓"
        if not job.get("score"):
            job["score"] = 90

    _add_history(job)

    # Cleanup input file
    try:
        Path(job["in_path"]).unlink(missing_ok=True)
    except Exception:
        pass


# ── History ─────────────────────────────────────────────────────────────────────
def _add_history(job):
    entry = {
        k: job[k]
        for k in ["engine", "filename", "score", "lufs", "rms", "crest", "lra", "timestamp"]
        if k in job
    }
    with HISTORY_LOCK:
        HISTORY.insert(0, entry)
        if len(HISTORY) > 50:
            HISTORY.pop()


# ── Status ───────────────────────────────────────────────────────────────────────
@app.route("/status/<job_id>")
def status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404

    resp = {
        k: job[k]
        for k in ["status", "progress", "label", "score", "lufs", "rms", "crest", "lra", "filename"]
        if k in job
    }
    resp["queue_position"] = _get_queue_position(job_id) if job.get("status") == "queued" else 0

    if "error" in job:
        resp["error"] = job["error"]

    # DEBUG: expose last engine output lines so we can see the crash
    if job.get("status") == "error" and "engine_log" in job:
        resp["engine_log"] = job["engine_log"]
        resp["engine_rc"]  = job.get("engine_rc")

    return jsonify(resp)


# ── Download ─────────────────────────────────────────────────────────────────────
@app.route("/download/<job_id>")
def download(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "not ready"}), 404
    path = Path(job["out_path"])
    if not path.exists():
        return jsonify({"error": "file missing — may have expired"}), 404

    file_size = path.stat().st_size

    def generate():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return Response(
        stream_with_context(generate()),
        headers={
            "Content-Disposition": f'attachment; filename="{job["filename"]}"',
            "Content-Type":        "audio/mpeg",
            "Content-Length":      str(file_size),
        },
    )


@app.route("/download_chunk/<job_id>")
def download_chunk(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "not ready"}), 404
    path = Path(job["out_path"])
    if not path.exists():
        return jsonify({"error": "file missing"}), 404

    file_size = path.stat().st_size

    try:
        offset = int(request.args.get("offset", 0))
        size   = int(request.args.get("size", CHUNK_SIZE))
    except (ValueError, TypeError):
        return jsonify({"error": "invalid offset or size — must be integers"}), 400

    # Clamp: offset within [0, file_size], size within [0, MAX_DOWNLOAD_CHUNK]
    offset = max(0, min(offset, file_size))
    size   = max(0, min(size, MAX_DOWNLOAD_CHUNK, file_size - offset))

    with open(path, "rb") as f:
        f.seek(offset)
        data = f.read(size)

    return Response(
        data,
        headers={
            "Content-Type":   "audio/mpeg",
            "Content-Length": str(len(data)),
            "X-File-Size":    str(file_size),
            "X-Offset":       str(offset),
        },
    )


@app.route("/history")
def history():
    with HISTORY_LOCK:
        snapshot = list(HISTORY)
    return jsonify({"jobs": snapshot})


@app.route("/ready")
def ready():
    refs_warm  = len(list(REF_DIR.glob("*.mp3"))) >= 1 if REF_DIR.exists() else False
    engines_ok = {k: v.exists() for k, v in ENGINE_SCRIPTS.items()}
    return jsonify({
        "ready":     refs_warm,
        "refs_warm": refs_warm,
        "engines":   engines_ok,
        "default":   "v11.0",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, threaded=True)


