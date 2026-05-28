#!/usr/bin/env python3
"""
tilawa_fix_s66_remote_config.py — Remote server config
=======================================================
Moves server list from hardcoded Dart to assets/servers.json
fetched on app startup. Adding new servers never requires
a new APK build — just update the JSON file on GitHub.

Patches:
  A  Create assets/servers.json with current 2 servers
  B  ApiService: fetch server list from asset + remote URL
  C  ApiService: _servers becomes dynamic list
"""
from pathlib import Path
from datetime import datetime
import json

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
API = Path.home() / 'tilawa-enhancer/lib/services/api_service.dart'
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(path, old, new, lbl):
    txt = path.read_text(encoding='utf-8')
    if old in txt: path.write_text(txt.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s66  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# A: Create assets/servers.json
assets_dir = Path.home() / 'tilawa-enhancer/assets'
assets_dir.mkdir(exist_ok=True)
servers_file = assets_dir / 'servers.json'
servers_data = {
    "servers": [
        "https://carm5333-tilawa-server.hf.space",
        "https://carm5333-background.hf.space"
    ],
    "remote_url": "https://raw.githubusercontent.com/hammer24678-star/tilawa-enhancer-/master/assets/servers.json"
}
servers_file.write_text(json.dumps(servers_data, indent=2, ensure_ascii=False))
ok('assets/servers.json created')

# Check if flutter assets includes json files
pubspec = Path.home() / 'tilawa-enhancer/pubspec.yaml'
pubspec_txt = pubspec.read_text()
if 'assets/servers.json' not in pubspec_txt and 'assets/' in pubspec_txt:
    # Already has assets/ glob or specific entries
    if '    - assets/' in pubspec_txt and 'servers' not in pubspec_txt:
        pubspec_txt = pubspec_txt.replace(
            '    - assets/',
            '    - assets/\n    - assets/servers.json\n    - assets/',
            1)
        pubspec.write_text(pubspec_txt)
        ok('pubspec.yaml: added assets/servers.json')
    else:
        ok('pubspec.yaml: assets already covered')
else:
    ok('pubspec.yaml: servers.json already listed or not needed')

# B: Replace hardcoded _servers with dynamic loading
rep(API,
    "  // S65: dual-server pool — load balanced, auto-failover\n"
    "  static const List<String> _servers = [\n"
    "    'https://carm5333-tilawa-server.hf.space',\n"
    "    'https://carm5333-background.hf.space',\n"
    "  ];\n"
    "\n"
    "  // Server health cache: {url: {latency, queue, ts}}\n"
    "  static final Map<String, Map<String, dynamic>> _health = {};",

    "  // S66: dynamic server pool — loaded from assets/servers.json\n"
    "  // Add new servers by updating servers.json — no APK rebuild needed\n"
    "  static List<String> _servers = [\n"
    "    'https://carm5333-tilawa-server.hf.space',\n"
    "    'https://carm5333-background.hf.space',\n"
    "  ];\n"
    "  static bool _serversLoaded = false;\n"
    "\n"
    "  static Future<void> loadServers() async {\n"
    "    if (_serversLoaded) return;\n"
    "    try {\n"
    "      // Load from bundled asset\n"
    "      final txt = await rootBundle.loadString('assets/servers.json');\n"
    "      final data = jsonDecode(txt) as Map<String, dynamic>;\n"
    "      final local = (data['servers'] as List).cast<String>();\n"
    "      if (local.isNotEmpty) _servers = local;\n"
    "      // Optionally fetch fresh list from GitHub (non-blocking)\n"
    "      final remoteUrl = data['remote_url'] as String?;\n"
    "      if (remoteUrl != null) {\n"
    "        http.get(Uri.parse(remoteUrl))\n"
    "            .timeout(const Duration(seconds: 5))\n"
    "            .then((res) {\n"
    "          if (res.statusCode == 200) {\n"
    "            final rd = jsonDecode(res.body) as Map<String, dynamic>;\n"
    "            final remote = (rd['servers'] as List).cast<String>();\n"
    "            if (remote.isNotEmpty) _servers = remote;\n"
    "          }\n"
    "        }).catchError((_) {});\n"
    "      }\n"
    "    } catch (_) {} // keep defaults on any error\n"
    "    _serversLoaded = true;\n"
    "  }\n"
    "\n"
    "  // Server health cache: {url: {latency, queue, ts}}\n"
    "  static final Map<String, Map<String, dynamic>> _health = {};",
    'Fix-B dynamic server loading from assets/servers.json')

# C: Call loadServers in preWarm
rep(API,
    "  // Pre-warm all servers (call on app init + file picker open)\n"
    "  static Future<void> preWarm() async {\n"
    "    await Future.wait(_servers.map(_refreshHealth));\n"
    "  }",

    "  // Pre-warm all servers (call on app init + file picker open)\n"
    "  static Future<void> preWarm() async {\n"
    "    await loadServers(); // S66: ensure server list is current\n"
    "    await Future.wait(_servers.map(_refreshHealth));\n"
    "  }",
    'Fix-C preWarm calls loadServers first')

# D: Add flutter/services import if not present
api_txt = API.read_text()
if "import 'package:flutter/services.dart'" not in api_txt:
    api_txt = api_txt.replace(
        "import 'dart:io';",
        "import 'dart:io';\nimport 'package:flutter/services.dart';",
        1)
    API.write_text(api_txt)
    ok('Added flutter/services.dart import for rootBundle')
else:
    ok('flutter/services.dart already imported')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S66: remote server config -- dynamic pool from assets/servers.json" && git push\n')
