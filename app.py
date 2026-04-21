"""
tilawa-server app.py — v3 (S24 overhaul)
Engines: v8.1 (Android-Hardened), v8.0 (Calibrated Precision), v7.0 (Stable Classic)

Endpoints:
  GET  /                           — health check + engine status
  GET  /ping                       — lightweight keepalive (S24)
  POST /upload                     — small files <10MB (legacy)
  POST /upload_start               — start chunked session → {job_id}
  POST /upload_chunk               — upload one chunk {job_id, index, total}
  POST /upload_finalize            — merge chunks + start engine {job_id, engine}
  GET  /status/<job_id>            — poll progress
  GET  /download/<job_id>          — stream output file
  GET  /download_chunk/<job_id>    — chunked download {offset, size}
  GET  /history                    — last 50 jobs
"""
import os, uuid, threading, time, subprocess, tempfile, math
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Increase max content length to 12MB per chunk (with 2MB headroom)
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024  # S25: 4MB chunk + 2MB headroom

JOBS = {}
HISTORY = []
TMP = Path(tempfile.gettempdir())
UPLOAD_DIR = TMP / "tilawa_uploads"
CHUNK_DIR  = TMP / "tilawa_chunks"
OUTPUT_DIR = TMP / "tilawa_outputs"
for d in [UPLOAD_DIR, CHUNK_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)

BASE = Path(__file__).parent
# S25: v8.4 added (Source Tier Intelligence); v8.1 replaced
ENGINE_SCRIPTS = {
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.5":  BASE / "engine_v85.py",
    "v8.4": BASE / "engine_v84.py",
    "v8.0": BASE / "engine_v80.py",
    "v7.0": BASE / "engine_v70.py",
}
REF_DIR = BASE / "reference_audio"

CHUNK_SIZE = 4 * 1024 * 1024  # S25: 4MB — aligns with client, better mobile retry granularity

# ── Health ────────────────────────────────────────────────────────────────────
@app.route("/")
def health():
    engines = {k: v.exists() for k, v in ENGINE_SCRIPTS.items()}
    refs = list(REF_DIR.glob("*.mp3")) if REF_DIR.exists() else []
    return jsonify({"status": "ok", "engines": engines,
                    "refs": len(refs), "chunk_size": CHUNK_SIZE})

# ── Legacy small upload (<10MB) ────────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    engine = request.form.get("engine", "v8.4")
    job_id = str(uuid.uuid4())[:8]
    suffix = Path(f.filename).suffix or ".mp3"
    in_path = UPLOAD_DIR / f"{job_id}_input{suffix}"
    f.save(str(in_path))
    _init_job(job_id, engine, str(in_path),
              original_name=f.filename or "audio")
    threading.Thread(target=_run_engine, args=(job_id,), daemon=True).start()
    return jsonify({"job_id": job_id})

