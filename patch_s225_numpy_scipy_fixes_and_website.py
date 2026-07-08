#!/usr/bin/env python3
"""
patch_s225_numpy_scipy_fixes_and_website.py — S225

BUGS FOUND (real, currently live in your repo):

  1. NUMPY_OK / _NP_OK falsely coupled to scipy import success.
     In engine_itiqan_v6_official.py, engine_isteidad_v21.py,
     hakim_gen_v2.py, bayan_ve_v2fix.py, idrak_text_v2.py,
     miraat_ref_v2.py, ihyaa_ve.py, and naqaa_v1_tested.py, the
     top-of-file import block does:

         try:
             import numpy as np
             from scipy.fft import rfft, rfftfreq
             NUMPY_OK = True
         except ImportError:
             NUMPY_OK = False

     Every one of these files then gates DOZENS of numpy-only functions
     on `if not NUMPY_OK: return`. Since NUMPY_OK is only set True if
     scipy ALSO imports successfully, any scipy hiccup (partial pip
     install, a dropped .so symlink, apk giving numpy but not scipy,
     a single broken scipy submodule) silently disables the ENTIRE
     numpy-only pipeline in each of these files, even though numpy
     itself imported fine and the vast majority of the gated functions
     never touch scipy at all.

     FIX: numpy is now imported on its own. rfft/rfftfreq/irfft (which
     have exact numpy.fft equivalents) fall back to numpy when scipy.fft
     is missing, so NUMPY_OK-gated code keeps working with numpy alone.
     Where a file's pipeline genuinely needs full scipy (naqaa's 8-phase
     DSP chain), a separate SCIPY_OK flag now gates that specific path
     instead of being folded into NUMPY_OK.

  2. `scipy.signal.lpc` does not exist — scipy has never shipped a
     public `lpc` function. In engine_isteidad_v21.py and ihyaa_ve.py,
     three separate features (IH-2 Formant Enhancement, the MPRM
     Makhraj Pharyngeal Resonance Model, and the J-3 formant resonator)
     did `try: from scipy.signal import lpc ... except ImportError:
     <disable feature>`. That import fails unconditionally on every
     machine regardless of whether scipy is installed, so all three
     features were permanently dead code — silently doing nothing on
     every single run since they were written.

     FIX: replaced with a small pure-numpy LPC implementation
     (autocorrelation + Levinson-Durbin recursion), so these features
     actually run. No scipy dependency needed for LPC at all.

ALSO: adds a link to the project's marketing website
(https://hammer24678-star.github.io/tilawa-enhancer-/) in the in-app
"About" bottom sheet (lib/screens/home_screen.dart), next to the
existing YouTube/Telegram links — it wasn't linked anywhere in the app.

Usage: python3 patch_s225_numpy_scipy_fixes_and_website.py /path/to/tilawa-enhancer
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
STAMP = REPO / '.patch_s225_numpy_scipy_fixes_and_website_done'

if STAMP.exists():
    print('patch_s225 already applied — delete .patch_s225_numpy_scipy_fixes_and_website_done to re-run')
    sys.exit(0)

APPLIED = []
SKIPPED = []
FAILED = []


def apply_fix(rel_path: str, label: str, old: str, new: str, required: bool = True):
    fp = REPO / rel_path
    if not fp.exists():
        msg = f'{rel_path}: FILE NOT FOUND — skipping [{label}]'
        print('  --  ' + msg)
        FAILED.append(msg)
        return
    src = fp.read_text(encoding='utf-8')
    count = src.count(old)
    if count == 0:
        if new in src:
            print(f'  --  {rel_path}: SKIP [{label}] — already applied')
            SKIPPED.append(f'{rel_path}: {label}')
        else:
            msg = f'{rel_path}: anchor text not found for [{label}] — file may have changed, skipping'
            print('  --  ' + msg)
            FAILED.append(msg)
        return
    if count > 1:
        msg = f'{rel_path}: anchor text for [{label}] appears {count} times (expected 1) — skipping to be safe'
        print('  --  ' + msg)
        FAILED.append(msg)
        return
    fp.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK  {rel_path}: applied [{label}]')
    APPLIED.append(f'{rel_path}: {label}')


# ═══════════════════════════════════════════════════════════════════════════
# 1. WEBSITE LINK — lib/screens/home_screen.dart
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(
    'lib/screens/home_screen.dart',
    'website link in About sheet',
    old="""                      const Icon(Icons.open_in_new_rounded,
                        color: Color(0xFF484F58), size: 16),
                    ]))),
                _infoSectionLabel(s.ar ? '🎯 المرجع الصوتي' : '🎯 Reference Standard'),""",
    new="""                      const Icon(Icons.open_in_new_rounded,
                        color: Color(0xFF484F58), size: 16),
                    ]))),
                _infoSectionLabel(s.ar ? '🌐 الموقع الإلكتروني' : '🌐 Website'),
                GestureDetector(
                  onTap: () => launchUrl(
                    Uri.parse('https://hammer24678-star.github.io/tilawa-enhancer-/'),
                    mode: LaunchMode.externalApplication),
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A140A),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: const Color(0xFFD4AF37).withValues(alpha: 0.35))),
                    child: Row(children: [
                      Container(
                        width: 40, height: 40,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFFD4AF37), Color(0xFFB8860B)]),
                          borderRadius: BorderRadius.circular(10)),
                        child: const Icon(Icons.language_rounded,
                          color: Colors.white, size: 22)),
                      const SizedBox(width: 12),
                      Expanded(child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                        Text(s.ar ? 'الموقع الإلكتروني الرسمي' : 'Official Website',
                          style: const TextStyle(
                            color: Color(0xFFC9D1D9),
                            fontWeight: FontWeight.bold, fontSize: 13)),
                        const SizedBox(height: 2),
                        const Text('hammer24678-star.github.io/tilawa-enhancer-',
                          style: TextStyle(
                            color: Color(0xFF8B949E), fontSize: 11)),
                      ])),
                      const Icon(Icons.open_in_new_rounded,
                        color: Color(0xFF484F58), size: 16),
                    ]))),
                _infoSectionLabel(s.ar ? '🎯 المرجع الصوتي' : '🎯 Reference Standard'),""",
)

# ═══════════════════════════════════════════════════════════════════════════
# 2. NUMPY_OK / scipy coupling fixes
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(
    'assets/engines/engine_itiqan_v6_official.py',
    'decouple NUMPY_OK from scipy',
    old="""try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    from scipy.optimize import minimize
    NUMPY_OK = SCIPY_OK = True
