#!/usr/bin/env python3
"""Fix welcome_screen ShaderMask — exact text from dump"""
from pathlib import Path

f = Path.home() / 'tilawa-enhancer/lib/screens/welcome_screen.dart'
txt = f.read_text(encoding='utf-8')

OLD = (
    "        ShaderMask(\n"
    "      shaderCallback: (b) => const LinearGradient(\n"
    "        colors: [Color(0xFFD4AF37), Color(0xFFF0CF60), Color(0xFFD4AF37)],\n"
    "        stops: [0.0, 0.5, 1.0]).createShader(b),\n"
    "      child: Text(s.appName,\n"
    "          textAlign: TextAlign.center,\n"
    "          style: const TextStyle(\n"
    "            fontSize: 36, fontWeight: FontWeight.bold,\n"
    "            color: Color(0xFFD4AF37), height: 1.2,\n"
    "            letterSpacing: -0.5)),\n"
    "        const SizedBox(height: 8),"
)
NEW = (
    "        ShaderMask(\n"
    "          shaderCallback: (b) => const LinearGradient(\n"
    "            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60), Color(0xFFD4AF37)],\n"
    "            stops: [0.0, 0.5, 1.0]).createShader(b),\n"
    "          child: Text(s.appName,\n"
    "            textAlign: TextAlign.center,\n"
    "            style: const TextStyle(\n"
    "              fontSize: 36, fontWeight: FontWeight.bold,\n"
    "              color: Colors.white, height: 1.2,\n"
    "              letterSpacing: -0.5))),\n"
    "        const SizedBox(height: 8),"
)

if OLD in txt:
    txt = txt.replace(OLD, NEW, 1)
    f.write_text(txt, encoding='utf-8')
    print('✅ ShaderMask fixed')
else:
    print('XX not found — printing lines 130-145:')
    for i, l in enumerate(txt.splitlines()[129:145], 130):
        print(f'{i:4d}  {repr(l)}')
