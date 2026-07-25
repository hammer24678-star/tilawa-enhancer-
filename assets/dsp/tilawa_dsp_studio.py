#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tilawa_dsp_studio.py — S228 "Studio Engine" · S236 v2 "full FX suite + analysis"
· S245 "real EBU R128 loudness" · S250 v4 "every embedded package wired up"

General-purpose numpy/scipy audio DSP engine for the Tilawa Audio Editor.

S250 — ALL 14 pip packages shipped in python-env.tar.gz now have a real job
here. Before this revision only 3 of them were ever imported (noisereduce,
webrtcvad, pystoi) and — see build_assets.sh — the offline install that was
supposed to place them on-device silently failed, so even those three were
never actually there. Run `python3 tilawa_dsp_studio.py --libs <out.json>`
for the live per-package availability/version report the app's Studio tab
renders:

  nara_wpe     WPE dereverberation (removes mosque/room reverb tails)
  noisereduce  spectral-gating denoise (stationary + non-stationary)
  webrtcvad    speech-aware trim AND internal pause squeezing
  pystoi       STOI / ESTOI speech-intelligibility scoring
  pyloudnorm   real ITU-R BS.1770-4 meter (vendored algorithm as fallback)
  soundfile    direct libsndfile decode/encode fast path (skips ffmpeg)
  soxr         high-quality resampling (export SR, pitch, VAD framing)
  audioread    last-resort decoder when ffmpeg is unavailable
  joblib       parallel per-channel processing of the heavy stages
  decorator    @_stage timing wrapper — per-stage ms in the run report
  tqdm         live progress written to a sidecar file the UI polls
  msgpack      binary analysis cache (instant waveform on re-open)
  pooch        content hashing for that cache key
  lazy_loader  defers the heavy imports so light runs stay fast

Every one of them fails soft: if a package is missing the stage either falls
back to a numpy/scipy implementation or becomes a no-op, so an older
python-env.tar.gz keeps working.

NOT shipped: librosa. It hard-imports numba, numba needs llvmlite, and
llvmlite publishes no musl/aarch64 wheel — building it would mean compiling
LLVM inside QEMU on every CI run (the exact trap S240 had to undo for
DeepFilter). Its features are implemented natively here instead: HPSS
harmonic/percussive separation, F0 tracking, spectral centroid and onset
detection are all plain numpy/scipy below. If a future environment does
provide librosa, the relevant helpers pick it up automatically.

IMPORTANT: this is deliberately NOT one of the Quran-restoration engines
(الصفاء / الإتقان / الاسترداد / إحياء ...). Those stay untouched, mono-focused,
and tuned to Sheikh-specific acoustic profiles. This script is a general
stereo audio tool — trim/EQ/effects/export — that happens to live in the
same app. Keep it that way: no restoration-engine imports, no shared state.

Runs entirely inside the existing proot Alpine environment (same python3 +
numpy + scipy already verified by LocalEngineRunner.numpyWorks() for the
main engines) via the audio editor's generic `runProotCmd` shell channel —
no new native/Kotlin code needed. Decodes/encodes through ffmpeg pipes
(f32le), exactly like the restoration engines do, to avoid any soundfile
dependency.

USAGE (process):
    python3 tilawa_dsp_studio.py <in_path> <out_path> <params_json_path>

USAGE (analysis — S236):
    python3 tilawa_dsp_studio.py --analyze <in_path> <out_json_path>

Analysis writes JSON to <out_json_path> (NOT stdout — the proot channel
truncates stdout to its last 800 chars): real waveform peak/RMS buckets,
a log-spaced average spectrum, duration, peak/RMS dBFS, real integrated
LUFS + Loudness Range (LRA) + true-peak (dBTP), and clipping percentage.
The Flutter side uses it to draw the *actual* waveform instead of
placeholder bars, and to power the Compliance tab's platform checklist.

<params_json_path> is a JSON file (see audio_editor_screen.dart
_buildDspParams()) describing the trim window, EQ bands, and every effect —
including, since S236, the entire `fx2` block (tone shaping, character FX,
stereo/space, cleanup & dynamics), which previously only existed in the
ffmpeg fallback chain and was silently dropped whenever this engine
succeeded. Prints {"ok": true} / {"ok": false, "error": "..."} to stdout
and exits 0/1 accordingly — the Dart side treats a non-zero exit as "fall
back to the plain ffmpeg filter chain", so it's safe for this script to
fail loud rather than produce silently-wrong audio.

Pipeline order (fixed, applied only where the relevant param is non-default):
  reverse → auto-trim silence → declip → declick → noise gate → de-hum →
  parametric EQ → spectral noise reduction → high/low-pass →
  bass/treble shelves → sub-bass → presence → vocal isolate →
  echo → convolution reverb →
  compressor → pitch shift → time stretch →
  tremolo → vibrato → chorus → flanger → phaser → bitcrush →
  stereo width → Haas widen → stereo enhance → swap/channel mode →
  de-esser → adaptive normalize → limiter →
  volume → loudness (real ITU-R BS.1770-4 LUFS) normalize + true-peak limit →
  fades → pad start/end → clip → encode
"""
import sys
import os
import json
import subprocess
import time

import numpy as np

try:
    from scipy import signal
    SCIPY_OK = True
except Exception:
    SCIPY_OK = False


# ═══════════════════════════════════════════════════════════════════════════
# S250 — EMBEDDED PACKAGE LAYER
# ═══════════════════════════════════════════════════════════════════════════
# One place that knows which of the S247 packages are actually installed in
# this python-env.tar.gz, what each of them powers, and how to get at them
# without paying the import cost on runs that don't need them.
#
# `lazy_loader` (itself one of the embedded packages) is used for exactly its
# intended purpose: noisereduce, nara_wpe and soundfile each pull in a chunk
# of numpy/scipy/cffi machinery at import time, and a plain trim/EQ export
# must not pay for any of it. lazy_loader.load() hands back a module proxy
# that only really imports on first attribute access, so probing what's
# installed stays cheap.

def _version_of(name: str):
    try:
        from importlib import metadata
        return metadata.version(name)
    except Exception:
        pass
    # Some builds install a C extension under a different distribution name
    # (e.g. webrtcvad-wheels provides the `webrtcvad` module) — ask the module.
    try:
        import importlib
        return str(getattr(importlib.import_module(name), '__version__', '') or '') or None
    except Exception:
        return None


# name → (import name, what it powers). Order is the order the UI lists them.
# These are exactly the 14 packages build_assets.sh installs and verifies.
_PKG_ROLES = [
    ('nara_wpe',    'nara_wpe',    'WPE dereverberation'),
    ('noisereduce', 'noisereduce', 'spectral-gating noise reduction'),
    ('webrtcvad',   'webrtcvad',   'speech-aware trim & pause squeeze'),
    ('pystoi',      'pystoi',      'STOI / ESTOI intelligibility score'),
    ('pyloudnorm',  'pyloudnorm',  'ITU-R BS.1770-4 loudness meter'),
    ('soundfile',   'soundfile',   'direct libsndfile decode/encode'),
    ('soxr',        'soxr',        'high-quality resampling'),
    ('audioread',   'audioread',   'fallback decoder (no ffmpeg)'),
    ('joblib',      'joblib',      'parallel per-channel processing'),
    ('decorator',   'decorator',   'per-stage timing report'),
    ('tqdm',        'tqdm',        'live progress for the UI'),
    ('msgpack',     'msgpack',     'binary analysis cache'),
    ('pooch',       'pooch',       'analysis cache hashing'),
    ('lazy_loader', 'lazy_loader', 'deferred heavy imports'),
]


def _importable(mod: str) -> bool:
    """True if `mod` can be imported, without keeping it loaded on failure."""
    try:
        from importlib.util import find_spec
        return find_spec(mod) is not None
    except Exception:
        return False


_HAVE = {name: _importable(mod) for name, mod, _ in _PKG_ROLES}

# Heavy modules go through lazy_loader when it's available; the eager import
# is only a fallback so behaviour is identical either way.
if _HAVE['lazy_loader']:
    import lazy_loader as _lazy

    def _lazy_mod(mod: str):
        try:
            return _lazy.load(mod, error_on_import=False)
        except Exception:
            return None
else:
    def _lazy_mod(mod: str):
        try:
            import importlib
            return importlib.import_module(mod)
        except Exception:
            return None


_MOD_CACHE = {}


def _mod(name: str):
    """Import-on-demand accessor. Returns None (never raises) when the
    package is absent, so every caller can just `if m is None: return x`."""
    if name in _MOD_CACHE:
        return _MOD_CACHE[name]
    m = _lazy_mod(name) if _HAVE.get(name) else None
    if m is not None:
        try:                     # lazy proxies only fail on first real use
            getattr(m, '__name__')
        except Exception:
            m = None
    _MOD_CACHE[name] = m
    return m


def libs_report(out_json: str = '') -> int:
    """`--libs` mode: what the Studio tab's "Engine Libraries" panel renders."""
    pkgs = []
    for name, mod, role in _PKG_ROLES:
        ok = _HAVE.get(name, False)
        pkgs.append({'name': name, 'ok': ok, 'role': role,
                     'version': _version_of(name) if ok else None})
    payload = {'ok': True, 'numpy': _version_of('numpy'), 'scipy': SCIPY_OK,
               'scipy_version': _version_of('scipy'),
               'python': '%d.%d.%d' % sys.version_info[:3],
               'ffmpeg': _ffmpeg_available(),
               'count_ok': sum(1 for p in pkgs if p['ok']),
               'count_total': len(pkgs), 'packages': pkgs}
    if out_json:
        try:
            with open(out_json, 'w', encoding='utf-8') as fh:
                json.dump(payload, fh)
        except Exception as e:
            print(json.dumps({'ok': False, 'error': f'cannot write report: {e}'}))
            return 1
    print(json.dumps({'ok': True, 'count_ok': payload['count_ok'],
                      'count_total': payload['count_total']}))
    return 0


def _ffmpeg_available() -> bool:
    try:
        r = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


# ─── decorator: per-stage timing, reported back to the app ─────────────────
# `decorator` preserves the wrapped function's signature (a plain functools
# wrapper does not), which matters here because the pipeline calls these
# stages positionally *and* by keyword.

_STAGE_MS = []          # [(stage name, milliseconds)] in execution order


def _stage(label: str):
    """Times a DSP stage, records it, and ticks the progress bar."""
    def deco(fn):
        def wrapper(f, *a, **kw):
            t0 = time.time()
            try:
                return f(*a, **kw)
            finally:
                _STAGE_MS.append((label, round((time.time() - t0) * 1000.0, 1)))
                _PROGRESS.tick(label)
        d = _mod('decorator')
        if d is not None:
            try:
                return d.decorator(wrapper, fn)
            except Exception:
                pass
        import functools

        @functools.wraps(fn)
        def plain(*a, **kw):
            return wrapper(fn, *a, **kw)
        return plain
    return deco


# ─── tqdm: live progress into a sidecar file the Flutter side polls ─────────
# The proot channel is a single blocking call with truncated stdout, so the
# only way to show real progress in the UI is a file. tqdm does the rate/ETA
# formatting; this wrapper keeps just the newest rendered line in the file.

class _ProgressSink:
    def __init__(self):
        self.path = None
        self._buf = ''

    def open(self, path):
        self.path = path or None

    def write(self, s):
        if not s:
            return
        # tqdm redraws with \r; keep only the newest frame
        self._buf = (self._buf + s).split('\r')[-1].split('\n')[-1]

    def flush(self):
        if not self.path:
            return
        try:
            with open(self.path, 'w', encoding='utf-8') as fh:
                fh.write(self._buf)
        except Exception:
            pass


class _Progress:
    """total-agnostic stage progress: each tick advances one step."""

    def __init__(self):
        self.bar = None
        self.sink = _ProgressSink()

    def start(self, total: int, path: str = ''):
        self.sink.open(path)
        if not path:
            return
        t = _mod('tqdm')
        if t is None:
            return
        try:
            self.bar = t.tqdm(total=max(1, total), file=self.sink, mininterval=0,
                              bar_format='{n_fmt}/{total_fmt}|{desc}', ascii=True)
        except Exception:
            self.bar = None

    def tick(self, label: str = ''):
        if self.bar is None:
            return
        try:
            self.bar.set_description_str(label, refresh=False)
            self.bar.update(1)
            self.sink.flush()
        except Exception:
            pass

    def done(self):
        if self.bar is None:
            return
        try:
            self.bar.set_description_str('done', refresh=False)
            self.bar.n = self.bar.total
            self.bar.refresh()
            self.sink.flush()
            self.bar.close()
        except Exception:
            pass


_PROGRESS = _Progress()


# ─── joblib: run the heavy per-channel stages on both channels at once ──────

