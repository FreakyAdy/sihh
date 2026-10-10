#!/usr/bin/env python3
"""Zero-dependency Live Sensor Bridge for Real-Device Judge Demonstrations.

Serves the web demo and acts as a real-time SSE (Server-Sent Events) broker
between a smartphone (held by the judge or presenter) and the laptop dashboard.

When the judge turns off location on the phone, the dashboard immediately
switches to live physical dead-reckoning fusion driven by the phone's IMU.

Usage:
    python scripts/live_sensor_bridge.py [--port 8080]
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import sys
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# Reconfigure stdout for utf-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DEMO_DIR = REPO_ROOT / "web-demo"
ROVER_WEB_DIR = REPO_ROOT / "rover" / "web"

# Global client subscribers for SSE stream
SUBSCRIBERS: list[queue.Queue] = []
SUBSCRIBERS_LOCK = threading.Lock()

# Latest broadcast state
LATEST_STATE: dict = {
    "timestamp": time.time(),
    "has_location": True,
    "location": None,
    "accel": {"x": 0.0, "y": 0.0, "z": 0.0},
    "gyro": {"yaw_deg": 0.0, "rate_rps": 0.0},
    "mock_outage": False,
}


def get_local_ip() -> str:
    """Detects local LAN IP address for phone connectivity."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connecting to a public address (doesn't send packets) to discover local route
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def broadcast_event(data: dict) -> None:
    """Broadcasts a telemetry event to all active SSE browser connections."""
    payload = f"data: {json.dumps(data)}\n\n".encode("utf-8")
    with SUBSCRIBERS_LOCK:
        dead = []
        for q in SUBSCRIBERS:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for d in dead:
            SUBSCRIBERS.remove(d)


class LiveBridgeHandler(SimpleHTTPRequestHandler):
    """Handles static web files, SSE telemetry streaming, and phone sensor ingestion."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_DEMO_DIR), **kwargs)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/sensor":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                # Update latest state
                global LATEST_STATE
                LATEST_STATE = data
                broadcast_event(data)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        elif parsed.path == "/api/outage":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                mock_outage = bool(data.get("mock_outage", False))
                LATEST_STATE["mock_outage"] = mock_outage
                broadcast_event({"type": "outage_toggle", "mock_outage": mock_outage})
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"mock_outage": mock_outage}).encode("utf-8"))
            except Exception as e:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/stream":
            # Server-Sent Events (SSE) endpoint
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            q: queue.Queue = queue.Queue(maxsize=100)
            with SUBSCRIBERS_LOCK:
                SUBSCRIBERS.append(q)

            # Send initial state
            init_payload = f"data: {json.dumps(LATEST_STATE)}\n\n".encode("utf-8")
            self.wfile.write(init_payload)
            self.wfile.flush()

            try:
                while True:
                    try:
                        msg = q.get(timeout=20.0)
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive heartbeat comment
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                with SUBSCRIBERS_LOCK:
                    if q in SUBSCRIBERS:
                        SUBSCRIBERS.remove(q)
        elif parsed.path == "/api/status":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "subscribers": len(SUBSCRIBERS),
                "latest_timestamp": LATEST_STATE.get("timestamp"),
                "has_location": LATEST_STATE.get("has_location"),
            }).encode("utf-8"))
        elif parsed.path in ("/", "/rover", "/agyaan", "/agyaan_hud.html"):
            hud_path = ROVER_WEB_DIR / "agyaan_hud.html"
            data = hud_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif parsed.path == "/agyaan_hud.css":
            css_path = ROVER_WEB_DIR / "agyaan_hud.css"
            data = css_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif parsed.path == "/agyaan_hud.js":
            js_path = ROVER_WEB_DIR / "agyaan_hud.js"
            data = js_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif parsed.path in ("/earth", "/earth.html"):
            earth_path = WEB_DEMO_DIR / "index.html"
            data = earth_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif parsed.path in ("/idr-navigation.apk", "/download/apk", "/app.apk"):
            apk_path = REPO_ROOT / "idr-navigation.apk"
            if not apk_path.is_file():
                apk_path = REPO_ROOT / "mobile" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
            if apk_path.is_file():
                data = apk_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/vnd.android.package-archive")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", 'attachment; filename="idr-navigation.apk"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                self.wfile.write(b"APK not found")
        else:
            # Serve regular static files from web-demo/
            super().do_GET()

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/rover", "/agyaan", "/agyaan_hud.html"):
            hud_path = ROVER_WEB_DIR / "agyaan_hud.html"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(hud_path.stat().st_size))
            self.end_headers()
        elif parsed.path == "/agyaan_hud.css":
            css_path = ROVER_WEB_DIR / "agyaan_hud.css"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(css_path.stat().st_size))
            self.end_headers()
        elif parsed.path == "/agyaan_hud.js":
            js_path = ROVER_WEB_DIR / "agyaan_hud.js"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(js_path.stat().st_size))
            self.end_headers()
        elif parsed.path in ("/earth", "/earth.html"):
            earth_path = WEB_DEMO_DIR / "index.html"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(earth_path.stat().st_size))
            self.end_headers()
        elif parsed.path in ("/idr-navigation.apk", "/download/apk", "/app.apk"):
            apk_path = REPO_ROOT / "idr-navigation.apk"
            if not apk_path.is_file():
                apk_path = REPO_ROOT / "mobile" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
            if apk_path.is_file():
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/vnd.android.package-archive")
                self.send_header("Content-Length", str(apk_path.stat().st_size))
                self.send_header("Content-Disposition", 'attachment; filename="idr-navigation.apk"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
            else:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
        else:
            super().do_HEAD()

    def do_OPTIONS(self) -> None:
        """Handles CORS preflight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IDR Live Sensor Bridge: Zero-dependency real device streamer for hackathon judges."
    )
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    args = parser.parse_args()

    local_ip = get_local_ip()
    port = args.port

    server = ThreadingHTTPServer(("0.0.0.0", port), LiveBridgeHandler)

    print("=" * 65)
    print("  🚀 IDR DUAL-DOMAIN MISSION CONTROL — LIVE DEMO")
    print("=" * 65)
    print(f"  🌕 AgYaan Lunar Rover HUD  : http://localhost:{port}/")
    print(f"  🌍 Earth Vehicle Nav (PS)  : http://localhost:{port}/index.html")
    print(f"  📲 Install Android APK     : http://{local_ip}:{port}/idr-navigation.apk")
    print(f"  📱 Phone Web Streamer      : http://{local_ip}:{port}/phone-streamer.html")
    print("=" * 65)
    print("  HOW TO RUN THE LIVE DEMO WITH THE JUDGE:")
    print("  1. Presenter default: Open http://localhost:8080/ for AgYaan 3D Rover HUD.")
    print("  2. When judges ask about Problem Statement 26168 / road vehicles:")
    print("     Click 'Earth Vehicle Nav (PS 26168)' in the top bar to show 1km tunnel outage!")
    print("  3. On phone over Wi-Fi, download APK: http://{local_ip}:{port}/idr-navigation.apk")
    print("=" * 65)
    print("Press Ctrl+C to stop the bridge server.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Live Sensor Bridge. Goodbye!")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