except ImportError:
    NUMPY_OK = SCIPY_OK = False

try:
    from scipy.interpolate import PchipInterpolator
    _PCHIP_OK = True
except ImportError:
    _PCHIP_OK = False

try:
    from scipy.signal import correlate as _scipy_correlate
    _SIGNAL_OK = True
except ImportError:
    _SIGNAL_OK = False""",
    new="""# S225: NUMPY_OK must depend ONLY on numpy importing. It was previously set
# in the same try block as scipy.fft/scipy.optimize, so ANY scipy import
# failure (partial pip install, missing .so symlink, apk giving numpy but not
# scipy, etc.) silently set NUMPY_OK = False too — disabling ~60 functions
# across this file that only need numpy and were already numpy-only internally.
# rfft/rfftfreq are pure-math functions with an exact numpy.fft equivalent, so
# they now fall back to numpy instead of being a hard scipy dependency.
try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if NUMPY_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback

try:
    from scipy.optimize import minimize
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

try:
    from scipy.interpolate import PchipInterpolator
    _PCHIP_OK = True
except ImportError:
    _PCHIP_OK = False

try:
    from scipy.signal import correlate as _scipy_correlate
    _SIGNAL_OK = True
except ImportError:
    _SIGNAL_OK = False""",
)

apply_fix(
    'assets/engines/engine_isteidad_v21.py',
    'decouple NUMPY_OK from scipy',
    old="""try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    from scipy.optimize import minimize
    NUMPY_OK = SCIPY_OK = True
