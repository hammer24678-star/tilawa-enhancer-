#!/bin/bash
# Fix: remove WebViewActivity from manifest — url_launcher already declares it
# Run: cd ~/tilawa-enhancer && bash /sdcard/Download/fix_webview.sh

cd ~/tilawa-enhancer

python3 - << 'EOF'
from pathlib import Path

f = Path("build_tilawa_app.sh")
txt = f.read_text()

# Remove the WebViewActivity block entirely
# url_launcher_android declares it in its own manifest — we must not redeclare
old = '''        <!-- url_launcher: exported=false required Android 12+ -->
        <activity
            android:name="io.flutter.plugins.urllauncher.WebViewActivity"
            android:exported="false"
            android:theme="@android:style/Theme.Black.NoTitleBar"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
            android:hardwareAccelerated="true"
            android:windowSoftInputMode="adjustResize"/>'''

if old in txt:
    txt = txt.replace(old, "")
    f.write_text(txt)
    print("✅ WebViewActivity block removed")
else:
    print("❌ Block not found — check manually")
    # Show what's around WebViewActivity in the file
    idx = txt.find("WebViewActivity")
    if idx > 0:
        print("Found at index", idx)
        print(repr(txt[max(0,idx-200):idx+300]))
EOF

git add build_tilawa_app.sh
git commit -m "fix: remove WebViewActivity redeclaration — url_launcher owns it"
git push

echo ""
echo "Done — https://github.com/c42742910-ops/tilawa-enhancer/actions"
