python3 << 'PYEOF'
from pathlib import Path

HOME = Path('lib/screens/home_screen.dart')
text = HOME.read_text(encoding='utf-8')

OLD = (
    '  Color _tBg     = _tBg;\n'
    '  Color _tCard   = _tCard;\n'
    '  Color _tBorder = _tBorder;\n'
    '  Color _tText   = _tText;\n'
    '  Color _tSub    = _tSub;\n'
    '  Color _tDim    = _tDim;\n'
    '  Color _tGold   = _tGold;\n'
    '  bool  _tDark   = true;\n'
)
NEW = (
    '  Color _tBg     = const Color(0xFF080A0E);\n'
    '  Color _tCard   = const Color(0xFF161B22);\n'
    '  Color _tBorder = const Color(0xFF21262D);\n'
    '  Color _tText   = const Color(0xFFC9D1D9);\n'
    '  Color _tSub    = const Color(0xFF8B949E);\n'
    '  Color _tDim    = const Color(0xFF484F58);\n'
    '  Color _tGold   = const Color(0xFFD4AF37);\n'
    '  bool  _tDark   = true;\n'
)

if OLD not in text:
    print('SKIP: already fixed or anchor not found')
elif text.count(OLD) > 1:
    print('WARN: anchor not unique')
else:
    HOME.write_text(text.replace(OLD, NEW, 1), encoding='utf-8')
    print('OK: home_screen.dart field initializers restored')
PYEOF