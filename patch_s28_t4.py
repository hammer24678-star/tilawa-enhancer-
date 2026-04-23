#!/usr/bin/env python3
"""
patch_s28_t4.py — Fix duplicate declarations introduced by T1 double-insertion

Errors this fixes (from build #74):
  api_service.dart  : _lastEngineKey declared twice (lines 57 & 98)
                      saveLastEngine / loadLastEngine declared twice
  home_screen.dart  : _latencyMs declared twice
                      _shareFile() declared twice
  lang_provider.dart: shareBtn getter missing
"""

from pathlib import Path
import sys

REPO = Path(".")
OK   = "\033[92m FIXED\033[0m"
SKIP = "\033[94m  OK  \033[0m"
WARN = "\033[93m WARN \033[0m"
ERR  = "\033[91m ERR  \033[0m"
errors = 0

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def count_occurrences(text: str, marker: str) -> int:
    count = 0
    idx = 0
    while True:
        idx = text.find(marker, idx)
        if idx == -1:
            break
        count += 1
        idx += len(marker)
    return count


def remove_second_line(text: str, marker: str) -> str:
    """Remove the second line that contains marker (exact line removal)."""
    first = text.find(marker)
    second = text.find(marker, first + 1)
    line_start = text.rfind('\n', 0, second) + 1
    line_end = text.find('\n', second)
    if line_end == -1:
        line_end = len(text)
    else:
        line_end += 1  # include the newline
    return text[:line_start] + text[line_end:]


def remove_dart_method_second_occurrence(text: str, method_sig: str) -> str:
    """
    Find the second occurrence of method_sig, then scan forward to find the
    matching closing brace (counting { and }) and remove the whole block
    including any preceding comment lines.
    """
    first = text.find(method_sig)
    if first == -1:
        return text
    second = text.find(method_sig, first + 1)
    if second == -1:
        return text  # no duplicate

    # Walk back from second to remove any blank line + comment above it
    block_start = second
    # Go back over blank lines and comment lines
    before = text[:second]
    lines_before = before.split('\n')
    trim_lines = 0
    for line in reversed(lines_before):
        stripped = line.strip()
        if stripped == '' or stripped.startswith('//') or stripped.startswith('///'):
            trim_lines += 1
        else:
            break
    # Recalculate block_start
    if trim_lines > 0:
        # Find position of the line that is trim_lines before second
        pos = second
        for _ in range(trim_lines):
            pos = text.rfind('\n', 0, pos)
            if pos == -1:
                pos = 0
                break
        block_start = pos  # keep the \n before, remove from next line

    # Now scan forward from second to find the matching closing brace
    brace_depth = 0
    i = second
    found_opening = False
    while i < len(text):
        ch = text[i]
        if ch == '{':
            brace_depth += 1
            found_opening = True
        elif ch == '}':
            brace_depth -= 1
            if found_opening and brace_depth == 0:
                # End of the method body
                end = i + 1
                # Consume trailing newline
                if end < len(text) and text[end] == '\n':
                    end += 1
                return text[:block_start] + text[end:]
        i += 1

    return text  # fallback: no change