def _par_channels(fn, x, *args, **kwargs):
    """Apply `fn(mono_channel, *args)` to every channel and restack.
    Uses joblib threads when available (numpy/scipy release the GIL in the
    filter/FFT kernels, so threads give a real ~2x on stereo without the
    memory cost of forking a second Python on a phone)."""
    ch = x.shape[1]
    if ch < 2:
        return np.stack([fn(x[:, 0], *args, **kwargs)], axis=1).astype(np.float32)
    jl = _mod('joblib') if ch > 1 else None
    cols = None
    if jl is not None:
        try:
            cols = jl.Parallel(n_jobs=ch, prefer='threads')(
                jl.delayed(fn)(x[:, c], *args, **kwargs) for c in range(ch))
        except Exception:
            cols = None
    if cols is None:
        cols = [fn(x[:, c], *args, **kwargs) for c in range(ch)]
    n = min(len(c) for c in cols)
    return np.stack([np.asarray(c[:n]) for c in cols], axis=1).astype(np.float32)


# ─── soxr: high-quality resampling, with a scipy fallback ───────────────────

def _resample(x, sr_from: int, sr_to: int):
    """Resample along axis 0 (works for mono vectors and (n, ch) blocks)."""
    if sr_from == sr_to or sr_from <= 0 or sr_to <= 0:
        return x
    sx = _mod('soxr')
    if sx is not None:
        try:
            return np.asarray(sx.resample(x, sr_from, sr_to, quality='HQ'),
                              dtype=np.float32)
        except Exception:
            pass
    if not SCIPY_OK:
        return x
    n_out = max(1, int(round(x.shape[0] * sr_to / float(sr_from))))
    return signal.resample(x, n_out, axis=0).astype(np.float32)


# ─── I/O via ffmpeg pipes (same convention as the restoration engines) ──────

_SF_EXTS = ('.wav', '.flac', '.ogg', '.oga', '.opus', '.aiff', '.aif', '.w64', '.caf')