except ImportError:
    NUMPY_OK = SCIPY_OK = False

try:
    from scipy.interpolate import PchipInterpolator
    _PCHIP_OK = True
except ImportError:
    _PCHIP_OK = False""",
    new="""# S225: NUMPY_OK must depend ONLY on numpy importing — see the matching
# fix in engine_itiqan_v6_official.py for the full rationale. rfft/rfftfreq
# fall back to their exact numpy.fft equivalents when scipy.fft is missing.
try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if NUMPY_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback

try:
    from scipy.optimize import minimize
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

try:
    from scipy.interpolate import PchipInterpolator
    _PCHIP_OK = True
except ImportError:
    _PCHIP_OK = False""",
)

apply_fix(
    'assets/engines/hakim_gen_v2.py',
    'decouple _NP_OK from scipy',
    old="""try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    from scipy.signal import sosfiltfilt, butter
    _NP_OK = True
except ImportError:
    _NP_OK = False""",
    new="""# S225: _NP_OK now depends ONLY on numpy — see engine_itiqan_v6_official.py
# for the full rationale (any scipy failure was silently disabling the whole
# numpy-only pipeline here too). rfft/rfftfreq fall back to numpy's own
# equivalents when scipy.fft is unavailable.
try:
    import numpy as np
    _NP_OK = True
except ImportError:
    _NP_OK = False

try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if _NP_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback

try:
    from scipy.signal import sosfiltfilt, butter
except ImportError:
    pass""",
)

apply_fix(
    'assets/engines/bayan_ve_v2fix.py',
    'decouple NUMPY_OK from scipy',
    old="""try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False""",
    new="""try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

# S225: rfft/rfftfreq fall back to numpy's own equivalents when scipy.fft is
# unavailable, so a missing/broken scipy no longer disables this whole
# numpy-only engine (see engine_itiqan_v6_official.py for full rationale).
try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if NUMPY_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback""",
)

apply_fix(
    'assets/engines/idrak_text_v2.py',
    'decouple _NP_OK from scipy',
    old="""try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    _NP_OK = True
except ImportError:
    _NP_OK = False""",
    new="""try:
    import numpy as np
    _NP_OK = True
except ImportError:
    _NP_OK = False

# S225: rfft/rfftfreq fall back to numpy's own equivalents when scipy.fft is
# unavailable, so a missing/broken scipy no longer disables this whole
# numpy-only engine (see engine_itiqan_v6_official.py for full rationale).
try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if _NP_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback""",
)

apply_fix(
    'assets/engines/miraat_ref_v2.py',
    'decouple _NP_OK from scipy',
    old="""try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    _NP_OK = True
except ImportError:
    _NP_OK = False""",
    new="""try:
    import numpy as np
    _NP_OK = True
except ImportError:
    _NP_OK = False

# S225: rfft/rfftfreq fall back to numpy's own equivalents when scipy.fft is
# unavailable, so a missing/broken scipy no longer disables this whole
# numpy-only engine (see engine_itiqan_v6_official.py for full rationale).
try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if _NP_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback""",
)

apply_fix(
    'assets/engines/naqaa_v1_tested.py',
    'decouple NUMPY_OK from scipy, add SCIPY_OK for the full DSP pipeline',
    old="""# ── optional numpy/scipy ────────────────────────────────────────────────────
try:
    import numpy as np
    from scipy.fft    import rfft, irfft, rfftfreq
    from scipy.signal import (stft, istft, butter, sosfiltfilt, lfilter,
                               correlate, find_peaks)
    from scipy.ndimage import median_filter, uniform_filter1d
    from scipy.linalg  import solve_toeplitz
    from scipy.interpolate import PchipInterpolator
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False
    print('[النقاء] WARNING: numpy/scipy not found — DSP modules disabled')""",
    new="""# ── optional numpy/scipy ────────────────────────────────────────────────────