def fix_duplicate_const(text: str, const_line_start: str) -> str:
    """
    Remove the second occurrence of a const declaration line and everything
    through the end of the next method that closes at the same indent level.
    Used for _lastEngineKey + saveLastEngine + loadLastEngine block.
    """
    first = text.find(const_line_start)
    if first == -1:
        return text
    second = text.find(const_line_start, first + 1)
    if second == -1:
        return text  # not duplicated

    # Walk back to include blank/comment lines before the second block
    block_start = second
    before = text[:second]
    lines_before = before.split('\n')
    trim_lines = 0
    for line in reversed(lines_before):
        stripped = line.strip()
        if stripped == '' or stripped.startswith('//') or stripped.startswith('///'):
            trim_lines += 1
        else:
            break
    if trim_lines > 0:
        pos = second
        for _ in range(trim_lines):
            pos = text.rfind('\n', 0, pos)
            if pos == -1:
                pos = 0
                break
        block_start = pos

    # From second, scan forward collecting all methods until we get back
    # to zero-depth and hit a blank line or a different section marker.
    # Strategy: scan past `loadLastEngine` closing brace.
    # We'll count braces from 'second' forward, and stop after we've
    # closed two complete methods (saveLastEngine + loadLastEngine).
    method_closes = 0
    brace_depth = 0
    i = second
    end = second
    while i < len(text) and method_closes < 2:
        ch = text[i]
        if ch == '{':
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0:
                method_closes += 1
                end = i + 1
        i += 1

    if method_closes < 1:
        # Fallback: couldn't find methods, just remove const line
        line_end = text.find('\n', second)
        if line_end == -1:
            line_end = len(text)
        else:
            line_end += 1
        return text[:block_start] + text[line_end:]

    # Consume trailing newline after block
    if end < len(text) and text[end] == '\n':
        end += 1

    return text[:block_start] + text[end:]


# ─────────────────────────────────────────────────────────────────────────────
# F1 — api_service.dart — remove duplicate _lastEngineKey block
# ─────────────────────────────────────────────────────────────────────────────
print("\n[F1] api_service.dart — duplicate _lastEngineKey / saveLastEngine / loadLastEngine")
API = REPO / "lib/services/api_service.dart"
if not API.exists():
    print(f"{ERR} api_service.dart not found")
    errors += 1
else:
    text = API.read_text(encoding="utf-8")
    n = count_occurrences(text, "static const _lastEngineKey")
    if n == 0:
        print(f"{WARN} _lastEngineKey not found at all — was T1 applied?")
        errors += 1
    elif n == 1:
        print(f"{SKIP} _lastEngineKey appears once — no fix needed")
    else:
        print(f"      _lastEngineKey appears {n}× — removing duplicate block")
        new_text = fix_duplicate_const(text, "  static const _lastEngineKey")
        # Verify
        n2 = count_occurrences(new_text, "static const _lastEngineKey")
        if n2 == 1:
            API.write_text(new_text, encoding="utf-8")
            print(f"{OK}  api_service.dart: duplicate _lastEngineKey block removed")
        else:
            print(f"{ERR} After fix, _lastEngineKey appears {n2}× — manual fix needed")
            errors += 1

    # Also check for duplicate checkServer / shareAudio (may or may not be duplicated)
    for method_sig in ["  static Future<int?> checkServer()", "  static Future<void> shareAudio("]:
        text = API.read_text(encoding="utf-8")
        n = count_occurrences(text, method_sig)
        if n >= 2:
            print(f"      {method_sig.strip()}: appears {n}× — removing second")
            new_text = remove_dart_method_second_occurrence(text, method_sig)
            API.write_text(new_text, encoding="utf-8")
            print(f"{OK}  api_service.dart: duplicate {method_sig.strip()} removed")
        elif n == 1:
            print(f"{SKIP} {method_sig.strip()} appears once — ok")
        else:
            # Not present — warn (may not be needed)
            print(f"{WARN} {method_sig.strip()} not found — check api_service.dart manually")


# ─────────────────────────────────────────────────────────────────────────────
# F2 — home_screen.dart — remove duplicate _latencyMs declaration
# ─────────────────────────────────────────────────────────────────────────────
print("\n[F2] home_screen.dart — duplicate _latencyMs state variable")
HOME = REPO / "lib/screens/home_screen.dart"
if not HOME.exists():
    print(f"{ERR} home_screen.dart not found")
    errors += 1
else:
    text = HOME.read_text(encoding="utf-8")
    # _latencyMs is declared as a state variable line: "  int?    _latencyMs;"
    # Try a few possible spacing variants
    marker = None
    for m in ["int?    _latencyMs", "int? _latencyMs", "int?  _latencyMs"]:
        if m in text:
            marker = m
            break
    if marker is None:
        print(f"{WARN} _latencyMs declaration not found — T1 may not have been applied")
        errors += 1
    else:
        n = count_occurrences(text, marker)
        if n == 1:
            print(f"{SKIP} _latencyMs appears once — ok")
        else:
            print(f"      _latencyMs appears {n}× — removing second occurrence")
            new_text = remove_second_line(text, marker)
            HOME.write_text(new_text, encoding="utf-8")
            print(f"{OK}  home_screen.dart: duplicate _latencyMs line removed")


