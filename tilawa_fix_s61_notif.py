import sys
from pathlib import Path

ROOT = Path.home() / 'tilawa-enhancer'
HS   = ROOT / 'lib/screens/home_screen.dart'
PY   = ROOT / 'patch_android.py'
PUB  = ROOT / 'pubspec.yaml'

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old not in t:
        print(f'  XX  NOT FOUND — {lbl}  [{path.name}]'); sys.exit(1)
    path.write_text(t.replace(old, new, 1), encoding='utf-8')
    print(f'  OK  {lbl}')

rep(PUB,
    '  shared_preferences: ^2.2.2',
    '  shared_preferences: ^2.2.2\n  flutter_local_notifications: ^17.2.0  # S61',
    'pubspec: add package')

rep(HS,
    "import 'settings_screen.dart';",
    "import 'settings_screen.dart';\nimport 'package:flutter_local_notifications/flutter_local_notifications.dart'; // S61",
    'import')

rep(HS,
    '  int _fallbackRetries = 0;    // S32: auto-retry counter for fallback mode',
    '  int _fallbackRetries = 0;    // S32: auto-retry counter for fallback mode\n  late FlutterLocalNotificationsPlugin _notif; // S61',
    'field _notif')

rep(HS,
    '    WidgetsBinding.instance.addObserver(this); // S56: lifecycle observer',
    '    WidgetsBinding.instance.addObserver(this); // S56: lifecycle observer\n'
    '    _notif = FlutterLocalNotificationsPlugin();\n'
    "    _notif.initialize(const InitializationSettings(\n"
    "      android: AndroidInitializationSettings('@mipmap/ic_launcher'),\n"
    '    )).then((_) {\n'
    '      _notif.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()\n'
    '          ?.requestNotificationsPermission();\n'
    '    });',
    'initState init')

rep(HS,
    '    if (file != null) _resultCtrl.forward(from: 0); // S29: animate in',
    '    if (file != null) _resultCtrl.forward(from: 0); // S29: animate in\n    if (file != null) _fireCompletionNotif(filename, score); // S61',
    'fire on success')

rep(HS,
    '  // ── Manual re-download button ──────────────────────────────────────────────',
    '  // ── S61: completion notification ──────────────────────────────────────────\n'
    '  Future<void> _fireCompletionNotif(String filename, dynamic score) async {\n'
    '    final s = score is num ? score.round() : 0;\n'
    "    final label = s >= 96 ? 'ممتاز' : s >= 90 ? 'رائع' : s >= 85 ? 'جيد جداً' : 'جيد';\n"
    '    const details = NotificationDetails(\n'
    '      android: AndroidNotificationDetails(\n'
    "        'tilawa_done', 'التحسين اكتمل',\n"
    "        channelDescription: 'إشعار عند اكتمال تحسين التلاوة',\n"
    '        importance: Importance.high, priority: Priority.high,\n'
    '        color: Color(0xFFC8A048),\n'
    "        icon: '@mipmap/ic_launcher',\n"
    '        playSound: true, enableVibration: true),);\n'
    '    try {\n'
    "      await _notif.show(0, 'محسِّن التلاوة ✦', '$filename · $s/100 $label', details);\n"
    '    } catch (_) {}\n'
    '  }\n\n'
    '  // ── Manual re-download button ──────────────────────────────────────────────',
    'method _fireCompletionNotif')

rep(PY,
    '    <uses-permission android:name="android.permission.INTERNET"/>',
    '    <uses-permission android:name="android.permission.INTERNET"/>\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>',
    'POST_NOTIFICATIONS permission')

print('\n  ALL DONE — 7/7')