# S225: NUMPY_OK now depends ONLY on numpy — previously coupled with every
# scipy submodule import in one try block, so any single missing/broken scipy
# submodule silently disabled numpy-only functionality too (basic LUFS/FFT
# triage). rfft/irfft/rfftfreq fall back to numpy.fft equivalents; the full
# 8-phase DSP pipeline (scipy.signal/ndimage/linalg/interpolate) still needs
# real scipy and is gated separately via SCIPY_OK below.
try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False
    print('[النقاء] WARNING: numpy not found — DSP modules disabled')

try:
    from scipy.fft import rfft, irfft, rfftfreq
except ImportError:
    if NUMPY_OK:
        rfft, irfft, rfftfreq = np.fft.rfft, np.fft.irfft, np.fft.rfftfreq  # S225

try:
    from scipy.signal import (stft, istft, butter, sosfiltfilt, lfilter,
                               correlate, find_peaks)
    from scipy.ndimage import median_filter, uniform_filter1d
    from scipy.linalg  import solve_toeplitz
    from scipy.interpolate import PchipInterpolator
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False
    if NUMPY_OK:
        correlate = np.correlate  # S225: numpy fallback for simple autocorrelation use
        print('[النقاء] WARNING: scipy not found — full DSP pipeline disabled, '
              'basic numpy-only analysis still available')""",
)

apply_fix(
    'assets/engines/naqaa_v1_tested.py',
    'gate full 8-phase DSP pipeline on NUMPY_OK and SCIPY_OK',
    old="""    # ── NUMPY available check for DSP phases ──────────────────────────────
    if not NUMPY_OK:
        _log('  numpy unavailable — skipping DSP phases 1-8')
        _log('  Running LUFS normalization only...')
        cur_wav = _phase9_lufs(cur_wav, triage, res, _log)""",
    new="""    # ── NUMPY/SCIPY available check for DSP phases ─────────────────────────
    # S225: phases 1-8 use scipy.signal/ndimage/linalg/interpolate heavily,
    # so this gate must check SCIPY_OK too, not just NUMPY_OK (see import
    # block at top of file).
    if not NUMPY_OK or not SCIPY_OK:
        _log('  numpy/scipy unavailable — skipping DSP phases 1-8')
        _log('  Running LUFS normalization only...')
        cur_wav = _phase9_lufs(cur_wav, triage, res, _log)""",
)

apply_fix(
    'assets/engines/ihyaa_ve.py',
    'decouple NUMPY_OK from scipy',
    old="""try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq, irfft
    from scipy.signal import lfilter, butter
    from scipy.interpolate import PchipInterpolator
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False""",
    new="""try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

# S225: rfft/rfftfreq/irfft fall back to their numpy.fft equivalents when
# scipy.fft is unavailable, so a missing/broken scipy no longer disables this
# whole numpy-only engine (see engine_itiqan_v6_official.py for full rationale).
try:
    from scipy.fft import rfft, rfftfreq, irfft
except ImportError:
    if NUMPY_OK:
        rfft, rfftfreq, irfft = np.fft.rfft, np.fft.rfftfreq, np.fft.irfft  # S225

try:
    from scipy.signal import lfilter, butter
except ImportError:
    pass

try:
    from scipy.interpolate import PchipInterpolator
except ImportError:
    pass""",
)

# ═══════════════════════════════════════════════════════════════════════════
# 3. scipy.signal.lpc DOES NOT EXIST — replace with pure-numpy LPC
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(
    'assets/engines/ihyaa_ve.py',
    'add pure-numpy Levinson-Durbin LPC helper',
    old="""# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def _log(msg: str) -> None:
    print(msg, flush=True)""",
    new="""# ══════════════════════════════════════════════════════════════════════════════
