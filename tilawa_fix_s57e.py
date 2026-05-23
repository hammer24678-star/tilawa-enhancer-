#!/usr/bin/env python3
import sys
from pathlib import Path
HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
def rep(o,n,l):
    t=HS.read_text(encoding='utf-8')
    if o not in t: print(f'XX {l}'); sys.exit(1)
    HS.write_text(t.replace(o,n,1),encoding='utf-8'); print(f'OK {l}')

rep('margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),\n      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),',
    'margin: const EdgeInsets.fromLTRB(16, 10, 16, 10),\n      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),',
    'server banner margin')
rep('margin: const EdgeInsets.fromLTRB(16,10,16,4),\n    decoration: BoxDecoration(\n      color: _bgSurface,',
    'margin: const EdgeInsets.fromLTRB(16,16,16,8),\n    decoration: BoxDecoration(\n      color: _bgSurface,',
    'engine selector margin')
rep('padding: const EdgeInsets.fromLTRB(16,14,16,10),\n        child: Row(children: [\n            const Icon(Icons.tune_rounded,',
    'padding: const EdgeInsets.fromLTRB(18,16,18,14),\n        child: Row(children: [\n            const Icon(Icons.tune_rounded,',
    'engine header padding')
rep('margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),\n        decoration: BoxDecoration(\n          color: hasFile',
    'margin: const EdgeInsets.fromLTRB(16, 16, 16, 8),\n        decoration: BoxDecoration(\n          color: hasFile',
    'file card margin')
rep('padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),\n            child: Column(children: [',
    'padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),\n            child: Column(children: [',
    'file card inner padding')
rep('const SliverToBoxAdapter(child: SizedBox(height: 40)),',
    'const SliverToBoxAdapter(child: SizedBox(height: 64)),',
    'bottom padding')
print('\ngit add -A && git commit -m "S57e: spacing" && git push')
