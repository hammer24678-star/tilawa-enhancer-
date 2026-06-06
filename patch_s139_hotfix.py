from pathlib import Path
from datetime import datetime
PA = Path.home() / 'tilawa-enhancer/patch_android.py'
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  NOT FOUND — {l}'); _log.append(('XX',l))
def rep(old, new, lbl):
    t = PA.read_text(encoding='utf-8')
    if old in t: PA.write_text(t.replace(old,new,1),encoding='utf-8'); ok(lbl)
    else: xx(lbl)
print(f'\n{"="*58}\n  S139-HOTFIX  {datetime.now().strftime("%H:%M:%S")}\n{"="*58}')
rep(
    '            val outFile = File(outputPath)\n            // S137: if output missing at expected path, search cacheDir for recent file',
    '            var outFile = File(outputPath)\n            // S137: if output missing at expected path, search cacheDir for recent file',
    'Bug-1: first outFile -> var')
rep(
    '            val outFile = File(resolvedOutput)\n            if (outFile.exists() && outFile.length() > 500) {',
    '            outFile = File(resolvedOutput)\n            if (outFile.exists() && outFile.length() > 500) {',
    'Bug-2: second val outFile -> reassignment')
rep(
    'ui { channel?.invokeMethod("engineDone", mapOf("path" to outputPath) + extra) }',
    'ui { channel?.invokeMethod("engineDone", mapOf("path" to resolvedOutput) + extra) }',
    'Bug-3: engineDone -> resolvedOutput')
ok_n=sum(1 for s,_ in _log if s=='OK'); xx_n=sum(1 for s,_ in _log if s=='XX')
print(f'\n  {"OK All OK" if xx_n==0 else str(xx_n)+" FAILED"}  {ok_n} OK\n')