#  LPC (pure numpy — S225)
# ══════════════════════════════════════════════════════════════════════════════
#  BUG FOUND: IH-2 Formant Enhancement called `from scipy.signal import lpc`,
#  wrapped in try/except ImportError. scipy.signal has never shipped a public
#  `lpc` function (LPC lives in librosa, not scipy), so that import raised
#  ImportError on every single call, on every machine, regardless of whether
#  scipy was installed. `_lpc_formants()` therefore always returned `[]` and
#  the entire IH-2 formant-restoration stage was silently dead code. Fixed by
#  replacing it with a standard autocorrelation + Levinson-Durbin LPC solve,
#  which only needs numpy and needs no scipy at all.
def _levinson_durbin_lpc(frame: 'np.ndarray', order: int) -> 'np.ndarray':
    \"\"\"
    Estimate LPC coefficients via autocorrelation + Levinson-Durbin recursion.
    Returns an (order+1)-length array `a` with a[0] == 1.0 — the same
    convention/shape a `scipy.signal.lpc`-style call would have returned.
    \"\"\"
    x = np.asarray(frame, dtype=np.float64)
    n = len(x)
    a = np.zeros(order + 1)
    a[0] = 1.0
    if n <= order:
        return a
    r_full = np.correlate(x, x, mode='full')
    mid = n - 1
    r = r_full[mid: mid + order + 1]
    if r[0] == 0:
        return a
    e = r[0]
    for i in range(1, order + 1):
        acc = r[i] + np.dot(a[1:i], r[i - 1:0:-1])
        k = -acc / e if e != 0 else 0.0
        a_new = a.copy()
        a_new[1:i] = a[1:i] + k * a[i - 1:0:-1]
        a_new[i] = k
        a = a_new
        e *= (1 - k * k)
        if e <= 0:
            break
    return a


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def _log(msg: str) -> None:
    print(msg, flush=True)""",
)

apply_fix(
    'assets/engines/ihyaa_ve.py',
    'fix _lpc_formants to use pure-numpy LPC',
    old="""    try:
        from scipy.signal import lpc as scipy_lpc
    except ImportError:
        return []

    N = len(frame)
    if N < order + 4:
        return []

    try:
        a = scipy_lpc(frame.astype(np.float64), order=order)
    except Exception:
        return []""",
    new="""    if not NUMPY_OK:
        return []

    N = len(frame)
    if N < order + 4:
        return []

    try:
        a = _levinson_durbin_lpc(frame.astype(np.float64), order)  # S225: was scipy.signal.lpc (doesn't exist)
    except Exception:
        return []""",
)

apply_fix(
    'assets/engines/ihyaa_ve.py',
    'remove dead always-failing scipy.signal.lpc import in _ih2_formant_enhance',
    old="""    try:
        from scipy.signal import lpc as scipy_lpc, sosfilt, butter as sci_butter
    except ImportError:
        return audio.copy()""",
    new="""    # S225 BUG FIX: this function used to open with
    #   try: from scipy.signal import lpc as scipy_lpc, sosfilt, butter as sci_butter
    #   except ImportError: return audio.copy()
    # scipy.signal has never shipped a public `lpc` function, so that import
    # raised ImportError on every call, on every machine — the entire IH-2
    # formant-enhancement stage below always short-circuited to a no-op
    # `return audio.copy()` before it ever ran. None of scipy_lpc/sosfilt/
    # sci_butter were actually referenced anywhere else in this function
    # (formant detection goes through `_lpc_formants()`, which now uses the
    # pure-numpy Levinson-Durbin implementation above), so the import is
    # removed rather than fixed.
    if not NUMPY_OK:
        return audio.copy()""",
)

apply_fix(
    'assets/engines/engine_isteidad_v21.py',
    'fix broken scipy.signal.lpc import that disabled MPRM',
    old="""import numpy as np
from numpy.fft import rfft, irfft, rfftfreq

try:
    from scipy.signal import lfilter, lpc as _scipy_lpc
    _SCIPY_SIGNAL_OK = True
except ImportError:
    _SCIPY_SIGNAL_OK = False

