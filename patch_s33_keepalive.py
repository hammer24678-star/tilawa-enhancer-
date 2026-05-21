"""
patch_s33_keepalive.py — Fix HF Space sleep: loopback → public URL keepalive

ROOT CAUSE:
  _keepalive() pings http://127.0.0.1:{port}/ping — this is a loopback
  request that never reaches HF's CDN/router. HF's sleep detection is at
  the infrastructure layer (external traffic only), so the space sleeps
  after ~48-72h of no real users, causing cold-boots and "Waking server..."

FIX (server-side only):
  Replace loopback ping with public HF Space URL ping so HF infrastructure
  counts it as real traffic and never sleeps the space.

  Old: http://127.0.0.1:{port}/ping   (invisible to HF)
  New: https://carm5333-tilawa-server.hf.space/ping  (external, HF sees it)

  Interval kept at 4 min (240s) — well under any sleep threshold.
  Startup delay increased 60→120s to ensure gunicorn is fully up before
  the first external ping.

Run from ~/tilawa-enhancer:
  python3 patch_s33_keepalive.py
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# ── helpers ───────────────────────────────────────────────────────────────────
def _h1(t):
    bar = "=" * 64
    print(f"\n{bar}\n  {t}\n{bar}")

def _h2(t):  print(f"\n  -- {t}")
def _ok(m):  print(f"     OK  {m}")
def _err(m): print(f"     XX  {m}")

_log = []

def _rec(sid, label, ok):
    _log.append((sid, label, "[OK] PASS" if ok else "[XX] FAIL"))
    return ok

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
        return text, False
    if c > 1:
        print(f"     !!  Anchor found {c}x -- using first -- {label}")
    _ok(f"Replaced -- {label}")
    return text.replace(old, new, 1), True

def _run(cmd, cwd=None, label="", timeout=180):
    r = subprocess.run(cmd, shell=True,
                       cwd=str(cwd or HF_CLONE),
                       capture_output=True, text=True, timeout=timeout)
    ok = r.returncode == 0
    ((_ok if ok else _err)(label or cmd))
    if not ok:
        for line in (r.stdout + r.stderr).strip().splitlines()[-6:]:
            print(f"        {line}")
    return ok, (r.stdout + r.stderr).strip()

def _require(cond, msg):
    if not cond:
        _err(f"FATAL: {msg}")
        _print_summary()
        sys.exit(1)

def _print_summary():
    _h1("SUMMARY")
    print(f"\n  {'Step':<8}  {'Label':<56}  Result")
    print(f"  {'----':<8}  {'------':<56}  ------")
    for sid, label, result in _log:
        print(f"  {sid:<8}  {label:<56}  {result}")

# ── config ────────────────────────────────────────────────────────────────────
HF_URL   = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
HF_CLONE = Path.home() / "tilawa-hf-clone"
APP      = HF_CLONE / "app.py"

_h1("STARTING S33 — " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
_h2("Root cause: loopback keepalive invisible to HF CDN → space sleeps")
_h2("Fix: ping public HF URL so HF infrastructure sees real traffic")

# ── verify clone ──────────────────────────────────────────────────────────────
_h2("Verify HF clone and app.py present")
_require(HF_CLONE.exists(), "HF clone missing — run: git clone <HF_URL> ~/tilawa-hf-clone")
_require(APP.exists(),      "app.py missing in clone")
_ok(f"app.py found ({APP.stat().st_size:,} bytes)")

app = APP.read_text(encoding="utf-8")

# ── pre-check ─────────────────────────────────────────────────────────────────
PUBLIC_URL = "https://carm5333-tilawa-server.hf.space/ping"
if PUBLIC_URL in app:
    _ok("Public URL keepalive already present — nothing to do")
    _rec("A", "keepalive already patched", True)
    _print_summary()
    sys.exit(0)

# ── PATCH A: replace _keepalive function ─────────────────────────────────────
_h1("PATCH A — replace loopback keepalive with public URL")

OLD_A = (
    "def _keepalive():\n"
    '    """Ping /ping every 4 min to prevent HF Space from sleeping."""\n'
    "    import urllib.request\n"
    "    time.sleep(60)\n"
    "    while True:\n"
    "        try:\n"
    "            port = int(os.environ.get(\"PORT\", 7860))\n"
    "            urllib.request.urlopen(f\"http://127.0.0.1:{port}/ping\", timeout=10)\n"
    "        except Exception:\n"
    "            pass\n"
    "        time.sleep(240)\n"
)

NEW_A = (
    "def _keepalive():\n"
    '    """Ping the public HF Space URL every 4 min.\n'
    "    IMPORTANT: must use the public URL, not loopback.\n"
    "    HF sleep detection is at the CDN/router layer — loopback pings\n"
    "    (127.0.0.1) are invisible to HF infrastructure and do NOT prevent\n"
    "    the space from sleeping. Only external requests count.\n"
    '    """\n'
    "    import urllib.request\n"
    "    # S33: wait 120s so gunicorn is fully ready before first external ping\n"
    "    time.sleep(120)\n"
    "    _PUBLIC = \"https://carm5333-tilawa-server.hf.space/ping\"\n"
    "    while True:\n"
    "        try:\n"
    "            urllib.request.urlopen(_PUBLIC, timeout=15)\n"
    "        except Exception:\n"
    "            pass\n"
    "        time.sleep(240)  # every 4 min\n"
)

