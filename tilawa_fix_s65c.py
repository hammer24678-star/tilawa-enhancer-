#!/usr/bin/env python3
"""tilawa_fix_s65c — fix remaining 4 anchors"""
from pathlib import Path
from datetime import datetime

API = Path.home() / 'tilawa-enhancer/lib/services/api_service.dart'
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(old, new, lbl):
    txt = API.read_text(encoding='utf-8')
    if old in txt: API.write_text(txt.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s65c  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

rep(
    "                http.MultipartRequest('POST', Uri.parse('$_base/upload_chunk'));",
    "                http.MultipartRequest('POST', Uri.parse('$server/upload_chunk'));",
    'Fix-6c upload_chunk')

rep(
    "    final finalRes = await http\n"
    "        .post(\n"
    "          Uri.parse('$_base/upload_finalize'),",
    "    final finalRes = await http\n"
    "        .post(\n"
    "          Uri.parse('$server/upload_finalize'),",
    'Fix-6d upload_finalize')

rep(
    "    final res = await http\n"
    "        .get(Uri.parse('$_base/status/$jobId'))",
    "    final res = await http\n"
    "        .get(Uri.parse('${_servers[0]}/status/$jobId'))",
    'Fix-6e status endpoint')

rep(
    "      'download_url': '$_base/download/$jobId',",
    "      'download_url': '${_servers[0]}/download/$jobId',",
    'Fix-6f download_url')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S65: complete multi-server LB -- health scoring, auto-retry, priority upload" && git push\n')