# ─────────────────────────────────────────────────────────────────────────────
# F3 — home_screen.dart — remove duplicate _shareFile() method
# ─────────────────────────────────────────────────────────────────────────────
print("\n[F3] home_screen.dart — duplicate _shareFile() method")
if HOME.exists():
    text = HOME.read_text(encoding="utf-8")
    sig = "Future<void> _shareFile()"
    n = count_occurrences(text, sig)
    if n == 0:
        print(f"{WARN} _shareFile() not found — T1 may not have been applied")
        errors += 1
    elif n == 1:
        print(f"{SKIP} _shareFile() appears once — ok")
    else:
        print(f"      _shareFile() appears {n}× — removing second method body")
        new_text = remove_dart_method_second_occurrence(text, f"  {sig}")
        n2 = count_occurrences(new_text, sig)
        if n2 == 1:
            HOME.write_text(new_text, encoding="utf-8")
            print(f"{OK}  home_screen.dart: duplicate _shareFile() removed")
        else:
            print(f"{ERR} After fix _shareFile() still appears {n2}× — manual fix needed")
            errors += 1


# ─────────────────────────────────────────────────────────────────────────────
# F4 — lang_provider.dart — add shareBtn getter if missing
# ─────────────────────────────────────────────────────────────────────────────
print("\n[F4] lang_provider.dart — shareBtn getter")
LANG = REPO / "lib/state/lang_provider.dart"
if not LANG.exists():
    print(f"{ERR} lang_provider.dart not found")
    errors += 1
else:
    text = LANG.read_text(encoding="utf-8")
    if "shareBtn" in text:
        print(f"{SKIP} shareBtn already present")
    else:
        # Insert after privacyPolicy line
        anchor = "String get privacyPolicy"
        if anchor not in text:
            print(f"{WARN} Could not find anchor '{anchor}' — adding before closing brace of S class")
            # Find the closing brace of class S (before LangProvider class)
            class_s_end = text.find("\n/// InheritedWidget")
            if class_s_end == -1:
                class_s_end = text.find("\nclass LangProvider")
            if class_s_end == -1:
                print(f"{ERR} Could not find insertion point for shareBtn")
                errors += 1
            else:
                # Insert before closing brace of S
                closing = text.rfind("}", 0, class_s_end)
                insert_pos = text.rfind("\n", 0, closing) + 1
                addition = "  String get shareBtn      => ar ? '\u0645\u0634\u0627\u0631\u0643\u0629'                       : 'Share';\n"
                new_text = text[:insert_pos] + addition + text[insert_pos:]
                LANG.write_text(new_text, encoding="utf-8")
                print(f"{OK}  lang_provider.dart: shareBtn added")
        else:
            # Find the end of the privacyPolicy line
            idx = text.find(anchor)
            line_end = text.find('\n', idx) + 1
            addition = "  String get shareBtn      => ar ? '\u0645\u0634\u0627\u0631\u0643\u0629'                       : 'Share';\n"
            new_text = text[:line_end] + addition + text[line_end:]
            LANG.write_text(new_text, encoding="utf-8")
            print(f"{OK}  lang_provider.dart: shareBtn added after privacyPolicy")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL FIXES APPLIED \033[0m")
    print()
    print("Next:")
    print("  git add lib/services/api_service.dart \\")
    print("          lib/screens/home_screen.dart \\")
    print("          lib/state/lang_provider.dart")
    print("  git commit -m 'S28-T4: fix duplicate declarations + missing shareBtn'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} FIX(ES) COULD NOT BE APPLIED — see WARN/ERR lines \033[0m")
    sys.exit(1)