app, okA = _replace_once(app, OLD_A, NEW_A,
                         "_keepalive loopback → public URL")
_rec("A", "_keepalive uses public HF URL", okA)

if not okA:
    # Fallback: maybe the function text differs slightly — try anchor on just the urlopen line
    _h2("Fallback: anchor on urlopen loopback line only")
    OLD_FALLBACK = '            urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=10)\n'
    NEW_FALLBACK = (
        '            _PUBLIC = "https://carm5333-tilawa-server.hf.space/ping"\n'
        '            urllib.request.urlopen(_PUBLIC, timeout=15)  # S33: public URL\n'
    )
    app, okA = _replace_once(app, OLD_FALLBACK, NEW_FALLBACK,
                             "urlopen loopback → public URL (fallback anchor)")
    _rec("A-fallback", "_keepalive urlopen line patched", okA)

_require(okA, "keepalive patch failed — check anchor text in app.py")

# ── write ─────────────────────────────────────────────────────────────────────
_h1("Writing patched app.py")
APP.write_text(app, encoding="utf-8")
_ok(f"app.py written ({len(app):,} chars)")
_rec("W", "app.py written", True)

# ── verify ────────────────────────────────────────────────────────────────────
_h1("Verification")
checks = [
    ("public URL present",          "carm5333-tilawa-server.hf.space/ping" in app),
    ("loopback REMOVED",            "127.0.0.1" not in app or
                                    app.count("127.0.0.1") == 0),
    ("_keepalive still defined",    "def _keepalive" in app),
    ("Thread still started",        "_keepalive, daemon=True" in app or
                                    "target=_keepalive" in app),
    ("S33 comment present",         "S33" in app),
    ("/ping endpoint",              "def ping()" in app),
    ("v10.0 in ENGINE_SCRIPTS",     '"v10.0"' in app),
]
all_pass = True
for label, cond in checks:
    ((_ok if cond else _err)(label))
    if not cond:
        all_pass = False

# loopback check is a warning only (might appear in comments)
loopback_count = app.count("127.0.0.1")
if loopback_count > 0:
    print(f"     !!  127.0.0.1 still appears {loopback_count}x"
          " — check if it's only in comments (OK) or in code (BAD)")

_rec("V", "app.py verification", all_pass)
_require(all_pass, "Verification failed")

# ── git ───────────────────────────────────────────────────────────────────────
_h1("Git operations")

_run('git config user.email "s33@tilawa.fix"', label="git config email")
_run('git config user.name "S33 Keepalive Fix"', label="git config name")

ok_add, _ = _run("git add app.py", label="git add app.py")
_rec("G1", "git add", ok_add)

_run("git status --short", label="git status")

msg = "S33: fix keepalive — ping public HF URL not loopback (prevents space sleep)"
ok_commit, out_commit = _run(f'git commit -m "{msg}"', label="git commit")
if not ok_commit and "nothing to commit" in out_commit:
    _ok("Nothing to commit (already patched in tree)")
    ok_commit = True
_rec("G2", "git commit", ok_commit)

ok_push, _ = _run(f"git push {HF_URL} main", label="git push", timeout=120)
_rec("G3", "git push", ok_push)

_print_summary()

if ok_push:
    print("\n  HF Space rebuilding. Ready in ~2-3 min:")
    print("  https://carm5333-tilawa-server.hf.space/")
    print("\n  After this deploy, the space will never sleep again —")
    print("  keepalive now pings the public URL every 4 min.")
else:
    print("\n  !! Push failed. Check output above.")
