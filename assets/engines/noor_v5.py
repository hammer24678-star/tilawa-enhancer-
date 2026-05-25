#!/usr/bin/env python3
"""
NOOR ENGINE v5 — Voice Character Correction
Usage: python3 noor_v5.py -i input.mp3 -o output.mp3
"""
import argparse, os, subprocess, sys, tempfile
import numpy as np
from scipy.fft import rfft, irfft, rfftfreq
from scipy.signal import get_window, lfilter, butter, sosfiltfilt
from pathlib import Path

SR   = 48_000
_TMP = tempfile.gettempdir()


def load(path, sr=SR):
    r = subprocess.run(['ffmpeg','-y','-i',path,'-ar',str(sr),'-ac','1',
                        '-f','f32le','pipe:1'], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()

def save_wav(a, path, sr=SR):
    subprocess.run(['ffmpeg','-y','-f','f32le','-ar',str(sr),'-ac','1',
                    '-i','pipe:0','-c:a','pcm_s24le',path],
                   input=a.astype(np.float32).tobytes(),
                   capture_output=True, check=True)

def to_mp3(wav, mp3):
    subprocess.run(['ffmpeg','-y','-i',wav,'-c:a','libmp3lame',
                    '-b:a','320k','-q:a','0',mp3],
                   capture_output=True, check=True)

def rms(a):
    return float(np.sqrt(np.mean(a.astype(np.float64)**2)) + 1e-20)

def db(a):
    return float(20*np.log10(rms(a)))


# ── F0 detection ──────────────────────────────────────────────────────────────
def f0(frame, sr=SR):
    win = frame * np.hanning(len(frame))
    if np.sqrt(np.mean(win**2)) < 4e-5:
        return 0.0
    lo, hi = int(sr/450), min(int(sr/75), len(frame)//2)
    c = np.correlate(win, win, 'full')[len(frame)-1:]
    c /= c[0] + 1e-12
    seg = c[lo:hi]
    if not len(seg): return 0.0
    pk = int(np.argmax(seg))
    if seg[pk] < 0.35: return 0.0
    lag = pk + lo
    if 0 < lag < len(c)-1:
        y0,y1,y2 = c[lag-1],c[lag],c[lag+1]
        d = y0-2*y1+y2
        if abs(d)>1e-10: lag += 0.5*(y0-y2)/d
    return float(sr / max(lag, 1.0))


# ── Stage 1: STFT harmonic noise gate ────────────────────────────────────────
def harmonic_gate(audio, sharpness=8.0, floor=0.06, strength=0.90,
                  fsize=2048, hop=1024, sr=SR):
    """
    STFT spectral mask: gaussian peaks at F0 harmonics, floor between them.
    50% overlap (hop=fsize//2) with hann^2 OLA — stable reconstruction.
    Edge samples (low weight) zeroed to avoid division spikes.
    """
    n    = len(audio)
    out  = np.zeros(n, dtype=np.float64)
    wts  = np.zeros(n, dtype=np.float64)
    hann = get_window('hann', fsize).astype(np.float64)
    freq = rfftfreq(fsize, d=1.0/sr)
    v = u = 0

    for s in range(0, n - fsize, hop):
        frame = audio[s:s+fsize].astype(np.float64)
        wf    = frame * hann
        F0    = f0(wf, sr)

        if F0 > 0:
            spec  = rfft(wf)
            sigma = F0 / sharpness
            mask  = np.full(len(freq), floor)
            k = 1
            while k * F0 < freq[-1]:
                mask = np.maximum(mask,
                                  np.exp(-0.5*((freq - k*F0)/sigma)**2))
                k += 1
            rec = irfft(spec * (mask*strength + (1.0-strength)), n=fsize)
            v  += 1
        else:
            rec = irfft(rfft(wf), n=fsize)   # pass-through
            u  += 1

        out[s:s+fsize] += rec  * hann
        wts[s:s+fsize] += hann * hann

    # Avoid edge spikes: only divide where weight is large enough
    safe          = wts > 0.01
    result        = np.zeros(n, dtype=np.float64)
    result[safe]  = out[safe] / wts[safe]

    # RMS preserve
    result *= rms(audio) / (float(np.sqrt(np.mean(result**2))) + 1e-20)
    result  = result.astype(np.float32)

    print(f'  [gate] voiced={v} unvoiced={u}  '
          f'max={np.max(np.abs(result)):.4f}  RMS={db(result):.2f}dBFS')
    return result


# ── Stage 2: even-harmonic enrichment ────────────────────────────────────────
def even_harmonics(audio, drive=1.8, mix_db=-18.0, sr=SR):
    """
    x² nonlinearity on body band → pure 2nd harmonic.
    Corrects odd/even balance toward reference.
    enchanted odd/even=+8.1dB, ref=+5.5dB → need ~2.6dB more even energy.
    """
    sos_src = butter(4, [100/(sr/2), 600/(sr/2)], btype='band', output='sos')
    body    = sosfiltfilt(sos_src, audio.astype(np.float64))

    norm    = body / (np.std(body) * drive + 1e-10)
    even    = norm ** 2
    even   -= np.mean(even)                        # remove DC

    sos_bp  = butter(4, [200/(sr/2), 1400/(sr/2)], btype='band', output='sos')
    even    = sosfiltfilt(sos_bp, even)

    mix_lin = rms(audio) * 10**(mix_db/20.0)
    ev_rms  = float(np.sqrt(np.mean(even**2)) + 1e-20)
    even   *= mix_lin / ev_rms

    result  = (audio.astype(np.float64) + even).astype(np.float32)
    print(f'  [even] mix={mix_db:.1f}dB  added_RMS={20*np.log10(ev_rms*mix_lin/ev_rms+1e-20):.1f}dBFS')
    return result


# ── Stage 3: parametric EQ (scipy biquads, float64) ──────────────────────────
def peak(a, freq, gain, q, sr=SR):
    A = 10**(gain/40.0); w0 = 2*np.pi*freq/sr; al = np.sin(w0)/(2*q)
    b = [1+al*A, -2*np.cos(w0), 1-al*A]
    a_ = [1+al/A, -2*np.cos(w0), 1-al/A]
    return lfilter([x/a_[0] for x in b], [1.0, a_[1]/a_[0], a_[2]/a_[0]], a)

def loshelf(a, freq, gain, q=0.65, sr=SR):
    A  = 10**(gain/40.0); w0 = 2*np.pi*freq/sr
    cw = np.cos(w0); sw = np.sin(w0)
    al = sw/2 * np.sqrt((A+1/A)*(1/q-1)+2)
    b  = [ A*((A+1)-(A-1)*cw+2*np.sqrt(A)*al),
          2*A*((A-1)-(A+1)*cw),
           A*((A+1)-(A-1)*cw-2*np.sqrt(A)*al)]
    a_ = [   (A+1)+(A-1)*cw+2*np.sqrt(A)*al,
          -2*((A-1)+(A+1)*cw),
              (A+1)+(A-1)*cw-2*np.sqrt(A)*al]
    return lfilter([x/a_[0] for x in b], [1.0,a_[1]/a_[0],a_[2]/a_[0]], a)

def apply_eq(audio, nodes):
    """nodes: list of (freq, gain_db, q, type) where type='peak'|'lowshelf'"""
    eq = audio.astype(np.float64)
    for freq, gain, q, typ in nodes:
        if abs(gain) < 0.05: continue
        if typ == 'lowshelf':
            eq = loshelf(eq, freq, gain, q)
        else:
            eq = peak(eq, freq, gain, q)
        print(f'  [eq] {typ:<10} {freq:>5}Hz  {gain:>+5.1f}dB  Q={q}')
    return eq


# ── Band measurement ──────────────────────────────────────────────────────────
def bands(audio, n=131072):
    spec  = np.abs(rfft(audio[:n].astype(np.float64)*np.hanning(n)))
    freq  = rfftfreq(n, d=1.0/SR)
    def b(lo, hi):
        return float(20*np.log10(np.mean(spec[(freq>=lo)&(freq<hi)])+1e-20))
    return {'body':b(80,200), 'body-hi':b(200,500), 'warmth':b(500,1000),
            'mid':b(1000,2000), 'presence':b(2000,4000), 'upper':b(4000,8000)}


# ── Main pipeline ─────────────────────────────────────────────────────────────
def run(inp, out, ref=None,
        sharpness=8.0, floor=0.06, strength=0.90,
        even_drive=1.8, even_mix=-18.0,
        eq_nodes=None):

    print(f'\n╔═══════════════════════════════════╗')
    print(f'║  NOOR ENGINE v5                   ║')
    print(f'╚═══════════════════════════════════╝')
    print(f'  in  → {os.path.basename(inp)}')
    print(f'  out → {os.path.basename(out)}\n')

    audio     = load(inp)
    target_db = db(audio)
    in_bands  = bands(audio)
    print(f'  Loaded: {len(audio)/SR:.1f}s  RMS={target_db:.2f}dBFS\n')

    ref_bands = None
    if ref and os.path.exists(ref):
        r   = load(ref)
        sc  = rms(audio) / rms(r)
        ref_bands = bands((r*sc).astype(np.float32))

    # Stage 1
    print('── Stage 1: Harmonic Noise Gate ──')
    s1 = harmonic_gate(audio, sharpness=sharpness, floor=floor,
                        strength=strength)

    # Stage 2
    print('\n── Stage 2: Even-Harmonic Enrichment ──')
    s2 = even_harmonics(s1, drive=even_drive, mix_db=even_mix)

    # Stage 3
    print('\n── Stage 3: EQ ──')
    if eq_nodes is None:
        eq_nodes = [
            (130,  +2.5, 0.65, 'lowshelf'),  # body restore
            (380,  -1.5, 0.90, 'peak'),       # body-hi cut
            (650,  -2.0, 0.90, 'peak'),       # warmth cut
            (1400, -2.0, 0.85, 'peak'),       # mid cut
            (2800, -1.5, 0.90, 'peak'),       # presence cut
            (5500, -1.0, 0.90, 'peak'),       # upper trim
            (3500, +1.0, 1.20, 'peak'),       # centroid lift
        ]
    s3 = apply_eq(s2, eq_nodes)

    # Volume match — exact RMS to input, no loudnorm
    gain   = rms(audio) / (float(np.sqrt(np.mean(s3**2))) + 1e-20)
    result = np.clip(s3 * gain, -0.97, 0.97).astype(np.float32)
    print(f'\n  Volume match: gain={20*np.log10(gain):+.2f}dB  '
          f'final RMS={db(result):.2f}dBFS')

    # Encode
    tmp = os.path.join(_TMP, 'noor_v5_tmp.wav')
    save_wav(result, tmp)
    to_mp3(tmp, out)
    Path(tmp).unlink(missing_ok=True)

    # Report
    final    = load(out)
    sc_fin   = rms(audio) / rms(final)
    out_bands = bands((final * sc_fin).astype(np.float32))

    print(f'\n  {"Band":<14} {"Ref":>7} {"Input":>7} {"Output":>7} {"Gap":>7}')
    print('  ' + '-'*46)
    for k in in_bands:
        r_ = ref_bands[k] if ref_bands else 0.0
        i_ = in_bands[k];  o_ = out_bands[k]
        gap_i = i_ - r_; gap_o = o_ - r_
        mark  = '✓' if ref_bands and abs(gap_o)<abs(gap_i) else ''
        ref_s = f'{r_:>7.1f}' if ref_bands else '    ---'
        print(f'  {k:<14} {ref_s} {i_:>7.1f} {o_:>7.1f} {gap_o:>+7.1f} {mark}')

    print(f'\n  ✓  {out}  ({Path(out).stat().st_size//1024} KB)')


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('-i', required=True)
    p.add_argument('-o', required=True)
    p.add_argument('--ref',        default=None)
    p.add_argument('--sharpness',  type=float, default=8.0)
    p.add_argument('--floor',      type=float, default=0.06)
    p.add_argument('--strength',   type=float, default=0.90)
    p.add_argument('--even-drive', type=float, default=1.8)
    p.add_argument('--even-mix',   type=float, default=-18.0)
    a = p.parse_args()
    run(a.i, a.o, ref=a.ref,
        sharpness=a.sharpness, floor=a.floor, strength=a.strength,
        even_drive=a.even_drive, even_mix=a.even_mix)