# ── Chunked upload ─────────────────────────────────────────────────────────────
@app.route("/upload_start", methods=["POST"])
def upload_start():
    """Client calls this first to get a job_id for chunked upload."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "audio.mp3")
    total_size = data.get("total_size", 0)
    # S25-SERVER2: server owns chunk_size — client derives total_chunks from it
    total_chunks = max(1, -(-total_size // CHUNK_SIZE))  # ceiling div

    job_id = str(uuid.uuid4())[:8]
    suffix = Path(filename).suffix or ".mp3"

    JOBS[job_id] = {
        "status": "uploading",
        "progress": 0,
        "label": "جارٍ الرفع...",
        "engine": "v8.7",
        "filename": f"enhanced_{job_id}_1425h.mp3",
        "in_path": str(UPLOAD_DIR / f"{job_id}_input{suffix}"),
        "out_path": str(OUTPUT_DIR / f"enhanced_{job_id}_1425h.mp3"),
        "score": None, "lufs": None, "rms": None,
        "crest": None, "lra": None,
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "suffix": suffix,
        "total_chunks": total_chunks,
        "received_chunks": 0,       # count of unique chunks received
        "received_set": set(),       # S25: track which indices arrived (dedup)
        "total_size": total_size,
    }
    # Create chunk directory for this job
    (CHUNK_DIR / job_id).mkdir(exist_ok=True)
    return jsonify({"job_id": job_id, "chunk_size": CHUNK_SIZE,
                    "total_chunks": total_chunks})

@app.route("/upload_chunk", methods=["POST"])
def upload_chunk():
    """Upload one chunk. Form fields: job_id, index. Body: binary chunk."""
    job_id = request.form.get("job_id")
    index  = int(request.form.get("index", 0))

    if not job_id or job_id not in JOBS:
        return jsonify({"error": "invalid job_id"}), 400
    if "chunk" not in request.files:
        return jsonify({"error": "no chunk"}), 400

    chunk_file = request.files["chunk"]
    chunk_path = CHUNK_DIR / job_id / f"chunk_{index:04d}"

    job = JOBS[job_id]

    # S25-SERVER3: idempotent — skip if this index already arrived (retry safety)
    if index not in job["received_set"]:
        chunk_file.save(str(chunk_path))
        job["received_set"].add(index)
        job["received_chunks"] = len(job["received_set"])
    # else: duplicate chunk — silently ignore, don't double-count

    total    = job["total_chunks"]
    received = job["received_chunks"]
    missing  = [i for i in range(total) if i not in job["received_set"]]

    # Update upload progress (0–30%)
    job["progress"] = int((received / total) * 30)
    job["label"]    = f"رفع {received}/{total}..."

    return jsonify({"received": received, "total": total,
                    "ok": True, "missing": missing})

@app.route("/upload_finalize", methods=["POST"])
def upload_finalize():
    """All chunks uploaded. Merge them and start processing."""
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    engine = data.get("engine", "v8.7")

    if not job_id or job_id not in JOBS:
        return jsonify({"error": "invalid job_id"}), 400

    job = JOBS[job_id]
    total    = job["total_chunks"]
    received = job["received_chunks"]

    # S25-SERVER4: refuse to merge if any chunk is missing
    missing = [i for i in range(total) if i not in job["received_set"]]
    if missing:
        return jsonify({
            "error": f"missing {len(missing)} chunk(s): {missing[:5]}{'...' if len(missing)>5 else ''}",
            "missing": missing,
        }), 400

    job["engine"] = engine
    job["status"] = "merging"
    job["label"]  = "دمج الأجزاء..."
    job["progress"] = 32

    threading.Thread(target=_merge_and_run,
                     args=(job_id,), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "merging"})

def _merge_and_run(job_id):
    """Merge chunks then run engine."""
    job = JOBS[job_id]
    chunk_dir = CHUNK_DIR / job_id
    in_path = Path(job["in_path"])

    try:
        # Collect and sort chunks
        chunks = sorted(chunk_dir.glob("chunk_*"),
                        key=lambda p: int(p.stem.split("_")[1]))
        if not chunks:
            raise RuntimeError("No chunks found")

        # Merge
        with open(in_path, "wb") as out_f:
            for chunk_path in chunks:
                out_f.write(chunk_path.read_bytes())
                chunk_path.unlink()  # free space immediately

        # Clean up chunk dir
        try: chunk_dir.rmdir()
        except: pass

        job["progress"] = 35
        job["label"] = f"تم الدمج — {in_path.stat().st_size // 1024 // 1024}MB"

        # Now run engine
        _run_engine(job_id)

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["label"] = f"خطأ في الدمج: {e}"

def _init_job(job_id, engine, in_path, original_name="audio"):
    out_name = f"enhanced_{job_id}_1425h.mp3"
    JOBS[job_id] = {
        "status": "queued", "progress": 5,
        "label": "في الطابور...", "engine": engine,
        "filename": out_name, "in_path": in_path,
        "out_path": str(OUTPUT_DIR / out_name),
        "score": None, "lufs": None, "rms": None,
        "crest": None, "lra": None,
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
    }

def _run_engine(job_id):
    job = JOBS[job_id]
    script = ENGINE_SCRIPTS.get(job["engine"])
    job["status"] = "running"
    if job["progress"] < 35:
        job["progress"] = 35
    job["label"] = f"تشغيل المحرك {job['engine']}..."

    success = False
    if script and script.exists():
        try:
            ref_files = list(REF_DIR.glob("*.mp3")) if REF_DIR.exists() else []
            cmd = ["python3", str(script),
                   "-i", job["in_path"],
                   "-o", job["out_path"],
                   "--iterations", "3"]  # S23 BUG4: was 1, disabling convergence loop
            for rf in ref_files[:3]:
                cmd += ["--ref", str(rf)]

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                line = line.strip()
                # S23 BUG3: match all engine output styles
                # v70 prints "Pass 1 ..." and "Score: N" (English, S22 patch)
                # v75/v76/v80 print Arabic bracket markers and star score
                if "Pass 1" in line or "[\u0667]" in line or "[\u0661]" in line:
                    job["progress"] = 45; job["label"] = "Pass 1 — تحليل الطيف..."
                elif "Pass 2" in line or "[\u0668]" in line or "[\u0662]" in line:
                    job["progress"] = 60; job["label"] = "Pass 2 — ضبط LUFS..."
                elif "Pass 3" in line or "[\u0669]" in line or "[\u0663]" in line:
                    job["progress"] = 75; job["label"] = "Pass 3 — تصحيح..."
                elif "Pass 4" in line or "[\u0664]" in line:
                    job["progress"] = 88; job["label"] = "Pass 4 — تشفير MP3..."
                elif "LUFS=" in line:
                    for part in line.split():
                        try:
                            if "LUFS=" in part:   job["lufs"]  = part.split("=")[1]
                            elif "RMS=" in part:  job["rms"]   = part.split("=")[1]
                            elif "Crest=" in part: job["crest"] = part.split("=")[1]
                            elif "LRA=" in part:  job["lra"]   = part.split("=")[1]
                        except: pass
                # S24 BUG-SCORE: standalone /100 scan -- runs on every line
                # independent of elif chain; catches v80/v81 score in any format
                if "/100" in line:
                    import re as _re
                    _m = _re.search(r"(\d{2,3}\.?\d*)\s*/\s*100", line)
                    if _m:
                        try:
                            _s = float(_m.group(1))
                            if 50.0 <= _s <= 100.0:
                                job["score"] = _s
                                job["progress"] = 95
                                job["label"] = "حساب النتيجة..."
                        except: pass
            proc.wait()
            if proc.returncode == 0 and Path(job["out_path"]).exists():
                success = True
        except Exception:
            pass

    if not success:
        # Fallback: ffmpeg loudnorm
        try:
            job["label"] = "معالجة أساسية (fallback)..."
            job["progress"] = 50
            subprocess.run(
                ["ffmpeg", "-y", "-i", job["in_path"],
                 "-af", "loudnorm=I=-6:TP=-1:LRA=4",
                 "-ar", "48000", "-b:a", "320k", job["out_path"]],
                check=True, capture_output=True)
            success = True
            job["score"] = 75
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
            job["label"] = f"خطأ: {e}"
            return

    if success:
        job["status"] = "done"
        job["progress"] = 100
        job["label"] = "اكتملت ✓"
        if not job.get("score"):
            job["score"] = 90
        _add_history(job)
        _prune_jobs()  # S24 BUG8

    # Cleanup input
    try: Path(job["in_path"]).unlink(missing_ok=True)
    except: pass

def _add_history(job):
    entry = {k: job[k] for k in
             ["engine","filename","score","lufs","rms","crest","lra","timestamp"]}
    HISTORY.insert(0, entry)
    if len(HISTORY) > 50: HISTORY.pop()

# S24 BUG8: prune JOBS dict to prevent unbounded memory growth
def _prune_jobs():
    """Remove oldest done/error jobs once JOBS exceeds 200 entries."""
    if len(JOBS) <= 200:
        return
    removable = [jid for jid, j in list(JOBS.items())
                 if j.get("status") in ("done", "error")]
    for jid in removable[:-100]:
        JOBS.pop(jid, None)

# ── Status ─────────────────────────────────────────────────────────────────────
@app.route("/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job: return jsonify({"error": "not found"}), 404
    return jsonify({k: job[k] for k in
        ["status","progress","label","score","lufs","rms","crest","lra","filename"]
        if k in job})

# ── Download — streaming for large files ────────────────────────────────────────
@app.route("/download/<job_id>")
def download(job_id):
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "not ready"}), 404
    path = Path(job["out_path"])
    if not path.exists():
        return jsonify({"error": "file missing"}), 404

    file_size = path.stat().st_size

    def generate():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)  # 1MB at a time
                if not chunk:
                    break
                yield chunk

    return Response(
        stream_with_context(generate()),
        headers={
            "Content-Disposition": f'attachment; filename="{job["filename"]}"',
            "Content-Type": "audio/mpeg",
            "Content-Length": str(file_size),
        }
    )

# ── History ─────────────────────────────────────────────────────────────────────
# S24 BUG7: /download_chunk was in docstring since v2 but never implemented
@app.route("/download_chunk/<job_id>")
def download_chunk(job_id):
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "not ready"}), 404
    path = Path(job["out_path"])
    if not path.exists():
        return jsonify({"error": "file missing"}), 404
    offset    = int(request.args.get("offset", 0))
    size      = int(request.args.get("size", CHUNK_SIZE))
    file_size = path.stat().st_size
    with open(path, "rb") as f:
        f.seek(offset)
        data = f.read(size)
    return Response(data, headers={
        "Content-Type":   "audio/mpeg",
        "Content-Length": str(len(data)),
        "X-File-Size":    str(file_size),
        "X-Offset":       str(offset),
    })

# S24: fast endpoint for Flutter wake detection
@app.route("/ping")
def ping():
    return jsonify({"ok": True, "t": time.time()})

@app.route("/history")
def history():
    return jsonify({"jobs": HISTORY})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, threaded=True)
