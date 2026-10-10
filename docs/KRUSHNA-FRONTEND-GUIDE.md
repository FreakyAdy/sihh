# Krushna's Frontend Handoff & Developer Guide

Welcome **Krushna**! You are the designated owner of the **frontend zone** for the **Smart India Hackathon (ISRO PS 26168)** Intelligent Dead Reckoning project.

Your mission is to polish and enhance the **presentation layer (`web-demo/`)**—making the Apple Maps-style navigation HUD look state-of-the-art for evaluators and judges, while ensuring the underlying sensor fusion, ML models, and CI stay 100% protected.

---

## 🚀 Quick Start (1 Click)

1. Double-click **`run_demo.bat`** in the repository root.
   *(Or in PowerShell: `./run_demo.ps1`)*
2. Your browser will automatically open:
   👉 **`http://localhost:8080/index.html`**
3. Open `web-demo/index.html` or `web-demo/styles.css` in your code editor, make changes, and simply **refresh your browser (`Ctrl+F5`)** to see your updates live!

---

## 🛡️ Zone Boundaries: What You Can & Cannot Edit

This repository uses **ONEFORALL (`ofa`)** to prevent merge conflicts and protect core algorithms.

### ✅ Allowed Files (Your Playground)
You have exclusive write ownership of the **`frontend`** zone:
- `web-demo/index.html` — Layout, semantic structure, cards, SVG markers, presentation controls
- `web-demo/styles.css` — Modern styling, typography, glassmorphism, micro-animations, mobile responsiveness
- `web-demo/app.js` — UI rendering functions, button event listeners, sound effects, animations

### ❌ Strictly Forbidden Files (Do NOT touch)
Modifying any of these files will cause **GitHub Actions CI (`ofa guard`)** to fail:
- `edge-engine/` — Core Kalman filter and inertial navigation engine
- `ml/` — Machine learning speed estimation models
- `shared/` — Mathematical contracts and data classes
- `mobile/` — Android Kotlin engine and vehicle calibration
- `tests/` — Automated test suite (79 passing tests)
- `scripts/` — Training, certification, and release scripts

> 💡 **Need new telemetry data?**
> If you want a new metric displayed on the dashboard (e.g., GPS satellite count, elevation, temperature), ask **@FreakyAdy** to add it to the state model!

---

## 🧰 Your Personal Safety Tool: `check_frontend.py`

Before committing or opening a pull request, run this one command in your terminal:

```bash
python scripts/check_frontend.py
```

This safety tool automatically checks:
1. **Boundary Guard**: Ensures no files outside `web-demo/` were touched.
2. **DOM Element Integrity**: Checks that all 23 telemetry IDs expected by `app.js` are still present in `index.html`.
3. **Syntax Sanity**: Verifies that CSS and JS files have balanced braces and no parse crashes.

When you see:
```text
🎉 ALL FRONTEND CHECKS PASSED!
Your code is safe, functional, and ready to commit and push.
```
...you are 100% good to go!

---

## 📋 Critical DOM IDs Cheat Sheet

When redesigning cards or rearranging elements in `web-demo/index.html`, **keep these `id="..."` attributes intact** so `app.js` can bind real-time telemetry to them:

| Element ID | What it Renders / Controls | Can you change its styling / HTML tag? |
| :--- | :--- | :--- |
| `playBtn` | Play / Pause button | Yes, any button or clickable element |
| `resetBtn` | Replay restart button | Yes |
| `stepBtn` | Advance 1 tick forward | Yes |
| `viewToggleBtn` | Fullscreen / iPhone frame toggle | Yes |
| `manualOutageBtn`| Manual GNSS blackout toggle | Yes |
| `dynamicIsland` | Morphing iOS Dynamic Island pill | Yes (keep classes `.outage-alert` styled) |
| `gnssDesktopChip`| Desktop top-bar GNSS status pill | Yes |
| `gnssDesktopText`| Desktop top-bar status text | Yes |
| `maneuverDistance`| Turn-by-turn remaining meters | Yes |
| `maneuverStreet` | Turn-by-turn road / tunnel text | Yes |
| `maneuverSub` | Turn-by-turn subtitle / algorithm note | Yes |
| `metricSpeed` | Digital speedometer (km/h) | Yes |
| `speedSource` | Speed source indicator (ZUPT / GNSS / DR) | Yes |
| `metricDrift` | Measured drift percentage (`< 10% PASS`)| Yes |
| `driftStatus` | Badge showing drift target status | Yes |
| `metricDuration` | Elapsed seconds in tunnel outage | Yes |
| `metricCrossTrack`| Lateral road centerline offset (m) | Yes |
| `chipNhc` | Non-Holonomic constraint chip | Yes |
| `chipMap` | HMM map matching constraint chip | Yes |
| `chipZupt` | Zero-Velocity stationary clamp chip | Yes |
| `routePath` | SVG road trajectory polyline | Keep as SVG `<path>` |
| `vehicleGroup` | Dynamic vehicle cursor SVG group | Keep inside `<svg>` |

---

## 🌿 Standard Git Workflow for Krushna

Follow these steps to work smoothly without merge conflicts:

### 1. Create your feature branch
```bash
git checkout -b frontend/krushna-ui
```

### 2. Make your frontend improvements
Edit `web-demo/index.html`, `web-demo/styles.css`, or `web-demo/app.js`. Refresh your browser at `http://localhost:8080/index.html` to review.

### 3. Run the safety guard
```bash
python scripts/check_frontend.py
```

### 4. Commit and push
```bash
git add web-demo/
git commit -m "feat(ui): redesign navigation dashboard and mobile typography"
git push -u origin frontend/krushna-ui
```

### 5. Create a Pull Request on GitHub
- Go to GitHub and open a Pull Request from `frontend/krushna-ui` to `master`.
- The automated **ONEFORALL Guard CI** will automatically run `ofa guard`, `pytest`, and `release_check.py` to verify your PR.
- **@FreakyAdy** will review and merge it cleanly into `master`!

---

*Happy coding, Krushna! Let's win Smart India Hackathon 2026! 🚀*
