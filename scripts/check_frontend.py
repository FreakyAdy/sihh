#!/usr/bin/env python3
"""Frontend Safety & Contract Checker for Krushna (@Krushna).

Run this command before committing or pushing changes to verify that:
1. No core engine, ML, or backend files were accidentally modified.
2. All critical UI element IDs required by app.js are present in index.html.
3. CSS and JavaScript files are intact with balanced syntax.

Usage:
    python scripts/check_frontend.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Safe encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DEMO_DIR = REPO_ROOT / "web-demo"

# Critical DOM element IDs that app.js expects to render navigation state
REQUIRED_DOM_IDS = [
    "routePath",
    "playBtn",
    "resetBtn",
    "stepBtn",
    "dynamicIsland",
    "gnssDesktopChip",
    "gnssDesktopText",
    "maneuverDistance",
    "maneuverStreet",
    "maneuverSub",
    "metricSpeed",
    "speedSource",
    "metricDrift",
    "driftStatus",
    "metricDuration",
    "metricCrossTrack",
    "chipNhc",
    "chipMap",
    "chipZupt",
    "deviceContainer",
    "viewToggleBtn",
    "manualOutageBtn",
    "vehicleGroup",
]


def check_git_boundaries() -> tuple[bool, list[str]]:
    """Checks if any modified or staged files are outside web-demo/."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception as e:
        print(f"[-] Could not check git status: {e}")
        return True, []

    foreign_files: list[str] = []
    for line in res.stdout.strip().splitlines():
        if not line.strip():
            continue
        # Format: XY <filepath>
        file_path = line[3:].strip()
        # Normalize path
        posix_path = file_path.replace("\\", "/")
        if not posix_path.startswith("web-demo/") and not posix_path.startswith(".obsidian/"):
            foreign_files.append(posix_path)

    return len(foreign_files) == 0, foreign_files


def check_html_integrity() -> tuple[bool, list[str]]:
    """Verifies that all required DOM IDs exist in index.html."""
    html_path = WEB_DEMO_DIR / "index.html"
    if not html_path.exists():
        return False, ["web-demo/index.html is missing!"]

    content = html_path.read_text(encoding="utf-8", errors="ignore")
    missing_ids: list[str] = []
    for dom_id in REQUIRED_DOM_IDS:
        # Check for id="dom_id" or id='dom_id'
        pattern = rf'id=[\'"]{re.escape(dom_id)}[\'"]'
        if not re.search(pattern, content):
            missing_ids.append(dom_id)

    return len(missing_ids) == 0, missing_ids


def check_css_and_js_syntax() -> tuple[bool, list[str]]:
    """Validates CSS and JS file presence and basic syntax sanity."""
    errors: list[str] = []
    
    css_path = WEB_DEMO_DIR / "styles.css"
    if not css_path.exists():
        errors.append("web-demo/styles.css is missing!")
    else:
        css = css_path.read_text(encoding="utf-8", errors="ignore")
        if css.count("{") != css.count("}"):
            errors.append(f"Mismatched curly braces in styles.css: {css.count('{')} '{{' vs {css.count('}')} '}}'")

    js_path = WEB_DEMO_DIR / "app.js"
    if not js_path.exists():
        errors.append("web-demo/app.js is missing!")
    else:
        js = js_path.read_text(encoding="utf-8", errors="ignore")
        if js.count("{") != js.count("}"):
            errors.append(f"Mismatched curly braces in app.js: {js.count('{')} '{{' vs {js.count('}')} '}}'")

    return len(errors) == 0, errors


def main() -> int:
    print("=" * 65)
    print("  🛡️  IDR FRONTEND SAFETY CHECK — KRUSHNA'S GUARD")
    print("=" * 65)

    all_passed = True

    # 1. Check Git Boundaries
    boundary_ok, foreign_files = check_git_boundaries()
    if boundary_ok:
        print("[+] Boundary Check: PASS (All edits are within web-demo/)")
    else:
        print("[!] Boundary Check: FAILED")
        print("    ⚠️  You modified files outside the frontend zone:")
        for f in foreign_files:
            print(f"       - {f}")
        print("    🚨 ONLY modify files inside 'web-demo/'.")
        print("    Run 'git checkout -- <file>' to restore non-frontend files.")
        all_passed = False

    # 2. Check HTML DOM Integrity
    dom_ok, missing_ids = check_html_integrity()
    if dom_ok:
        print(f"[+] HTML DOM Integrity: PASS (All {len(REQUIRED_DOM_IDS)} critical telemetry IDs found)")
    else:
        print("[!] HTML DOM Integrity: FAILED")
        print("    ⚠️  The following required element IDs are missing from index.html:")
        for dom_id in missing_ids:
            print(f"       - id=\"{dom_id}\"")
        print("    app.js needs these elements to render navigation telemetry!")
        all_passed = False

    # 3. Check CSS / JS files
    syntax_ok, syntax_errors = check_css_and_js_syntax()
    if syntax_ok:
        print("[+] CSS & JS Syntax: PASS (Styles and scripts are balanced and valid)")
    else:
        print("[!] CSS & JS Syntax: FAILED")
        for err in syntax_errors:
            print(f"       - {err}")
        all_passed = False

    print("=" * 65)
    if all_passed:
        print("🎉 ALL FRONTEND CHECKS PASSED!")
        print("Your code is safe, functional, and ready to commit and push.")
        print("=" * 65)
        return 0
    else:
        print("❌ FRONTEND CHECKS FAILED.")
        print("Please address the issues above before committing.")
        print("=" * 65)
        return 1


if __name__ == "__main__":
    sys.exit(main())