def _to_stereo(x):
    """(n,) or (n,ch) → (n,2) float32."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    elif x.shape[1] > 2:
        x = x[:, :2]
    return np.ascontiguousarray(x)


def _decode_soundfile(path: str, sr: int, start: float, dur: float):
    """S250 — libsndfile fast path. For the formats soundfile handles natively
    this skips spawning ffmpeg and piping f32le through a pipe entirely, which
    is a large win on the analysis pass (it runs on every file you open) and
    on WAV round-trips. Seeks to `start` instead of decoding-then-discarding."""
    sf = _mod('soundfile')
    if sf is None or not path.lower().endswith(_SF_EXTS):
        return None
    try:
        with sf.SoundFile(path) as f:
            in_sr = int(f.samplerate)
            if start > 0:
                f.seek(min(int(start * in_sr), len(f)))
            frames = int(dur * in_sr) if dur > 0 else -1
            data = f.read(frames=frames, dtype='float32', always_2d=True)
        if data is None or len(data) == 0:
            return None
        x = _to_stereo(data)
        return _resample(x, in_sr, sr) if in_sr != sr else x
    except Exception:
        return None


def _decode_ffmpeg(path: str, sr: int, start: float, dur: float):
    cmd = ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error']
    if start > 0:
        cmd += ['-ss', f'{start:.3f}']
    cmd += ['-i', path]
    if dur > 0:
        cmd += ['-t', f'{dur:.3f}']
    cmd += ['-ar', str(sr), '-ac', '2', '-f', 'f32le', '-']
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=600)
    except Exception:
        return None
    if r.returncode != 0 or len(r.stdout) < 8:
        return None
    data = np.frombuffer(r.stdout, dtype=np.float32)
    if len(data) % 2 == 1:
        data = data[:-1]
    return data.reshape(-1, 2).copy()


def _decode_audioread(path: str, sr: int, start: float, dur: float):
    """S250 — last resort. audioread goes through whatever media backend the
    system has (including Android's own), so a broken/missing ffmpeg in the
    proot rootfs no longer means "the editor can't open this file"."""
    ar = _mod('audioread')
    if ar is None:
        return None
    try:
        with ar.audio_open(path) as f:
            in_sr, ch = int(f.samplerate), int(f.channels)
            chunks = []
            for buf in f:
                chunks.append(np.frombuffer(buf, dtype='<i2'))
            if not chunks:
                return None
        pcm = np.concatenate(chunks).astype(np.float32) / 32768.0
        usable = (len(pcm) // max(1, ch)) * max(1, ch)
        x = _to_stereo(pcm[:usable].reshape(-1, max(1, ch)))
        if start > 0:
            x = x[min(int(start * in_sr), len(x)):]
        if dur > 0:
            x = x[:int(dur * in_sr)]
        if len(x) == 0:
            return None
        return _resample(x, in_sr, sr) if in_sr != sr else x
    except Exception:
        return None


def _decode(path: str, sr: int, start: float, dur: float):
    """Decode (and trim) input to interleaved stereo float32.
    soundfile → ffmpeg → audioread, first one that works wins."""
    for fn in (_decode_soundfile, _decode_ffmpeg, _decode_audioread):
        x = fn(path, sr, start, dur)
        if x is not None and x.shape[0] > 0:
            return x
    return None


def _encode_soundfile(x, sr: int, out_path: str, out_sr: int, out_ch: int,
                      depth: int, meta: dict) -> bool:
    """S250 — WAV export straight through libsndfile: exact bit depth, no
    subprocess, and soxr (not ffmpeg's resampler) for any rate change. Also
    writes the metadata tags libsndfile supports, so a WAV export no longer
    silently loses them just because it took this faster path."""
    sf = _mod('soundfile')
    if sf is None:
        return False
    subtype = {16: 'PCM_16', 24: 'PCM_24', 32: 'PCM_32'}.get(depth, 'PCM_16')
    try:
        y = _resample(x, sr, out_sr) if out_sr != sr else x
        if out_ch == 1:
            y = y.mean(axis=1, keepdims=True)
        y = np.clip(y, -1.0, 1.0).astype(np.float32)
        with sf.SoundFile(out_path, mode='w', samplerate=int(out_sr),
                          channels=int(out_ch), subtype=subtype) as f:
            for tag, key in (('title', 'title'), ('artist', 'artist'), ('album', 'album')):
                v = str(meta.get(key, '') or '').strip()
                if v:
                    try:
                        setattr(f, tag, v)
                    except Exception:
                        pass
            f.write(y)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 44
    except Exception:
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
        return False


def _encode(x: 'np.ndarray', sr: int, out_path: str, out_cfg: dict) -> bool:
    """S236: honors the Export-tab details that v1 ignored — output sample
    rate, mono/stereo channel count, WAV bit depth and metadata tags.
    S250: WAV goes through soundfile+soxr when available; lossy formats still
    need ffmpeg's encoders."""
    fmt = str(out_cfg.get('format', 'WAV')).upper()
    kbps = int(out_cfg.get('kbps', 192))
    out_sr = int(out_cfg.get('sample_rate', sr) or sr)
    out_ch = 1 if str(out_cfg.get('channels', 'Stereo')) == 'Mono' else 2
    depth = int(out_cfg.get('wav_bit_depth', 16) or 16)
    meta = out_cfg.get('metadata', {}) or {}

    if fmt == 'WAV' and _encode_soundfile(x, sr, out_path, out_sr, out_ch, depth, meta):
        return True

    x = np.asarray(x)
    in_ch = x.shape[1] if x.ndim > 1 else 1
    raw = np.clip(x, -1.0, 1.0).astype(np.float32).tobytes()
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
           '-f', 'f32le', '-ar', str(sr), '-ac', str(in_ch), '-i', '-']
    for tag in ('title', 'artist', 'album'):
        v = str(meta.get(tag, '') or '').strip()
        if v:
            cmd += ['-metadata', f'{tag}={v}']
    cmd += ['-ar', str(out_sr), '-ac', str(out_ch)]
    if fmt == 'WAV':
        pcm = {16: 'pcm_s16le', 24: 'pcm_s24le', 32: 'pcm_s32le'}.get(depth, 'pcm_s16le')
        cmd += ['-c:a', pcm, out_path]
    else:
        codec = {'MP3': 'libmp3lame', 'M4A': 'aac'}.get(fmt, 'libmp3lame')
        cmd += ['-c:a', codec, '-b:a', f'{kbps}k', out_path]
    try:
        r = subprocess.run(cmd, input=raw, capture_output=True, timeout=600)
    except Exception:
        return False
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 44


# ─── Biquad designers — RBJ audio-cookbook ──────────────────────────────────

def _peaking_biquad(freq: float, gain_db: float, q: float, sr: int):
    """RBJ audio-cookbook peaking-EQ biquad coefficients."""
    a_amp = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    alpha = np.sin(w0) / (2.0 * q)
    cosw0 = np.cos(w0)
    b0 = 1 + alpha * a_amp
    b1 = -2 * cosw0
    b2 = 1 - alpha * a_amp
    a0 = 1 + alpha / a_amp
    a1 = -2 * cosw0
    a2 = 1 - alpha / a_amp
    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    return b, a


def _shelf_biquad(freq: float, gain_db: float, sr: int, kind: str = 'low',
                  slope: float = 0.9):
    """RBJ low-shelf / high-shelf biquad — real tone-shaping filters for the
    FX+ Bass/Treble Boost rows (v1 delegated these to ffmpeg `bass=`/`treble=`
    and then dropped them whenever the engine succeeded)."""
    a_amp = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    cosw0, sinw0 = np.cos(w0), np.sin(w0)
    alpha = sinw0 / 2.0 * np.sqrt((a_amp + 1 / a_amp) * (1 / slope - 1) + 2)
    two_sq = 2 * np.sqrt(a_amp) * alpha
    if kind == 'low':
        b0 = a_amp * ((a_amp + 1) - (a_amp - 1) * cosw0 + two_sq)
        b1 = 2 * a_amp * ((a_amp - 1) - (a_amp + 1) * cosw0)
        b2 = a_amp * ((a_amp + 1) - (a_amp - 1) * cosw0 - two_sq)
        a0 = (a_amp + 1) + (a_amp - 1) * cosw0 + two_sq
        a1 = -2 * ((a_amp - 1) + (a_amp + 1) * cosw0)
        a2 = (a_amp + 1) + (a_amp - 1) * cosw0 - two_sq
    else:
        b0 = a_amp * ((a_amp + 1) + (a_amp - 1) * cosw0 + two_sq)
        b1 = -2 * a_amp * ((a_amp - 1) + (a_amp + 1) * cosw0)
        b2 = a_amp * ((a_amp + 1) + (a_amp - 1) * cosw0 - two_sq)
        a0 = (a_amp + 1) - (a_amp - 1) * cosw0 + two_sq
        a1 = 2 * ((a_amp - 1) - (a_amp + 1) * cosw0)
        a2 = (a_amp + 1) - (a_amp - 1) * cosw0 - two_sq
    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    return b, a


def _allpass_biquad(freq: float, q: float, sr: int):
    """RBJ allpass biquad — phaser stages."""
    w0 = 2 * np.pi * freq / sr
    alpha = np.sin(w0) / (2.0 * q)
    cosw0 = np.cos(w0)
    a0 = 1 + alpha
    b = np.array([1 - alpha, -2 * cosw0, 1 + alpha]) / a0
    a = np.array([1.0, -2 * cosw0 / a0, (1 - alpha) / a0])
    return b, a


# ─── Parametric EQ — real RBJ-cookbook peaking biquads, cascaded ────────────

def _apply_eq(x, sr, freqs, gains, q):
    """Cascade one zero-phase peaking biquad per non-zero band (real filters,
    not ffmpeg's blunt `equalizer=` chain)."""
    if not SCIPY_OK or not freqs or not gains:
        return x
    nyq = sr / 2.0
    sos_list = []
    for f, g in zip(freqs, gains):
        if abs(g) < 0.1:
            continue
        f = min(max(f, 20.0), nyq * 0.98)
        b, a = _peaking_biquad(f, g, max(q, 0.1), sr)
        sos_list.append(signal.tf2sos(b, a))
    if not sos_list:
        return x
    sos = np.vstack(sos_list)
    return signal.sosfiltfilt(sos, x, axis=0).astype(np.float32)


# ─── Declick — median-filter outlier detection + interpolation ─────────────

def _declick(x, sr, sensitivity):
    if not SCIPY_OK or x.shape[0] < 32:
        return x
    thresh_z = float(np.interp(sensitivity, [0, 100], [8.0, 2.0]))
    y = x.copy()
    idx = np.arange(x.shape[0])
    for ch in range(x.shape[1]):
        sig_ = x[:, ch].astype(np.float64)
        med = signal.medfilt(sig_, kernel_size=7)
        resid = sig_ - med
        mad = np.median(np.abs(resid - np.median(resid))) + 1e-9
        z = np.abs(resid) / (1.4826 * mad)
        bad = z > thresh_z
        good = ~bad
        if np.any(bad) and np.sum(good) > 2:
            sig_[bad] = np.interp(idx[bad], idx[good], sig_[good])
        y[:, ch] = sig_.astype(np.float32)
    return y


# ─── Spectral noise reduction — STFT noise-floor gating ─────────────────────

def _spectral_denoise(x, sr, strength):
    if not SCIPY_OK or strength <= 0:
        return x
    strength = min(max(strength, 0.0), 100.0) / 100.0
    n_fft = 2048
    hop = n_fft // 4
    out = np.zeros_like(x)
    for ch in range(x.shape[1]):
        f, t, z = signal.stft(x[:, ch], fs=sr, nperseg=n_fft,
                               noverlap=n_fft - hop, boundary='zeros')
        mag = np.abs(z)
        phase = np.angle(z)
        noise_floor = np.percentile(mag, 10, axis=1, keepdims=True)
        over_sub = 1.0 + 2.0 * strength
        clean_mag = mag - over_sub * noise_floor
        floor = 0.05 * mag  # spectral floor — avoids "musical noise" artifacts
        clean_mag = np.maximum(clean_mag, floor)
        blended = strength * clean_mag + (1.0 - strength) * mag
        zc = blended * np.exp(1j * phase)
        _, xr = signal.istft(zc, fs=sr, nperseg=n_fft, noverlap=n_fft - hop, boundary=True)
        n = min(len(xr), x.shape[0])
        out[:n, ch] = xr[:n]
    return out.astype(np.float32)


# ─── S248: real noisereduce library (bundled via S247) ──────────────────────
@_stage('denoise')
def _ai_denoise(x, sr, strength, stationary=True):
    """Spectral-gating denoise via the real noisereduce package — separate
    from, and more accurate than, the DIY STFT gate above. Fails soft (no-op)
    if noisereduce isn't installed.

    S250: `stationary=False` switches to noisereduce's non-stationary mode,
    which tracks a moving noise estimate — the right choice for traffic,
    fan-speed changes, or a hall's shifting background, where a single fixed
    noise profile smears the recitation."""
    nr = _mod('noisereduce')
    if strength <= 0 or nr is None:
        return x
    amt = min(max(strength, 0.0), 100.0) / 100.0

    def one(ch_data):
        return nr.reduce_noise(y=np.ascontiguousarray(ch_data, dtype=np.float32),
                               sr=sr, prop_decrease=amt,
                               stationary=bool(stationary), use_tqdm=False)
    return _par_channels(one, x)


# ─── S250: nara_wpe dereverberation ─────────────────────────────────────────
@_stage('dereverb')
def _dereverb(x, sr, strength, taps=10, delay=3):
    """WPE (weighted prediction error) dereverberation — the one tool here
    that actually shortens a room's reverb tail instead of masking it. This is
    what a recitation recorded in a live mosque needs: it estimates the late
    reverberation from the signal's own past and subtracts it, per frequency
    bin, jointly across both channels.

    `strength` 0..100 maps to iteration count and a dry/wet blend so it can be
    dialled in gently — full WPE on a lightly-reverberant file sounds thin.
    Runs at a 16 kHz analysis rate (where reverb energy lives, and where the
    iterations are affordable on a phone) and folds the result back into the
    full-rate signal, keeping the original highs untouched."""
    wpe_mod = _mod('nara_wpe')
    if strength <= 0 or wpe_mod is None or not SCIPY_OK:
        return x
    amt = min(max(float(strength), 0.0), 100.0) / 100.0
    try:
        from nara_wpe.wpe import wpe_v8
        from nara_wpe.utils import stft as wpe_stft, istft as wpe_istft
    except Exception:
        return x
    n0 = x.shape[0]
    work_sr = 16000
    try:
        xr = _resample(x, sr, work_sr) if sr != work_sr else x
        if xr.shape[0] < 4096:
            return x
        size, shift = 512, 128
        # nara_wpe wants (channels, samples) → (D, T, F) → (F, D, T)
        Y = wpe_stft(np.ascontiguousarray(xr.T.astype(np.float64)),
                     size=size, shift=shift).transpose(2, 0, 1)
        iters = int(round(1 + 2 * amt))               # 1..3 iterations
        Z = wpe_v8(Y, taps=int(taps), delay=int(delay), iterations=iters,
                   statistics_mode='full')
        z = wpe_istft(Z.transpose(1, 2, 0), size=size, shift=shift)
        z = np.ascontiguousarray(np.real(z).T).astype(np.float32)
        z = _resample(z, work_sr, sr) if sr != work_sr else z
        n = min(n0, z.shape[0])
        wet = np.zeros_like(x)
        wet[:n] = z[:n]
        if n < n0:                                    # tail beyond WPE output
            wet[n:] = x[n:]
        # gain-match so the blend is timbral, not a level change
        p_dry = float(np.sqrt(np.mean(x ** 2)) + 1e-9)
        p_wet = float(np.sqrt(np.mean(wet ** 2)) + 1e-9)
        wet *= min(max(p_dry / p_wet, 0.25), 4.0)
        mix = 0.35 + 0.65 * amt                       # never a hard 100% wet
        return ((1.0 - mix) * x + mix * wet).astype(np.float32)
    except Exception:
        return x


# ─── S250: harmonic/percussive focus (native HPSS) ──────────────────────────
_HPSS_NFFT = 2048
_HPSS_HOP = 512


def _hpss_masks(mag, kernel=17, power=2.0):
    """Fitzgerald-style median-filter HPSS soft masks.

    Sustained pitched content (a recited voice) is smooth ALONG TIME at a
    fixed frequency, so a median filter across time isolates it; transient
    content (page turns, mic bumps, mouth clicks, chair creaks, room slaps) is
    smooth ACROSS FREQUENCY at a fixed time, so a median filter across
    frequency isolates that. Wiener-style soft masks then split the spectrum.

    This is the algorithm librosa.decompose.hpss implements; it is reproduced
    here in plain scipy because librosa can't ship on-device (see module
    docstring). ~25 lines, no numba, and fast enough to run on a phone."""
    from scipy.ndimage import median_filter
    k = max(3, int(kernel) | 1)
    harm = median_filter(mag, size=(1, k), mode='reflect')
    perc = median_filter(mag, size=(k, 1), mode='reflect')
    hp = harm ** power
    pp = perc ** power
    tot = hp + pp + 1e-12
    return hp / tot, pp / tot


@_stage('harmonic focus')
def _harmonic_focus(x, sr, amount):
    """Splits the signal into harmonic (voice) and percussive (transient
    noise) parts and pulls the percussive part down. This catches the
    transient noises a noise gate can't (they're louder than the threshold)
    and that spectral denoise only smears (they're broadband).
    amount 0..100 = how much of the percussive part to remove."""
    if amount <= 0 or not SCIPY_OK:
        return x
    a = min(max(float(amount), 0.0), 100.0) / 100.0
    lb = _mod('librosa')          # free upgrade if a future env has it
    n_fft, hop = _HPSS_NFFT, _HPSS_HOP

    def one(ch_data):
        y = np.ascontiguousarray(ch_data, dtype=np.float32)
        if len(y) < n_fft * 2:
            return y
        if lb is not None:
            try:
                d = lb.stft(y, n_fft=n_fft, hop_length=hop)
                h, p = lb.decompose.hpss(d, margin=(1.0, 1.0 + 2.0 * a))
                return lb.istft(h + (1.0 - a) * p, hop_length=hop,
                                length=len(y)).astype(np.float32)
            except Exception:
                pass
        _, _, z = signal.stft(y, fs=sr, nperseg=n_fft, noverlap=n_fft - hop,
                              boundary='zeros')
        mag, phase = np.abs(z), np.angle(z)
        mh, mp = _hpss_masks(mag)
        keep = mag * (mh + (1.0 - a) * mp)
        _, out = signal.istft(keep * np.exp(1j * phase), fs=sr, nperseg=n_fft,
                              noverlap=n_fft - hop, boundary=True)
        n = min(len(out), len(y))
        res = np.zeros(len(y), dtype=np.float32)
        res[:n] = out[:n]
        return res
    try:
        return _par_channels(one, x)
    except Exception:
        return x


# ─── S250: native content analysis (F0 / brightness / onsets) ───────────────

def _f0_median(mono, sr, fmin=60.0, fmax=500.0):
    """Median voiced F0 via normalized autocorrelation per frame.

    Frames whose peak clarity is below 0.35 (unvoiced/noise) or whose energy
    is below the file's 60th percentile are discarded before taking the
    median, so pauses and breath don't drag the estimate down."""
    if not SCIPY_OK or len(mono) < sr // 2:
        return None
    frame = int(0.046 * sr) | 1        # ~46 ms — two periods at 60 Hz is 33 ms
    hop = max(1, frame // 2)
    lag_min = max(2, int(sr / fmax))
    lag_max = min(frame - 2, int(sr / fmin))
    if lag_max <= lag_min:
        return None
    starts = np.arange(0, max(1, len(mono) - frame), hop)
    if starts.size == 0:
        return None
    energies = np.array([float(np.mean(mono[s:s + frame] ** 2)) for s in starts])
    thr = float(np.percentile(energies, 60))
    f0s = []
    win = np.hanning(frame)
    for s, e in zip(starts, energies):
        if e < thr or e <= 1e-9:
            continue
        seg = mono[s:s + frame] * win
        seg = seg - seg.mean()
        ac = signal.correlate(seg, seg, mode='full')[frame - 1:]
        if ac[0] <= 1e-12:
            continue
        ac = ac / ac[0]
        band = ac[lag_min:lag_max]
        if band.size == 0:
            continue
        i = int(np.argmax(band))
        if band[i] < 0.35:
            continue
        lag = lag_min + i
        # parabolic interpolation around the peak for sub-sample accuracy
        if 0 < i < band.size - 1:
            a0, b0, c0 = band[i - 1], band[i], band[i + 1]
            denom = (a0 - 2 * b0 + c0)
            if abs(denom) > 1e-12:
                lag += 0.5 * (a0 - c0) / denom
        if lag > 0:
            f0s.append(sr / lag)
    if len(f0s) < 3:
        return None
    return float(np.median(f0s))


def _spectral_centroid(mono, sr):
    """Energy-weighted mean frequency — "brightness" in one number."""
    if not SCIPY_OK or len(mono) < 4096:
        return None
    try:
        f, pxx = signal.welch(mono, fs=sr, nperseg=4096)
        tot = float(np.sum(pxx))
        if tot <= 1e-20:
            return None
        return float(np.sum(f * pxx) / tot)
    except Exception:
        return None


def _onset_rate(mono, sr):
    """Onsets per minute from a spectral-flux novelty curve with adaptive
    thresholding — a proxy for phrase/syllable pace."""
    if not SCIPY_OK or len(mono) < sr:
        return None
    try:
        n_fft, hop = 1024, 256
        _, _, z = signal.stft(mono, fs=sr, nperseg=n_fft, noverlap=n_fft - hop,
                              boundary=None)
        mag = np.abs(z)
        flux = np.sum(np.clip(np.diff(mag, axis=1), 0, None), axis=0)
        if flux.size < 8:
            return None
        k = min(21, (flux.size // 2) * 2 + 1)
        local = signal.medfilt(flux, kernel_size=k if k % 2 else k + 1)
        thr = local + 0.6 * float(np.std(flux))
        above = flux > thr
        onsets = int(np.sum(above[1:] & ~above[:-1]))
        minutes = max(len(mono) / float(sr) / 60.0, 1e-6)
        return float(onsets) / minutes
    except Exception:
        return None


# ─── Echo — true feedback delay line (IIR, not ffmpeg aecho) ────────────────

def _echo(x, sr, mix, delay_s=0.35, feedback=0.35):
    if not SCIPY_OK or mix <= 0:
        return x
    mix = min(max(mix, 0.0), 100.0) / 100.0
    d = max(1, int(delay_s * sr))
    a = np.zeros(d + 1, dtype=np.float64)
    a[0] = 1.0
    a[d] = -feedback
    wet = signal.lfilter([1.0], a, x.astype(np.float64), axis=0)
    peak = np.max(np.abs(wet)) + 1e-9
    if peak > 1.5:
        wet = wet / peak * 1.2
    return ((1.0 - mix) * x + mix * wet).astype(np.float32)


# ─── Convolution reverb — procedurally synthesized impulse response ────────

_REVERB_PRESETS = {
    'Room':      (0.35, 0.007),
    'Hall':      (1.80, 0.018),
    'Plate':     (1.10, 0.010),
    'Cathedral': (3.40, 0.030),
}


def _make_ir(sr, rtype):
    decay_s, predelay_s = _REVERB_PRESETS.get(rtype, _REVERB_PRESETS['Room'])
    n = max(8, int(sr * decay_s))
    t = np.arange(n) / sr
    rng = np.random.default_rng(1234)
    noise = rng.standard_normal(n).astype(np.float64)
    ir = np.zeros(n, dtype=np.float64)
    for tap_t, tap_g in [(0.007, 0.50), (0.013, 0.35), (0.021, 0.25), (0.034, 0.18)]:
        i = int(tap_t * sr)
        if i < n:
            ir[i] += tap_g
    env = np.exp(-t / (decay_s / 5.0))
    ir = ir + 0.6 * noise * env
    predelay_n = int(predelay_s * sr)
    if predelay_n > 0 and predelay_n < n:
        ir[:predelay_n] *= 0.2
    peak = np.max(np.abs(ir)) + 1e-9
    return (ir / peak).astype(np.float32)


def _reverb(x, sr, mix, rtype):
    if not SCIPY_OK or mix <= 0:
        return x
    mix = min(max(mix, 0.0), 100.0) / 100.0
    ir = _make_ir(sr, rtype)
    wet = np.zeros_like(x)
    dry_peak = np.max(np.abs(x)) + 1e-9
    for ch in range(x.shape[1]):
        w = signal.fftconvolve(x[:, ch], ir, mode='full')[:x.shape[0]]
        wet[:, ch] = w
    wet_peak = np.max(np.abs(wet)) + 1e-9
    wet = wet / wet_peak * dry_peak
    return ((1.0 - mix) * x + mix * wet).astype(np.float32)


# ─── Block envelope helper (compressor / gate / limiter share this) ─────────

def _block_env(x, sr, block_s=0.001, attack_ms=5.0, release_ms=150.0):
    """Per-block peak envelope with one-pole attack/release smoothing.
    Returns (env_per_block, block_len)."""
    block = max(16, int(sr * block_s))
    n = x.shape[0]
    nb = int(np.ceil(n / block))
    xa = np.abs(x).max(axis=1)
    pad = nb * block - n
    if pad:
        xa = np.concatenate([xa, np.zeros(pad)])
    lvl = xa.reshape(nb, block).max(axis=1)
    atk = np.exp(-block / (sr * max(attack_ms, 0.1) / 1000.0))
    rel = np.exp(-block / (sr * max(release_ms, 1.0) / 1000.0))
    env = np.zeros(nb, dtype=np.float64)
    e_prev = 0.0
    for i in range(nb):
        coeff = atk if lvl[i] > e_prev else rel
        e_prev = coeff * e_prev + (1.0 - coeff) * lvl[i]
        env[i] = e_prev
    return env, block


def _expand_gain(gain_b, block, n):
    return np.repeat(gain_b, block)[:n]


# ─── Compressor — block-envelope follower (fast, not sample-by-sample) ─────

def _compressor(x, sr, threshold_db, ratio, attack_ms, release_ms, makeup_db):
    if ratio <= 1.0:
        return x
    env, block = _block_env(x, sr, 0.001, attack_ms, release_ms)
    thr = 10 ** (threshold_db / 20.0)
    gain_b = np.ones_like(env)
    over = env > thr
    gain_b[over] = (thr + (env[over] - thr) / ratio) / (env[over] + 1e-12)
    gain = _expand_gain(gain_b, block, x.shape[0])
    makeup = 10 ** (makeup_db / 20.0)
    return (x * gain[:, None] * makeup).astype(np.float32)


# ─── Pitch shift / time stretch — real phase vocoder (STFT), decoupled ─────
# Old ffmpeg pipeline hacked pitch via asetrate+atempo (chipmunk artifacts and
# tempo/pitch coupled together). This is a genuine phase vocoder: pitch and
# tempo are independent controls, each backed by the same stretch primitive.

def _phase_vocoder_stretch(x, stretch, n_fft=2048, hop=512):
    """Time-stretch a mono float64 signal by `stretch` (out_len / in_len),
    preserving pitch, via STFT phase-accumulation (classic phase vocoder)."""
    if not SCIPY_OK or abs(stretch - 1.0) < 1e-3:
        return x.copy()
    n = len(x)
    if n <= n_fft:
        return x.copy()
    window = signal.windows.hann(n_fft, sym=False)
    out_hop = max(1, int(round(hop * stretch)))
    num_frames = 1 + (n - n_fft) // hop
    if num_frames < 1:
        return x.copy()
    n_bins = n_fft // 2 + 1
    omega = 2 * np.pi * hop * np.arange(n_bins) / n_fft
    prev_phase = np.zeros(n_bins)
    phase_acc = np.zeros(n_bins)
    out_len = out_hop * num_frames + n_fft
    y = np.zeros(out_len, dtype=np.float64)
    win_sum = np.zeros(out_len, dtype=np.float64)
    for i in range(num_frames):
        s = i * hop
        frame = x[s:s + n_fft]
        if len(frame) < n_fft:
            frame = np.pad(frame, (0, n_fft - len(frame)))
        spec = np.fft.rfft(frame * window)
        mag = np.abs(spec)
        phase = np.angle(spec)
        dphi = phase - prev_phase - omega
        dphi = dphi - 2 * np.pi * np.round(dphi / (2 * np.pi))
        true_freq = omega + dphi
        prev_phase = phase
        phase_acc = phase_acc + true_freq * stretch
        new_spec = mag * np.exp(1j * phase_acc)
        new_frame = np.fft.irfft(new_spec, n_fft) * window
        os_ = i * out_hop
        y[os_:os_ + n_fft] += new_frame
        win_sum[os_:os_ + n_fft] += window ** 2
    valid = win_sum > 1e-8
    y[valid] /= win_sum[valid]
    return y[:out_len]


@_stage('pitch shift')
def _pitch_shift(x, sr, semitones):
    """S250: the vocoder output is now resampled with soxr's HQ kernel instead
    of scipy.signal.resample (an FFT resampler, which rings on transients and
    forces the whole signal through one big FFT), and both channels run in
    parallel. librosa.effects.pitch_shift is used instead if a future
    environment ever provides it."""
    if abs(semitones) < 1e-3:
        return x
    lb = _mod('librosa')
    if lb is not None:
        try:
            def one_lb(ch_data):
                return lb.effects.pitch_shift(
                    np.ascontiguousarray(ch_data, dtype=np.float32),
                    sr=sr, n_steps=float(semitones), res_type='soxr_hq')
            y = _par_channels(one_lb, x)
            if y.shape[0] > 0:
                return y
        except Exception:
            pass
    if not SCIPY_OK:
        return x
    ratio = 2.0 ** (semitones / 12.0)
    n_target = x.shape[0]

    def one(ch_data):
        stretched = _phase_vocoder_stretch(np.asarray(ch_data, dtype=np.float64), ratio)
        if len(stretched) < 2:
            return np.asarray(ch_data, dtype=np.float32)
        # resample by the same ratio → pitch changes, length comes back
        out = _resample(stretched.astype(np.float32), int(sr * ratio), sr)
        res = np.zeros(n_target, dtype=np.float32)
        n = min(n_target, len(out))
        res[:n] = out[:n]
        return res
    return _par_channels(one, x)


@_stage('time stretch')
def _time_stretch(x, sr, tempo):
    """S250: both channels in parallel (see _pitch_shift)."""
    if abs(tempo - 1.0) < 1e-3:
        return x
    lb = _mod('librosa')
    if lb is not None:
        try:
            def one_lb(ch_data):
                return lb.effects.time_stretch(
                    np.ascontiguousarray(ch_data, dtype=np.float32),
                    rate=float(tempo))
            y = _par_channels(one_lb, x)
            if y.shape[0] > 0:
                return y
        except Exception:
            pass
    if not SCIPY_OK:
        return x

    def one(ch_data):
        return _phase_vocoder_stretch(
            np.asarray(ch_data, dtype=np.float64), 1.0 / tempo).astype(np.float32)
    return _par_channels(one, x)


# ─── S236: FX+ — tone shaping ───────────────────────────────────────────────

def _apply_biquad(x, b, a):
    return signal.lfilter(b, a, x.astype(np.float64), axis=0)


def _tone_shelves(x, sr, bass_db, treble_db):
    if not SCIPY_OK:
        return x
    y = x.astype(np.float64)
    if abs(bass_db) >= 0.05:
        b, a = _shelf_biquad(100.0, float(np.clip(bass_db, -12, 12)), sr, 'low')
        y = _apply_biquad(y, b, a)
    if abs(treble_db) >= 0.05:
        b, a = _shelf_biquad(6500.0, float(np.clip(treble_db, -12, 12)), sr, 'high')
        y = _apply_biquad(y, b, a)
    return y.astype(np.float32)


def _sub_bass(x, sr, amount):
    """Adds a filtered low band back in (asubboost-style) — amount 0..100."""
    if not SCIPY_OK or amount <= 0:
        return x
    a = min(max(amount, 0.0), 100.0) / 100.0
    sos = signal.butter(4, 90.0 / (sr / 2.0), btype='low', output='sos')
    low = signal.sosfilt(sos, x.astype(np.float64), axis=0)
    return (x + a * 1.2 * low).astype(np.float32)


def _presence(x, sr, amount):
    """Clarity/crystalizer: soft-saturated high band mixed back in."""
    if not SCIPY_OK or amount <= 0:
        return x
    a = min(max(amount, 0.0), 100.0) / 100.0
    sos = signal.butter(2, 3500.0 / (sr / 2.0), btype='high', output='sos')
    hi = signal.sosfilt(sos, x.astype(np.float64), axis=0)
    excited = np.tanh(hi * 3.0) / 3.0
    return (x + a * 0.9 * excited).astype(np.float32)


def _hp_lp(x, sr, hp_hz, lp_hz):
    if not SCIPY_OK:
        return x
    y = x.astype(np.float64)
    nyq = sr / 2.0
    if hp_hz and hp_hz > 0:
        f = min(max(float(hp_hz), 10.0), nyq * 0.95)
        sos = signal.butter(2, f / nyq, btype='high', output='sos')
        y = signal.sosfilt(sos, y, axis=0)
    if lp_hz and 0 < lp_hz < 20000:
        f = min(max(float(lp_hz), 100.0), nyq * 0.98)
        sos = signal.butter(2, f / nyq, btype='low', output='sos')
        y = signal.sosfilt(sos, y, axis=0)
    return y.astype(np.float32)


# ─── S236: FX+ — character effects ──────────────────────────────────────────

def _tremolo(x, sr, amount, rate_hz=5.0):
    if amount <= 0:
        return x
    d = min(max(amount, 0.0), 100.0) / 100.0
    t = np.arange(x.shape[0]) / sr
    lfo = 1.0 - d * 0.5 * (1.0 + np.sin(2 * np.pi * rate_hz * t))
    return (x * lfo[:, None]).astype(np.float32)


def _mod_delay_read(x_ch, delay_samps):
    """Fractional modulated-delay read via linear interpolation (vectorized)."""
    n = len(x_ch)
    pos = np.arange(n) - delay_samps
    pos = np.clip(pos, 0.0, n - 1.0)
    return np.interp(pos, np.arange(n), x_ch)


def _vibrato(x, sr, amount, rate_hz=5.0):
    if amount <= 0:
        return x
    d = min(max(amount, 0.0), 100.0) / 100.0
    depth = d * 0.004 * sr          # up to ±4 ms pitch wobble
    base = depth + 8
    t = np.arange(x.shape[0])
    delay = base + depth * np.sin(2 * np.pi * rate_hz * t / sr)
    y = np.zeros_like(x, dtype=np.float64)
    for ch in range(x.shape[1]):
        y[:, ch] = _mod_delay_read(x[:, ch].astype(np.float64), delay)
    return y.astype(np.float32)


def _chorus(x, sr):
    """Three modulated delay taps (~20 ms base) blended with the dry path."""
    n = x.shape[0]
    t = np.arange(n)
    y = x.astype(np.float64).copy()
    for base_ms, depth_ms, rate, gain in [(18, 2.5, 0.8, 0.30),
                                          (24, 3.0, 1.1, 0.25),
                                          (30, 2.0, 0.6, 0.20)]:
        base = base_ms * sr / 1000.0
        depth = depth_ms * sr / 1000.0
        for ch in range(x.shape[1]):
            ph = ch * np.pi / 3  # slight L/R phase offset — wider image
            d2 = base + depth * np.sin(2 * np.pi * rate * t / sr + ph)
            y[:, ch] += gain * _mod_delay_read(x[:, ch].astype(np.float64), d2)
    peak = np.max(np.abs(y)) + 1e-9
    if peak > 1.0:
        y /= peak
    return y.astype(np.float32)


def _flanger(x, sr):
    """Classic swept short delay (0.5–5 ms, 0.25 Hz) mixed 50/50."""
    n = x.shape[0]
    t = np.arange(n)
    base = 0.003 * sr
    depth = 0.0025 * sr
    delay = base + depth * np.sin(2 * np.pi * 0.25 * t / sr)
    y = np.zeros_like(x, dtype=np.float64)
    for ch in range(x.shape[1]):
        wet = _mod_delay_read(x[:, ch].astype(np.float64), delay)
        y[:, ch] = 0.6 * x[:, ch] + 0.6 * wet
    peak = np.max(np.abs(y)) + 1e-9
    if peak > 1.0:
        y /= peak
    return y.astype(np.float32)


def _phaser(x, sr, stages=4, rate_hz=0.5):
    """Block-based cascade of LFO-swept allpass biquads (state carried across
    blocks so sweeps stay click-free)."""
    if not SCIPY_OK:
        return x
    block = 1024
    n = x.shape[0]
    y = np.zeros_like(x, dtype=np.float64)
    for ch in range(x.shape[1]):
        zi = [np.zeros(2) for _ in range(stages)]
        src = x[:, ch].astype(np.float64)
        dst = np.zeros(n, dtype=np.float64)
        for s in range(0, n, block):
            e = min(n, s + block)
            seg = src[s:e]
            t_mid = (s + e) / 2.0 / sr
            sweep = 0.5 * (1.0 + np.sin(2 * np.pi * rate_hz * t_mid))
            f0 = 300.0 * (2.0 ** (sweep * 3.0))  # 300 Hz .. 2.4 kHz sweep
            for st in range(stages):
                b, a = _allpass_biquad(min(f0 * (1.0 + 0.4 * st), sr * 0.45), 0.7, sr)
                seg, zi[st] = signal.lfilter(b, a, seg, zi=zi[st])
            dst[s:e] = seg
        y[:, ch] = 0.5 * src + 0.5 * dst
    return y.astype(np.float32)


def _bitcrush(x, amount):
    """Bit-depth quantize + sample-hold decimation — amount 0..100."""
    if amount <= 0:
        return x
    a = min(max(amount, 0.0), 100.0) / 100.0
    bits = 16.0 - a * 12.0                    # 16 → 4 bits
    levels = 2.0 ** bits
    y = np.round(x.astype(np.float64) * levels) / levels
    hold = int(1 + round(a * 7))              # 1 → 8× sample-hold
    if hold > 1:
        n = y.shape[0]
        idx = (np.arange(n) // hold) * hold
        y = y[idx]
    return y.astype(np.float32)


# ─── S236: FX+ — stereo & space ─────────────────────────────────────────────

def _stereo_width(x, width):
    if x.shape[1] < 2 or abs(width - 1.0) < 1e-3:
        return x
    mid = (x[:, 0] + x[:, 1]) * 0.5
    side = (x[:, 0] - x[:, 1]) * 0.5 * width
    left = mid + side
    right = mid - side
    return np.stack([left, right], axis=1).astype(np.float32)


def _haas(x, sr, delay_ms=15.0):
    """Haas widener — delays the right channel a few ms."""
    d = int(sr * delay_ms / 1000.0)
    if d <= 0 or d >= x.shape[0] or x.shape[1] < 2:
        return x
    r = np.concatenate([np.zeros(d, dtype=x.dtype), x[:-d, 1]])
    return np.stack([x[:, 0], r], axis=1)


def _stereo_enhance(x, amount):
    """extrastereo-style side gain: amount -100 (mono-ish) .. +100 (wide)."""
    if x.shape[1] < 2 or amount == 0:
        return x
    return _stereo_width(x, 1.0 + min(max(amount, -100.0), 100.0) / 100.0)


def _channel_mode(x, mode, swap_lr):
    y = x
    if swap_lr and y.shape[1] >= 2:
        y = y[:, ::-1].copy()
    if mode == 'Mono' and y.shape[1] >= 2:
        m = y.mean(axis=1)
        y = np.stack([m, m], axis=1)
    elif mode == 'Left' and y.shape[1] >= 2:
        y = np.stack([y[:, 0], y[:, 0]], axis=1)
    elif mode == 'Right' and y.shape[1] >= 2:
        y = np.stack([y[:, 1], y[:, 1]], axis=1)
    return y.astype(np.float32)


# ─── S238: voice/recitation tools ──────────────────────────────────────────

def _dehum(x, sr, base_hz, strength):
    """Mains-hum remover: narrow IIR notches at the base frequency (50 or
    60 Hz) and its first four harmonics. Strength widens the notches."""
    if not SCIPY_OK or strength <= 0:
        return x
    depth = min(max(strength, 0.0), 100.0) / 100.0
    q = float(np.interp(depth, [0, 1], [45.0, 22.0]))  # stronger = wider notch
    y = x.astype(np.float64)
    for k in range(1, 6):
        f = base_hz * k
        if f >= sr * 0.45:
            break
        b, a = signal.iirnotch(f / (sr / 2.0), q)
        y = signal.lfilter(b, a, y, axis=0)
    return y.astype(np.float32)


def _vocal_isolate(x, sr, amount):
    """Recitation/voice focus: the voice sits in the stereo center and the
    150 Hz–5 kHz band — attenuate the side channel (ambience, room) and
    gently emphasize the voice band. amount 0..100."""
    if not SCIPY_OK or amount <= 0:
        return x
    a = min(max(amount, 0.0), 100.0) / 100.0
    y = x.astype(np.float64)
    if y.shape[1] >= 2:
        mid = (y[:, 0] + y[:, 1]) * 0.5
        side = (y[:, 0] - y[:, 1]) * 0.5 * (1.0 - 0.85 * a)
        y = np.stack([mid + side, mid - side], axis=1)
    lo = 150.0 / (sr / 2.0)
    hi = min(5000.0, sr * 0.44) / (sr / 2.0)
    sos = signal.butter(2, [lo, hi], btype='band', output='sos')
    band = signal.sosfilt(sos, y, axis=0)
    y = (1.0 - 0.40 * a) * y + 0.55 * a * band
    return y.astype(np.float32)


# ─── S236: FX+ — cleanup & dynamics ────────────────────────────────────────

def _noise_gate(x, sr, threshold_db):
    """Soft downward expander below threshold (smoothed block envelope)."""
    env, block = _block_env(x, sr, 0.005, attack_ms=2.0, release_ms=120.0)
    thr = 10 ** (min(max(threshold_db, -80.0), -10.0) / 20.0)
    ratio = (env / (thr + 1e-12)) ** 2
    gain_b = np.clip(ratio, 0.0, 1.0)
    gain_b[env >= thr] = 1.0
    gain = _expand_gain(gain_b, block, x.shape[0])
    return (x * gain[:, None]).astype(np.float32)


def _deesser(x, sr, amount):
    """Split-band sibilance tamer: compress only the 4.5–9.5 kHz band."""
    if not SCIPY_OK or amount <= 0:
        return x
    strength = min(max(amount, 0.0), 100.0) / 100.0
    hi_edge = min(9500.0, sr * 0.45)
    sos = signal.butter(4, [4500.0 / (sr / 2.0), hi_edge / (sr / 2.0)],
                        btype='band', output='sos')
    band = signal.sosfilt(sos, x.astype(np.float64), axis=0)
    rest = x.astype(np.float64) - band
    env, block = _block_env(band.astype(np.float32), sr, 0.002,
                            attack_ms=1.0, release_ms=60.0)
    active = env[env > 1e-5]
    thr = np.percentile(active, 60) if active.size else 1.0
    gain_b = np.ones_like(env)
    over = env > thr
    gain_b[over] = (thr / (env[over] + 1e-12)) ** strength
    gain = _expand_gain(gain_b, block, x.shape[0])
    return (rest + band * gain[:, None]).astype(np.float32)


def _declip(x, sr):
    """Reconstructs clipped runs (|x| ≥ ~0.985) by interpolating from the
    surrounding clean samples — same interp strategy as _declick."""
    y = x.copy()
    idx = np.arange(x.shape[0])
    for ch in range(x.shape[1]):
        sig_ = x[:, ch].astype(np.float64)
        bad = np.abs(sig_) >= 0.985
        good = ~bad
        if np.any(bad) and np.sum(good) > 2:
            sig_[bad] = np.interp(idx[bad], idx[good], sig_[good])
            y[:, ch] = sig_.astype(np.float32)
    return y


def _adaptive_normalize(x, sr, target_rms_db=-16.0):
    """dynaudnorm-lite: frame-wise gain ride toward a target RMS, smoothed so
    it breathes instead of pumping."""
    frame = max(256, int(sr * 0.4))
    hop = frame // 2
    n = x.shape[0]
    if n < frame:
        return x
    mono = x.mean(axis=1).astype(np.float64)
    starts = np.arange(0, n - frame + 1, hop)
    rms = np.array([np.sqrt(np.mean(mono[s:s + frame] ** 2)) + 1e-9 for s in starts])
    target = 10 ** (target_rms_db / 20.0)
    gains = np.clip(target / rms, 0.5, 8.0)
    if len(gains) >= 5:  # gaussian-ish smoothing across frames
        kernel = np.array([0.06, 0.24, 0.4, 0.24, 0.06])
        gains = np.convolve(gains, kernel, mode='same')
    centers = starts + frame // 2
    per_sample = np.interp(np.arange(n), centers, gains)
    return np.clip(x * per_sample[:, None], -1.0, 1.0).astype(np.float32)


def _hard_limiter(x, sr, ceiling_db):
    """Look-ahead-ish limiter: smoothed gain reduction + safety clip."""
    ceiling = 10 ** (min(max(ceiling_db, -12.0), 0.0) / 20.0)
    env, block = _block_env(x, sr, 0.001, attack_ms=0.5, release_ms=50.0)
    gain_b = np.ones_like(env)
    over = env > ceiling
    gain_b[over] = ceiling / (env[over] + 1e-12)
    gain = _expand_gain(gain_b, block, x.shape[0])
    y = x * gain[:, None]
    return np.clip(y, -ceiling, ceiling).astype(np.float32)


def _auto_trim_silence(x, sr, thresh_db=-45.0, pad_s=0.08):
    env = np.abs(x).max(axis=1)
    thr = 10 ** (thresh_db / 20.0)
    above = np.flatnonzero(env > thr)
    if above.size == 0:
        return x
    pad = int(pad_s * sr)
    s = max(0, int(above[0]) - pad)
    e = min(x.shape[0], int(above[-1]) + pad)
    if e - s < int(0.05 * sr):
        return x
    return x[s:e].copy()


# ─── S248/S250: real webrtcvad voice-activity detection ─────────────────────
_VAD_RATES = (8000, 16000, 32000, 48000)
_VAD_FRAME_MS = 30


def _vad_frames(x, sr, aggressiveness):
    """Per-frame speech/no-speech decisions from webrtcvad.
    Returns (voiced list, samples per frame at the ORIGINAL rate) or None.

    S250 FIX: the previous version had two real bugs. (1) When `sr` wasn't one
    of webrtcvad's four supported rates and scipy was missing, it left
    vad_sr = 48000 while handing the untouched sr-rate audio to is_speech() —
    frame lengths, the rate argument, and the index scale-back were all
    computed from a rate the samples weren't at. (2) `range(0, len - fb, fb)`
    drops the final whole frame, so up to 30 ms of trailing speech could be
    cut. Both are fixed here, and resampling now goes through soxr."""
    vad_mod = _mod('webrtcvad')
    if vad_mod is None:
        return None
    try:
        vad = vad_mod.Vad(int(min(max(int(aggressiveness), 0), 3)))
    except Exception:
        return None
    mono = x.mean(axis=1).astype(np.float32)
    if sr in _VAD_RATES:
        vad_sr, mono_r = sr, mono
    else:
        vad_sr = min(_VAD_RATES, key=lambda r: abs(r - sr))
        mono_r = _resample(mono, sr, vad_sr)
        if mono_r is mono:            # no resampler available — can't run VAD
            return None
    frame_len = int(vad_sr * _VAD_FRAME_MS / 1000)
    if frame_len <= 0:
        return None
    pcm16 = (np.clip(mono_r, -1.0, 1.0) * 32767.0).astype('<i2').tobytes()
    frame_bytes = frame_len * 2
    voiced = []
    for i in range(0, len(pcm16) - frame_bytes + 1, frame_bytes):
        try:
            voiced.append(bool(vad.is_speech(pcm16[i:i + frame_bytes], vad_sr)))
        except Exception:
            voiced.append(True)      # fail open — never over-trim
    if not voiced:
        return None
    return voiced, frame_len * (sr / float(vad_sr))


@_stage('vad trim')
def _vad_trim(x, sr, aggressiveness=2, pad_s=0.15):
    """Real speech detection instead of a plain energy threshold — trims
    leading/trailing silence AND non-speech noise the energy gate would miss.
    Falls back to _auto_trim_silence if webrtcvad isn't installed."""
    res = _vad_frames(x, sr, aggressiveness)
    if res is None:
        return _auto_trim_silence(x, sr)
    voiced, frame_samples = res
    if not any(voiced):
        return x
    first = voiced.index(True)
    last = len(voiced) - 1 - voiced[::-1].index(True)
    pad = int(pad_s * sr)
    s = max(0, int(first * frame_samples) - pad)
    e = min(x.shape[0], int((last + 1) * frame_samples) + pad)
    if e - s < int(0.05 * sr):
        return x
    return x[s:e].copy()


@_stage('pause squeeze')
def _vad_squeeze(x, sr, aggressiveness=2, max_pause_s=1.2, keep_s=0.35):
    """S250 — shortens the pauses *inside* a recording instead of only at its
    ends. Any run of non-speech longer than `max_pause_s` is cut down to
    `keep_s`, with a short equal-power crossfade over the join so no click is
    introduced. This is the single biggest time-saver on a long lecture or a
    recitation with page-turn gaps, and unlike a plain silence-removal filter
    it keeps quiet *breath* (webrtcvad still reports voice) rather than
    chopping the reciter's intake."""
    res = _vad_frames(x, sr, aggressiveness)
    if res is None or max_pause_s <= 0:
        return x
    voiced, frame_samples = res
    keep = max(0.05, min(float(keep_s), float(max_pause_s)))
    max_pause_frames = int(max_pause_s * 1000.0 / _VAD_FRAME_MS)
    keep_frames = int(keep * 1000.0 / _VAD_FRAME_MS)
    if max_pause_frames <= keep_frames:
        return x

    # collect [start, end) frame ranges of over-long non-speech runs
    cuts = []
    run = None
    for i, v in enumerate(voiced + [True]):
        if not v and run is None:
            run = i
        elif v and run is not None:
            if i - run > max_pause_frames and run > 0:   # never the leading pause
                half = keep_frames // 2
                cuts.append((run + half, i - (keep_frames - half)))
            run = None
    if not cuts:
        return x

    xfade = min(int(0.012 * sr), int(frame_samples))     # ~12 ms
    fi = np.sin(np.linspace(0.0, 1.0, xfade) * np.pi / 2.0)[:, None] if xfade > 1 else None
    pieces = []
    prev_end = 0
    for a_f, b_f in cuts:
        a = max(prev_end, int(a_f * frame_samples))
        b = min(x.shape[0], int(b_f * frame_samples))
        if b - a < int(0.05 * sr):
            continue
        seg = x[prev_end:a]
        if fi is not None and seg.shape[0] > xfade and b + xfade <= x.shape[0]:
            head = seg[:-xfade]
            tail = seg[-xfade:] * (1.0 - fi) + x[b:b + xfade] * fi
            pieces.append(head)
            pieces.append(tail.astype(np.float32))
            prev_end = b + xfade
        else:
            pieces.append(seg)
            prev_end = b
    pieces.append(x[prev_end:])
    y = np.concatenate([p for p in pieces if p.shape[0] > 0], axis=0)
    if y.shape[0] < int(0.2 * sr):
        return x
    return y.astype(np.float32)


def _pad(x, sr, start_s, end_s):
    parts = []
    if start_s > 0:
        parts.append(np.zeros((int(start_s * sr), x.shape[1]), dtype=x.dtype))
    parts.append(x)
    if end_s > 0:
        parts.append(np.zeros((int(end_s * sr), x.shape[1]), dtype=x.dtype))
    return np.concatenate(parts, axis=0) if len(parts) > 1 else x


# ─── Loudness — real ITU-R BS.1770-4 meter, vendored from pyloudnorm ────────
# S245: pyloudnorm (github.com/csteinmetz1/pyloudnorm, MIT license) is pure
# Python + numpy/scipy — no compiled extension, no extra pip install needed
# on-device — so its actual algorithm is inlined here directly rather than
# the hand-rolled approximation this file used before (single absolute-
# threshold gate, no relative gate, no proper K-weighting shelf/high-pass
# pair). This IS the real ITU-R BS.1770-4 two-stage gated measurement:
# K-weighting (high-shelf + high-pass) → 400ms blocks, 75% overlap →
# absolute gate (-70 LUFS) → relative gate (measured mean - 10 LU) → final
# integrated loudness. Loudness Range (LRA) follows EBU Tech 3342.

def _k_weight_coeffs(sr):
    """RBJ high-shelf (+4dB @ 1500Hz) cascaded with a high-pass (38Hz) —
    the two K-weighting stages from ITU-R BS.1770-4 Annex 1."""
    def high_shelf(g_db, q, fc, sr):
        a = 10 ** (g_db / 40.0)
        w0 = 2 * np.pi * fc / sr
        alpha = np.sin(w0) / (2.0 * q)
        cosw0 = np.cos(w0)
        b0 = a * ((a + 1) + (a - 1) * cosw0 + 2 * np.sqrt(a) * alpha)
        b1 = -2 * a * ((a - 1) + (a + 1) * cosw0)
        b2 = a * ((a + 1) + (a - 1) * cosw0 - 2 * np.sqrt(a) * alpha)
        a0 = (a + 1) - (a - 1) * cosw0 + 2 * np.sqrt(a) * alpha
        a1 = 2 * ((a - 1) - (a + 1) * cosw0)
        a2 = (a + 1) - (a - 1) * cosw0 - 2 * np.sqrt(a) * alpha
        return np.array([b0, b1, b2]) / a0, np.array([a0, a1, a2]) / a0

    def high_pass(q, fc, sr):
        w0 = 2 * np.pi * fc / sr
        alpha = np.sin(w0) / (2.0 * q)
        cosw0 = np.cos(w0)
        b0 = (1 + cosw0) / 2
        b1 = -(1 + cosw0)
        b2 = (1 + cosw0) / 2
        a0 = 1 + alpha
        a1 = -2 * cosw0
        a2 = 1 - alpha
        return np.array([b0, b1, b2]) / a0, np.array([a0, a1, a2]) / a0

    b1, a1 = high_shelf(4.0, 1 / np.sqrt(2), 1500.0, sr)
    b2, a2 = high_pass(0.5, 38.0, sr)
    return (b1, a1), (b2, a2)


def _k_weight(x, sr):
    (b1, a1), (b2, a2) = _k_weight_coeffs(sr)
    y = signal.lfilter(b1, a1, x, axis=0)
    y = signal.lfilter(b2, a2, y, axis=0)
    return y


# channel gains per ITU-R BS.1770-4 (L, R, C, Ls, Rs) — this app is always
# stereo (L, R), so only the first two are ever used.
_CH_GAIN = [1.0, 1.0, 1.0, 1.41, 1.41]


def _block_powers(x, sr, block_s, overlap):
    """Per-block, per-channel weighted mean-square power (eq. 1 of BS.1770-4),
    then combined across channels per block (the "l_j" gating loudness)."""
    n = x.shape[0]
    ch = x.shape[1]
    step = 1.0 - overlap
    hop = max(1, int(block_s * sr * step))
    block = max(1, int(block_s * sr))
    if n < block:
        return np.array([]), np.zeros((ch, 0))
    starts = np.arange(0, n - block + 1, hop)
    z = np.zeros((ch, len(starts)))
    for c in range(ch):
        for j, s in enumerate(starts):
            z[c, j] = np.mean(x[s:s + block, c] ** 2)
    with np.errstate(divide='ignore'):
        l_j = -0.691 + 10.0 * np.log10(
            np.sum([_CH_GAIN[c] * z[c] for c in range(ch)], axis=0))
    return l_j, z


def _integrated_loudness(x, sr):
    """Real ITU-R BS.1770-4 gated integrated loudness.

    S250: when the pyloudnorm package itself is installed (S247 embeds it) we
    call its Meter directly — same algorithm, but maintained upstream and
    exercised by its own test suite. The vendored implementation below stays
    as the fallback for older python-env.tar.gz bundles, and the two agree to
    within rounding."""
    pyln = _mod('pyloudnorm')
    if pyln is not None:
        try:
            meter = pyln.Meter(int(sr))
            val = float(meter.integrated_loudness(np.asarray(x, dtype=np.float64)))
            if np.isfinite(val):
                return val
        except Exception:
            pass
    if not SCIPY_OK:
        return -23.0
    kw = _k_weight(x, sr)
    l_j, z = _block_powers(kw, sr, block_s=0.4, overlap=0.75)
    if l_j.size == 0:
        return float(-0.691 + 10 * np.log10(np.mean(kw ** 2) + 1e-12))
    ch = z.shape[0]
    with np.errstate(invalid='ignore'):
        abs_gated = l_j >= -70.0
        if not np.any(abs_gated):
            return -70.0
        z_avg = np.array([np.mean(z[c, abs_gated]) for c in range(ch)])
        gamma_r = -0.691 + 10.0 * np.log10(
            np.sum([_CH_GAIN[c] * z_avg[c] for c in range(ch)])) - 10.0
        rel_gated = abs_gated & (l_j > gamma_r)
        if not np.any(rel_gated):
            rel_gated = abs_gated
        z_avg = np.nan_to_num(np.array([np.mean(z[c, rel_gated]) for c in range(ch)]))
    with np.errstate(divide='ignore'):
        lufs = -0.691 + 10.0 * np.log10(np.sum([_CH_GAIN[c] * z_avg[c] for c in range(ch)]))
    return float(lufs)


def _loudness_range(x, sr):
    """EBU Tech 3342 Loudness Range (LRA) in LU — 3s blocks / 97% overlap,
    absolute gate -70 LUFS, relative gate (median - 20 LU), 10th-95th
    percentile spread. Returns None if the signal is too short/quiet."""
    if not SCIPY_OK:
        return None
    try:
        pad = np.zeros((int(1.5 * sr), x.shape[1]), dtype=x.dtype)
        kw = _k_weight(np.concatenate([x, pad], axis=0), sr)
        l_j, _ = _block_powers(kw, sr, block_s=3.0, overlap=0.97)
        if l_j.size == 0:
            return None
        abs_gated = l_j[l_j >= -70.0]
        if abs_gated.size == 0:
            return None
        n = len(abs_gated)
        power = np.sum(10 ** (abs_gated / 10.0)) / n
        integrated = 10 * np.log10(power)
        rel_gated = abs_gated[abs_gated >= integrated - 20.0]
        if rel_gated.size == 0:
            return None
        lo, hi = np.percentile(rel_gated, [10, 95])
        return float(hi - lo)
    except Exception:
        return None


def _true_peak_limit(x, sr, ceiling_db):
    ceiling = 10 ** (ceiling_db / 20.0)
    up = signal.resample_poly(x, 4, 1, axis=0)
    peak = np.max(np.abs(up)) + 1e-9
    y = x
    if peak > ceiling:
        y = x * (ceiling / peak)
    # soft-clip safety net for any residual overs
    return np.tanh(y / ceiling) * ceiling


def _true_peak_db(x, sr):
    """4x-oversampled true-peak estimate (dBTP), for reporting only."""
    if not SCIPY_OK:
        return float(20 * np.log10(np.max(np.abs(x)) + 1e-9))
    up = signal.resample_poly(x, 4, 1, axis=0)
    return float(20 * np.log10(np.max(np.abs(up)) + 1e-9))


def _loudness_normalize(x, sr, target_lufs, true_peak_db, limiter):
    if not SCIPY_OK or target_lufs is None:
        return x
    cur = _integrated_loudness(x, sr)
    gain_db = float(np.clip(target_lufs - cur, -24.0, 24.0))
    y = x * (10 ** (gain_db / 20.0))
    if limiter:
        y = _true_peak_limit(y, sr, true_peak_db)
    return y.astype(np.float32)


# ─── Fades — proper envelope curves (equal-power by default) ───────────────

def _fade_env(t, curve):
    if curve == 'Linear':
        return t
    if curve == 'Exponential':
        return t ** 2
    return np.sin(t * np.pi / 2.0)  # Equal Power (default) — perceptually smoother


def _apply_fades(x, sr, fade_in_s, fade_out_s, curve):
    n = x.shape[0]
    y = x.copy()
    if fade_in_s > 0:
        ni = min(n, int(fade_in_s * sr))
        if ni > 1:
            t = np.linspace(0.0, 1.0, ni)
            y[:ni] *= _fade_env(t, curve)[:, None]
    if fade_out_s > 0:
        no_ = min(n, int(fade_out_s * sr))
        if no_ > 1:
            t = np.linspace(1.0, 0.0, no_)
            y[n - no_:] *= _fade_env(t, curve)[:, None]
    return y


# ─── S236: ANALYSIS MODE — real waveform / spectrum / loudness for the UI ──

_ANALYZE_SR = 22050        # plenty for visuals + stats, keeps decode fast
_ANALYSIS_CACHE_V = 3      # bump whenever the payload shape changes
_WAVE_BUCKETS = 96         # bars drawn by the Flutter waveform
_SPEC_BANDS = 30           # log-spaced spectrum bands (60 Hz .. 10 kHz)


# ─── S250: analysis cache (pooch hashing + msgpack storage) ─────────────────
# Re-opening a file you already analysed (very common: pick file → edit →
# export → pick it again) used to re-run the whole numpy pass. The cache key
# is pooch's content hash, so it survives renames/copies — _safeInput() copies
# every input to a fresh temp name, which is exactly the case a path-based key
# would miss. msgpack keeps the store compact (the payload is ~200 floats per
# entry) and, unlike JSON, round-trips floats without reformatting them.

def _cache_path() -> str:
    base = os.environ.get('TMPDIR') or '/tmp'
    return os.path.join(base, 'tilawa_analysis_cache.msgpack')


def _content_key(path: str):
    p = _mod('pooch')
    try:
        if p is not None:
            return 'sha256:' + p.file_hash(path, alg='sha256')
    except Exception:
        pass
    try:                              # cheap fallback key
        st = os.stat(path)
        return f'stat:{st.st_size}:{int(st.st_mtime)}'
    except Exception:
        return None


def _cache_load(key):
    mp = _mod('msgpack')
    if mp is None or key is None:
        return None
    try:
        with open(_cache_path(), 'rb') as fh:
            store = mp.unpackb(fh.read(), raw=False, strict_map_key=False)
        entry = store.get(key)
        if isinstance(entry, dict) and entry.get('_v') == _ANALYSIS_CACHE_V:
            entry = dict(entry)
            entry.pop('_v', None)
            return entry
    except Exception:
        pass
    return None


def _cache_store(key, payload):
    mp = _mod('msgpack')
    if mp is None or key is None:
        return
    try:
        store = {}
        try:
            with open(_cache_path(), 'rb') as fh:
                store = mp.unpackb(fh.read(), raw=False, strict_map_key=False) or {}
        except Exception:
            store = {}
        if len(store) > 40:           # keep the file small — drop oldest half
            store = dict(list(store.items())[-20:])
        entry = dict(payload)
        entry['_v'] = _ANALYSIS_CACHE_V
        store[key] = entry
        tmp = _cache_path() + '.tmp'
        with open(tmp, 'wb') as fh:
            fh.write(mp.packb(store, use_bin_type=True))
        os.replace(tmp, _cache_path())
    except Exception:
        pass


# ─── S250: content insights (native DSP + webrtcvad) ───────────────────────

_NOTE_NAMES = ['C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B']


def _note_for_hz(hz):
    if not hz or hz <= 0:
        return None
    midi = 69 + 12 * np.log2(hz / 440.0)
    i = int(round(midi))
    return f'{_NOTE_NAMES[i % 12]}{i // 12 - 1}'


def _voice_insights(x, sr, mono):
    """Content-aware numbers the UI turns into actionable suggestions:
    median vocal pitch, brightness, phrase-onset rate, how much of the file is
    actually speech, and how many over-long internal pauses it has."""
    out = {}
    y = np.ascontiguousarray(mono, dtype=np.float64)
    try:
        f0 = _f0_median(y, sr)
        if f0:
            out['f0_hz'] = round(f0, 1)
            out['note'] = _note_for_hz(f0)
    except Exception:
        pass
    try:
        cent = _spectral_centroid(y, sr)
        if cent:
            out['brightness_hz'] = round(cent, 0)
    except Exception:
        pass
    try:
        rate = _onset_rate(y, sr)
        if rate is not None:
            out['onsets_per_min'] = round(rate, 1)
    except Exception:
        pass
    res = _vad_frames(x, sr, 2)
    if res is not None:
        voiced, frame_samples = res
        try:
            out['speech_pct'] = round(100.0 * sum(voiced) / float(len(voiced)), 1)
            long_pauses, run = 0, None
            for i, v in enumerate(voiced + [True]):
                if not v and run is None:
                    run = i
                elif v and run is not None:
                    if (i - run) * _VAD_FRAME_MS >= 1200 and run > 0:
                        long_pauses += 1
                    run = None
            out['long_pauses'] = long_pauses
        except Exception:
            pass
    if x.shape[1] >= 2:
        try:
            l, r = x[:, 0].astype(np.float64), x[:, 1].astype(np.float64)
            denom = float(np.std(l) * np.std(r))
            if denom > 1e-12:
                out['stereo_corr'] = round(float(np.mean((l - l.mean()) * (r - r.mean())) / denom), 3)
        except Exception:
            pass
    try:
        out['dc_offset'] = round(float(np.mean(mono)), 5)
    except Exception:
        pass
    return out


def analyze(in_path: str, out_json: str) -> int:
    key = _content_key(in_path)
    cached = _cache_load(key)
    if cached is not None:
        try:
            with open(out_json, 'w', encoding='utf-8') as fh:
                json.dump(cached, fh)
            print(json.dumps({'ok': True, 'cached': True, 'scipy': SCIPY_OK}))
            return 0
        except Exception:
            pass
    x = _decode(in_path, _ANALYZE_SR, 0.0, 0.0)
    if x is None or x.shape[0] == 0:
        print(json.dumps({'ok': False, 'error': 'decode failed (ffmpeg/soundfile/audioread)'}))
        return 1
    try:
        n = x.shape[0]
        duration = n / float(_ANALYZE_SR)
        mono = x.mean(axis=1).astype(np.float64)

        # Waveform buckets — true peak + RMS per bucket, display-normalized.
        nb = _WAVE_BUCKETS
        edges = np.linspace(0, n, nb + 1).astype(int)
        peaks = np.zeros(nb)
        rms = np.zeros(nb)
        for i in range(nb):
            seg = mono[edges[i]:max(edges[i] + 1, edges[i + 1])]
            peaks[i] = np.max(np.abs(seg)) if seg.size else 0.0
            rms[i] = np.sqrt(np.mean(seg ** 2)) if seg.size else 0.0
        norm = max(float(peaks.max()), 1e-6)
        peaks_n = np.clip(peaks / norm, 0.0, 1.0)
        rms_n = np.clip(rms / norm, 0.0, 1.0)

        # Level stats (true dBFS, pre-normalization).
        peak_db = float(20 * np.log10(np.max(np.abs(mono)) + 1e-9))
        rms_db = float(20 * np.log10(np.sqrt(np.mean(mono ** 2)) + 1e-9))
        clip_pct = float(100.0 * np.mean(np.abs(mono) >= 0.985))
        # S245: real ITU-R BS.1770-4 integrated loudness + EBU Tech 3342
        # Loudness Range (vendored pyloudnorm algorithm — see above),
        # replacing the old single-gate approximation.
        lufs = None
        lra = None
        true_peak = None
        if SCIPY_OK:
            try:
                lufs = round(_integrated_loudness(x.astype(np.float64), _ANALYZE_SR), 1)
            except Exception:
                lufs = None
            try:
                lra = _loudness_range(x.astype(np.float64), _ANALYZE_SR)
                lra = round(lra, 1) if lra is not None else None
            except Exception:
                lra = None
            try:
                true_peak = round(_true_peak_db(x.astype(np.float64), _ANALYZE_SR), 1)
            except Exception:
                true_peak = None

        # Average spectrum — log-spaced bands, normalized 0..1 over a 60 dB range.
        spectrum = []
        if SCIPY_OK and n > 4096:
            try:
                f, pxx = signal.welch(mono, fs=_ANALYZE_SR, nperseg=4096)
                band_edges = np.geomspace(60.0, min(10000.0, _ANALYZE_SR * 0.45),
                                          _SPEC_BANDS + 1)
                p_db = 10 * np.log10(pxx + 1e-14)
                top = float(p_db.max())
                for i in range(_SPEC_BANDS):
                    m = (f >= band_edges[i]) & (f < band_edges[i + 1])
                    v = float(p_db[m].mean()) if np.any(m) else -120.0
                    spectrum.append(round(float(np.clip((v - top + 60.0) / 60.0, 0.0, 1.0)), 3))
            except Exception:
                spectrum = []

        payload = {
            'ok': True,
            'duration_sec': round(duration, 3),
            'peaks': [round(float(v), 3) for v in peaks_n],
            'rms': [round(float(v), 3) for v in rms_n],
            'spectrum': spectrum,
            'peak_db': round(peak_db, 1),
            'rms_db': round(rms_db, 1),
            'lufs': lufs,
            'lra': lra,
            'true_peak_db': true_peak,
            'clip_pct': round(clip_pct, 2),
            'scipy': SCIPY_OK,
        }
        payload.update(_voice_insights(x, _ANALYZE_SR, mono))   # S250
        with open(out_json, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        _cache_store(key, payload)                              # S250
        print(json.dumps({'ok': True, 'scipy': SCIPY_OK}))
        return 0
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'analysis failed: {e}'}))
        return 1


# ─── S238: SPLIT-BY-SILENCE — cut a recitation into pieces at the pauses ────
# python3 tilawa_dsp_studio.py --split <in> <out_base> <params.json>
# Writes <out_base>_001.<ext>, _002… and a <out_base>_report.json listing them.
# Perfect for splitting a long recitation into ayah-sized files: cuts are
# placed in the middle of each detected pause, and each piece keeps ~120 ms
# of breathing room on both sides.

def split_mode(in_path: str, out_base: str, params_path: str) -> int:
    try:
        with open(params_path, 'r', encoding='utf-8') as fh:
            p = json.load(fh)
    except Exception:
        p = {}
    sr = 32000  # decode rate for detection + output resampled by ffmpeg anyway
    thresh_db = float(p.get('silence_db', -40.0))
    min_sil = float(p.get('min_silence_s', 0.6))
    min_seg = float(p.get('min_seg_s', 1.0))
    out_cfg = p.get('output', {}) or {}
    fmt = str(out_cfg.get('format', 'MP3')).upper()
    ext = {'MP3': 'mp3', 'WAV': 'wav', 'M4A': 'm4a'}.get(fmt, 'mp3')

    x = _decode(in_path, sr, 0.0, 0.0)
    if x is None or x.shape[0] == 0:
        print(json.dumps({'ok': False, 'error': 'ffmpeg decode failed'}))
        return 1
    try:
        n = x.shape[0]
        env = np.abs(x).max(axis=1)
        # ~20 ms smoothing so consonant gaps don't read as pauses
        win = max(1, int(0.02 * sr))
        env = np.convolve(env, np.ones(win) / win, mode='same')
        thr = 10 ** (thresh_db / 20.0)
        silent = env < thr

        # find silent runs long enough to count as a pause; cut at run centers
        cuts = []
        run_start = None
        for i in range(n + 1):
            is_sil = silent[i] if i < n else False
            if is_sil and run_start is None:
                run_start = i
            elif not is_sil and run_start is not None:
                if i - run_start >= int(min_sil * sr):
                    cuts.append((run_start + i) // 2)
                run_start = None

        bounds = [0] + cuts + [n]
        pad = int(0.12 * sr)
        segments = []
        for a, b in zip(bounds[:-1], bounds[1:]):
            aa = max(0, a - (pad if a > 0 else 0))
            bb = min(n, b + (pad if b < n else 0))
            seg = x[aa:bb]
            if bb - aa < int(min_seg * sr):
                continue
            if float(np.max(np.abs(seg))) < thr:  # pure silence — drop
                continue
            segments.append((aa, bb))

        if not segments:
            print(json.dumps({'ok': False, 'error': 'no segments found — lower the silence threshold'}))
            return 1

        files = []
        for i, (a, b) in enumerate(segments, start=1):
            out_path = f'{out_base}_{i:03d}.{ext}'
            if _encode(x[a:b].copy(), sr, out_path, out_cfg):
                files.append({'path': out_path,
                              'start_sec': round(a / sr, 2),
                              'dur_sec': round((b - a) / sr, 2)})
        report = {'ok': len(files) > 0, 'count': len(files), 'files': files}
        with open(f'{out_base}_report.json', 'w', encoding='utf-8') as fh:
            json.dump(report, fh)
        print(json.dumps({'ok': len(files) > 0, 'count': len(files)}))
        return 0 if files else 1
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'split failed: {e}'}))
        return 1


# ─── Main pipeline ───────────────────────────────────────────────────────────

# ─── S248: pystoi intelligibility score (bundled via S247) ──────────────────
_QUALITY_SR = 16000  # pystoi's standard analysis rate

def quality_check(orig_path: str, proc_path: str, out_json: str) -> int:
    """Compares original vs. processed audio with the STOI metric — an
    objective measure of speech intelligibility (0..1), not loudness.
    Writes JSON to out_json (same convention as analyze()) and returns 0/1.

    S250: also reports ESTOI (extended STOI), which unlike plain STOI is
    sensitive to *modulation*-domain damage — exactly the artefact aggressive
    spectral denoising leaves behind — plus the loudness delta, so the score
    can't be misread as "it just got quieter". Length mismatch is reported
    instead of silently comparing misaligned audio."""
    result = {'ok': False}
    ps = _mod('pystoi')
    if ps is None:
        result['error'] = 'pystoi not installed in this python environment'
        with open(out_json, 'w', encoding='utf-8') as fh:
            json.dump(result, fh)
        return 1
    try:
        stoi = ps.stoi
        sr = _QUALITY_SR
        a = _decode(orig_path, sr, 0.0, 0.0)
        b = _decode(proc_path, sr, 0.0, 0.0)
        if a is None or b is None or a.shape[0] == 0 or b.shape[0] == 0:
            raise RuntimeError('decode failed for one or both files')
        am = a.mean(axis=1).astype(np.float64)
        bm = b.mean(axis=1).astype(np.float64)
        n = min(len(am), len(bm))
        if n < sr // 2:
            raise RuntimeError('audio too short to score (need at least 0.5s)')
        drift = abs(len(am) - len(bm)) / float(sr)
        result['ok'] = True
        result['stoi'] = round(float(stoi(am[:n], bm[:n], sr, extended=False)), 4)
        try:
            result['estoi'] = round(float(stoi(am[:n], bm[:n], sr, extended=True)), 4)
        except Exception:
            result['estoi'] = None
        result['sr'] = sr
        result['compared_sec'] = round(n / sr, 2)
        result['length_drift_sec'] = round(drift, 2)
        try:
            result['lufs_delta'] = round(
                _integrated_loudness(bm[:n, None].repeat(2, axis=1), sr)
                - _integrated_loudness(am[:n, None].repeat(2, axis=1), sr), 1)
        except Exception:
            result['lufs_delta'] = None
    except Exception as e:
        result['error'] = str(e)
    with open(out_json, 'w', encoding='utf-8') as fh:
        json.dump(result, fh)
    return 0 if result.get('ok') else 1


def _count_stages(p: dict, fx: dict) -> int:
    """How many @_stage-wrapped stages this run will actually execute — tqdm
    needs a total for the percentage to mean anything. Only the expensive,
    conditional stages are counted (the cheap unconditional ones are folded
    into the +2 the caller adds for decode/encode)."""
    vad_cfg = fx.get('vad_trim', {}) or {}
    flags = [
        bool(vad_cfg.get('enabled')),
        bool((fx.get('pause_squeeze', {}) or {}).get('enabled')),
        float((fx.get('dereverb', {}) or {}).get('strength', 0) or 0) > 0,
        bool((fx.get('ai_denoise', {}) or {}).get('enabled')),
        float(fx.get('harmonic_focus', 0) or 0) > 0,
        abs(float(p.get('pitch_semitones', 0) or 0)) > 1e-3,
        abs(float(p.get('tempo', 1.0) or 1.0) - 1.0) > 1e-3,
    ]
    return max(1, sum(1 for f in flags if f))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--split':
        if len(sys.argv) < 5:
            print(json.dumps({'ok': False,
                              'error': 'usage: tilawa_dsp_studio.py --split <in> <out_base> <params.json>'}))
            return 1
        return split_mode(sys.argv[2], sys.argv[3], sys.argv[4])

    if len(sys.argv) >= 2 and sys.argv[1] == '--analyze':
        if len(sys.argv) < 4:
            print(json.dumps({'ok': False,
                              'error': 'usage: tilawa_dsp_studio.py --analyze <in> <out.json>'}))
            return 1
        return analyze(sys.argv[2], sys.argv[3])

    if len(sys.argv) >= 2 and sys.argv[1] == '--quality':
        if len(sys.argv) < 5:
            print(json.dumps({'ok': False,
                              'error': 'usage: tilawa_dsp_studio.py --quality <original> <processed> <out.json>'}))
            return 1
        return quality_check(sys.argv[2], sys.argv[3], sys.argv[4])

    # S250 — package availability report for the Studio tab
    if len(sys.argv) >= 2 and sys.argv[1] == '--libs':
        return libs_report(sys.argv[2] if len(sys.argv) >= 3 else '')

    if len(sys.argv) < 4:
        print(json.dumps({'ok': False, 'error': 'usage: tilawa_dsp_studio.py <in> <out> <params.json>'}))
        return 1

    in_path, out_path, params_path = sys.argv[1], sys.argv[2], sys.argv[3]
    try:
        with open(params_path, 'r', encoding='utf-8') as fh:
            p = json.load(fh)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'bad params json: {e}'}))
        return 1

    sr = int(p.get('sr', 48000))
    start = float(p.get('trim_start', 0.0))
    dur = float(p.get('trim_dur', 0.0))

    fx = p.get('fx2', {}) or {}

    # S250 — live progress for the UI. The Dart side passes a path it then
    # polls while this blocking proot call runs; `_count_stages` gives tqdm a
    # real total so the percentage means something.
    _PROGRESS.start(_count_stages(p, fx) + 2, str(p.get('progress_path', '') or ''))

    t_start = time.time()
    x = _decode(in_path, sr, start, dur)
    _PROGRESS.tick('decode')
    if x is None or x.shape[0] == 0:
        print(json.dumps({'ok': False, 'error': 'decode failed (ffmpeg/soundfile/audioread)'}))
        return 1

    try:
        if p.get('reverse'):
            x = x[::-1].copy()

        # ── cleanup first: silence trim, declip, declick, gate ──
        vad_cfg = fx.get('vad_trim', {}) or {}
        if vad_cfg.get('enabled'):
            # S248 — real webrtcvad trim takes priority over the plain
            # energy-threshold auto-trim below
            x = _vad_trim(x, sr, int(vad_cfg.get('aggressiveness', 2)))
        elif fx.get('auto_trim_silence'):
            x = _auto_trim_silence(x, sr)

        # S250 — squeeze over-long pauses inside the recording
        sq = fx.get('pause_squeeze', {}) or {}
        if sq.get('enabled'):
            x = _vad_squeeze(x, sr,
                             int(vad_cfg.get('aggressiveness', 2)),
                             float(sq.get('max_pause_s', 1.2)),
                             float(sq.get('keep_s', 0.35)))

        if fx.get('declip'):
            x = _declip(x, sr)

        dc = p.get('declick', {}) or {}
        if dc.get('enabled'):
            x = _declick(x, sr, float(dc.get('sensitivity', 50)))

        gate = fx.get('noise_gate', {}) or {}
        if gate.get('enabled'):
            x = _noise_gate(x, sr, float(gate.get('threshold_db', -50)))

        # S238 — mains-hum removal early, before any spectral shaping
        hum = fx.get('dehum', {}) or {}
        if hum.get('enabled'):
            x = _dehum(x, sr, float(hum.get('base_hz', 50)),
                       float(hum.get('strength', 60)))

        # S250 — WPE dereverb belongs here: after impulsive-noise repair (so
        # clicks don't pollute the prediction) but before any EQ/denoise, since
        # both of those change the spectral statistics WPE estimates from.
        drv = fx.get('dereverb', {}) or {}
        if float(drv.get('strength', 0) or 0) > 0:
            x = _dereverb(x, sr, float(drv.get('strength', 0)),
                          int(drv.get('taps', 10)), int(drv.get('delay', 3)))

        # ── spectral shaping ──
        x = _apply_eq(x, sr, p.get('eq_freqs', []), p.get('eq_gains', []),
                      float(p.get('eq_q', 1.4)))

        nr = float((p.get('noise_reduction', {}) or {}).get('strength', 0))
        if nr > 0:
            x = _spectral_denoise(x, sr, nr)

        # S248 — real noisereduce (separate toggle, can stack with the gate above)
        ai_dn = fx.get('ai_denoise', {}) or {}
        if ai_dn.get('enabled'):
            x = _ai_denoise(x, sr, float(ai_dn.get('strength', 60)),
                            not bool(ai_dn.get('non_stationary', False)))  # S250

        # S250 — HPSS: pull down transient (percussive) noise
        if float(fx.get('harmonic_focus', 0) or 0) > 0:
            x = _harmonic_focus(x, sr, float(fx.get('harmonic_focus', 0)))

        x = _hp_lp(x, sr, float(fx.get('highpass_hz', 0) or 0),
                   float(fx.get('lowpass_hz', 20000) or 20000))

        x = _tone_shelves(x, sr, float(fx.get('bass_db', 0) or 0),
                          float(fx.get('treble_db', 0) or 0))

        if float(fx.get('sub_bass', 0) or 0) > 0:
            x = _sub_bass(x, sr, float(fx.get('sub_bass', 0)))

        if float(fx.get('presence', 0) or 0) > 0:
            x = _presence(x, sr, float(fx.get('presence', 0)))

        # S238 — voice/recitation focus
        if float(fx.get('vocal_isolate', 0) or 0) > 0:
            x = _vocal_isolate(x, sr, float(fx.get('vocal_isolate', 0)))

        # ── space ──
        echo_mix = float((p.get('echo', {}) or {}).get('mix', 0))
        if echo_mix > 0:
            x = _echo(x, sr, echo_mix)

        rv = p.get('reverb', {}) or {}
        if float(rv.get('mix', 0)) > 0:
            x = _reverb(x, sr, float(rv.get('mix', 0)), rv.get('type', 'Room'))

        # ── dynamics (main compressor) ──
        comp = p.get('compressor', {}) or {}
        if comp.get('enabled'):
            x = _compressor(x, sr, float(comp.get('threshold_db', -18)),
                             float(comp.get('ratio', 4)),
                             float(comp.get('attack_ms', 20)),
                             float(comp.get('release_ms', 200)),
                             float(comp.get('makeup_db', 0)))

        # ── pitch / tempo ──
        pitch = float(p.get('pitch_semitones', 0))
        if abs(pitch) > 1e-3:
            x = _pitch_shift(x, sr, pitch)

        tempo = float(p.get('tempo', 1.0))
        if abs(tempo - 1.0) > 1e-3:
            x = _time_stretch(x, sr, tempo)

        # ── character FX ──
        if float(fx.get('tremolo', 0) or 0) > 0:
            x = _tremolo(x, sr, float(fx.get('tremolo', 0)))
        if float(fx.get('vibrato', 0) or 0) > 0:
            x = _vibrato(x, sr, float(fx.get('vibrato', 0)))
        if fx.get('chorus'):
            x = _chorus(x, sr)
        if fx.get('flanger'):
            x = _flanger(x, sr)
        if fx.get('phaser'):
            x = _phaser(x, sr)
        if float(fx.get('bitcrush', 0) or 0) > 0:
            x = _bitcrush(x, float(fx.get('bitcrush', 0)))

        # ── stereo & space ──
        x = _stereo_width(x, float(p.get('stereo_width', 1.0)))
        if fx.get('haas_widen'):
            x = _haas(x, sr)
        if float(fx.get('stereo_fx', 0) or 0) != 0:
            x = _stereo_enhance(x, float(fx.get('stereo_fx', 0)))
        x = _channel_mode(x, str(fx.get('channel_mode', 'Stereo')),
                          bool(fx.get('swap_lr', False)))

        # ── final cleanup & dynamics ──
        if float(fx.get('deesser', 0) or 0) > 0:
            x = _deesser(x, sr, float(fx.get('deesser', 0)))
        if fx.get('adaptive_normalize'):
            x = _adaptive_normalize(x, sr)
        lim = fx.get('limiter', {}) or {}
        if lim.get('enabled'):
            x = _hard_limiter(x, sr, float(lim.get('ceiling_db', -1.0)))

        vol = float(p.get('volume', 1.0))
        if abs(vol - 1.0) > 1e-3:
            x = x * vol

        loud = p.get('loudness', {}) or {}
        target = loud.get('target_lufs')
        if target is not None:
            x = _loudness_normalize(x, sr, float(target),
                                     float(loud.get('true_peak_limit_db', -1.0)),
                                     bool(loud.get('limiter', True)))

        x = _apply_fades(x, sr, float(p.get('fade_in', 0)), float(p.get('fade_out', 0)),
                          p.get('fade_curve', 'Equal Power'))

        x = _pad(x, sr, float(fx.get('pad_start_sec', 0) or 0),
                 float(fx.get('pad_end_sec', 0) or 0))

        x = np.clip(x, -1.0, 1.0).astype(np.float32)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'dsp stage failed: {e}'}))
        return 1

    ok = _encode(x, sr, out_path, p.get('output', {}) or {})
    _PROGRESS.tick('encode')
    _PROGRESS.done()

    # S250 — sidecar run report: which packages were live, what each stage
    # cost. The app shows this in the Studio tab so a slow export is
    # diagnosable instead of just "it took a while".
    report = {
        'ok': ok,
        'scipy': SCIPY_OK,
        'total_ms': round((time.time() - t_start) * 1000.0, 1),
        'stages': [{'name': n, 'ms': ms} for n, ms in _STAGE_MS],
        'libs': {k: bool(v) for k, v in _HAVE.items()},
        'out_sec': round(x.shape[0] / float(sr), 3),
    }
    try:
        with open(out_path + '.report.json', 'w', encoding='utf-8') as fh:
            json.dump(report, fh)
    except Exception:
        pass
    print(json.dumps({'ok': ok, 'scipy': SCIPY_OK,
                      'total_ms': report['total_ms']}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
