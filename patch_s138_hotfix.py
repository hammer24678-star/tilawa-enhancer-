import sys
from pathlib import Path

kt_glob = list(Path.home().glob(
    'tilawa-enhancer/android/app/src/main/kotlin/**/*LocalEngineRunner.kt'
))
if not kt_glob:
    print('XX LocalEngineRunner.kt not found'); sys.exit(1)

KT = kt_glob[0]
print(f'>> {KT}')
t = KT.read_text(encoding='utf-8')

if 'val outFile = File(outputPath)' in t:
    t = t.replace('val outFile = File(outputPath)', 'var outFile = File(outputPath)', 1)
    print('OK fix-A: first outFile → var')
else:
    print('XX fix-A not found')

if 'val outFile = File(resolvedOutput)' in t:
    t = t.replace('val outFile = File(resolvedOutput)', 'outFile = File(resolvedOutput)', 1)
    print('OK fix-B: second val outFile removed')
else:
    print('XX fix-B not found')

KT.write_text(t, encoding='utf-8')
print('done')