log = logging.getLogger(\"sidrah\")""",
    new="""import numpy as np
from numpy.fft import rfft, irfft, rfftfreq

# S225 BUG FIX: this used to be one `from scipy.signal import lfilter, lpc as
# _scipy_lpc` — scipy.signal has never shipped a public `lpc` function, so
# that import raised ImportError unconditionally (regardless of whether
# scipy itself was installed), which set _SCIPY_SIGNAL_OK = False on every
# machine and permanently disabled _mprm_enhance() (the Makhraj Pharyngeal
# Resonance Model stage) even though `lfilter` — the part it actually
# needs from scipy — is a completely real, working function. `_scipy_lpc`
# is replaced with a pure-numpy Levinson-Durbin LPC solve so this no longer
# needs scipy.signal.lpc at all.
try:
    from scipy.signal import lfilter
    _SCIPY_SIGNAL_OK = True
except ImportError:
    _SCIPY_SIGNAL_OK = False


def _scipy_lpc(frame: np.ndarray, order: int) -> np.ndarray:
    \"\"\"Pure-numpy LPC via autocorrelation + Levinson-Durbin (S225).\"\"\"
    x = np.asarray(frame, dtype=np.float64)
    n = len(x)
    a = np.zeros(order + 1)
    a[0] = 1.0
    if n <= order:
        return a
    r_full = np.correlate(x, x, mode='full')
    mid = n - 1
    r = r_full[mid: mid + order + 1]
    if r[0] == 0:
        return a
    e = r[0]
    for i in range(1, order + 1):
        acc = r[i] + np.dot(a[1:i], r[i - 1:0:-1])
        k = -acc / e if e != 0 else 0.0
        a_new = a.copy()
        a_new[1:i] = a[1:i] + k * a[i - 1:0:-1]
        a_new[i] = k
        a = a_new
        e *= (1 - k * k)
        if e <= 0:
            break
    return a

log = logging.getLogger(\"sidrah\")""",
)

apply_fix(
    'assets/engines/engine_isteidad_v21.py',
    'fix J-3 formant resonator gate (only ever needed LPC, not lfilter)',
    old="""    if not _SCIPY_SIGNAL_OK or not NUMPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    hop        = max(1, int(sr * 0.010))
    nfft       = hop * 4""",
    new="""    # S225 BUG FIX: this only ever needed LPC (no lfilter), but was gated on
    # _SCIPY_SIGNAL_OK — and its inner `from scipy.signal import lpc` always
    # raised ImportError (see the S225 note above `_scipy_lpc()`), so this
    # whole J-3 stage silently did nothing on every run. Now gated on
    # NUMPY_OK only, using the pure-numpy `_scipy_lpc()` LPC solve.
    if not NUMPY_OK:
        return audio
    if len(audio) < sr * 0.5:
        return audio

    hop        = max(1, int(sr * 0.010))
    nfft       = hop * 4""",
)

apply_fix(
    'assets/engines/engine_isteidad_v21.py',
    'use pure-numpy _scipy_lpc in J-3 formant tracking',
    old="""        formant_f = 0.0
        try:
            from scipy.signal import lpc as _lpc_fn
            a_coef    = _lpc_fn(frame * win, order=12)""",
    new="""        formant_f = 0.0
        try:
            a_coef    = _scipy_lpc(frame * win, order=12)  # S225: pure-numpy LPC""",
)

print()
print(f'Applied: {len(APPLIED)}   Skipped(already applied): {len(SKIPPED)}   Failed: {len(FAILED)}')
if FAILED:
    print()
    print('FAILURES — review these before committing:')
    for f in FAILED:
        print('  ' + f)
    sys.exit(1)

STAMP.write_text('ok\n')
print()
print('OK  S225 applied.')
print()
print('  git add lib/screens/home_screen.dart assets/engines/*.py')
print('  git commit -m "S225: fix numpy/scipy coupling bugs across all local')
print('  engines + dead scipy.signal.lpc (doesn'"'"'t exist) disabling IH-2/MPRM/J-3;')
print('  add website link to About sheet"')
