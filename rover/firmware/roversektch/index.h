#pragma once

const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>AgYaan — Autonomous Lunar Exploration Rover HUD</title>
  <style>
    :root {
      --bg: #07090e;
      --card: rgba(15, 23, 42, 0.85);
      --border: rgba(56, 189, 248, 0.2);
      --neon-blue: #38bdf8;
      --neon-cyan: #06b6d4;
      --neon-amber: #f59e0b;
      --neon-red: #ef4444;
      --neon-green: #10b981;
      --text: #f8fafc;
      --text-dim: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
    body { background: var(--bg); color: var(--text); padding: 12px; }
    
    header {
      display: flex; justify-content: space-between; align-items: center;
      padding: 12px 16px; background: var(--card); border: 1px solid var(--border);
      border-radius: 12px; margin-bottom: 12px; backdrop-filter: blur(10px);
    }
    .brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 18px; letter-spacing: 1px; color: var(--neon-cyan); }
    .badge { padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; background: rgba(56, 189, 248, 0.15); color: var(--neon-blue); border: 1px solid var(--border); }
    
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
    @media(max-width: 900px) { .grid { grid-template-columns: 1fr; } }
    
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px; position: relative; }
    .card-title { font-size: 12px; font-weight: 700; letter-spacing: 1.5px; color: var(--text-dim); text-transform: uppercase; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
    
    /* Dual Haz-Cams */
    .cam-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .cam-box { position: relative; border-radius: 8px; overflow: hidden; background: #000; aspect-ratio: 4/3; border: 1px solid rgba(255,255,255,0.1); }
    .cam-box img { width: 100%; height: 100%; object-fit: cover; }
    .cam-tag { position: absolute; top: 6px; left: 6px; background: rgba(0,0,0,0.7); font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 700; color: var(--neon-cyan); }
    
    /* 3D Isometric Canvas */
    #isoCanvas { width: 100%; height: 280px; background: radial-gradient(circle at center, #0f172a 0%, #030712 100%); border-radius: 8px; border: 1px solid rgba(56, 189, 248, 0.15); }
    
    /* Telemetry Tiles */
    .telemetry-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 10px; }
    .tile { background: rgba(2, 6, 23, 0.6); padding: 8px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06); text-align: center; }
    .tile-val { font-size: 18px; font-weight: 800; color: var(--neon-blue); }
    .tile-lbl { font-size: 10px; color: var(--text-dim); margin-top: 2px; }
    
    /* Control Deck */
    .dpad-container { display: flex; flex-direction: column; align-items: center; gap: 6px; margin: 12px 0; }
    .dpad-row { display: flex; gap: 6px; }
    .btn { background: #1e293b; color: #fff; border: 1px solid #334155; padding: 12px 20px; border-radius: 8px; font-size: 14px; font-weight: 700; cursor: pointer; transition: 0.15s; }
    .btn:active { background: var(--neon-cyan); color: #000; transform: scale(0.96); }
    .btn.danger { background: rgba(239, 68, 68, 0.2); border-color: var(--neon-red); color: var(--neon-red); }
    .btn.action { background: rgba(16, 185, 129, 0.2); border-color: var(--neon-green); color: var(--neon-green); }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <span>🌕</span> AgYaan COMMAND HUD
    </div>
    <div style="display: flex; gap: 8px; align-items: center;">
      <span class="badge" id="modeBadge">MODE: MANUAL</span>
      <span class="badge" id="connBadge" style="color: var(--neon-green);">ONLINE</span>
    </div>
  </header>

  <div class="grid">
    <!-- Dual Haz-Cams View -->
    <div class="card">
      <div class="card-title">
        <span>Dual Stereoscopic Haz-Cams</span>
        <span style="color: var(--neon-cyan);">60 FPS Sub-50ms</span>
      </div>
      <div class="cam-grid">
        <div class="cam-box">
          <div class="cam-tag">PORT HAZ-CAM (:81)</div>
          <img id="portCam" src="http://192.168.204.228:81/stream" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'320\' height=\'240\'><rect fill=\'%230b0f19\' width=\'320\' height=\'240\'/><text fill=\'%2338bdf8\' x=\'50%25\' y=\'50%25\' dominant-baseline=\'middle\' text-anchor=\'middle\' font-size=\'14\' font-family=\'monospace\'>PORT HAZ-CAM (OFFLINE)</text></svg>'">
        </div>
        <div class="cam-box">
          <div class="cam-tag">STARBOARD HAZ-CAM (:81)</div>
          <img id="starCam" src="http://192.168.204.192:81/stream" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'320\' height=\'240\'><rect fill=\'%230b0f19\' width=\'320\' height=\'240\'/><text fill=\'%2338bdf8\' x=\'50%25\' y=\'50%25\' dominant-baseline=\'middle\' text-anchor=\'middle\' font-size=\'14\' font-family=\'monospace\'>STARBOARD HAZ-CAM (OFFLINE)</text></svg>'">
        </div>
      </div>
      <div class="telemetry-row">
        <div class="tile"><div class="tile-val" id="valLidar">--</div><div class="tile-lbl">LiDAR (cm)</div></div>
        <div class="tile"><div class="tile-val" id="valHeading">0°</div><div class="tile-lbl">MPU6050 Yaw</div></div>
        <div class="tile"><div class="tile-val" id="valPoseX">0.0</div><div class="tile-lbl">X Odom (cm)</div></div>
        <div class="tile"><div class="tile-val" id="valPoseY">0.0</div><div class="tile-lbl">Y Odom (cm)</div></div>
      </div>
    </div>

    <!-- 3D Isometric Lunar Hazard Map -->
    <div class="card">
      <div class="card-title">
        <span>Isometric 3D Lunar Hazard Map</span>
        <span style="color: var(--neon-amber);">TF-LiDAR Scan Active</span>
      </div>
      <canvas id="isoCanvas" width="480" height="280"></canvas>
      
      <!-- Teleoperation Controls -->
      <div class="dpad-container">
        <button class="btn" onclick="sendCmd('forward')">▲ FWD</button>
        <div class="dpad-row">
          <button class="btn" onclick="sendCmd('left')">◀ PIVOT L</button>
          <button class="btn danger" onclick="sendCmd('stop')">■ HALT</button>
          <button class="btn" onclick="sendCmd('right')">PIVOT R ▶</button>
        </div>
        <div class="dpad-row">
          <button class="btn" onclick="sendCmd('reverse')">▼ REV</button>
          <button class="btn action" onclick="toggleAuto()">SCAN &amp; BYPASS</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let telemetry = { x_cm: 0, y_cm: 0, heading_deg: 0, lidar_cm: 85, mode: "MANUAL" };
    let breadcrumbs = [];

    function sendCmd(cmd) {
      fetch('/cmd?cmd=' + cmd).catch(() => {});
    }

    function toggleAuto() {
      const target = (telemetry.mode === 'AUTONOMOUS') ? 'manual' : 'auto';
      sendCmd(target);
    }

    function fetchTelemetry() {
      fetch('/telemetry')
        .then(res => res.json())
        .then(data => {
          telemetry = data;
          document.getElementById('valLidar').innerText = data.lidar_cm;
          document.getElementById('valHeading').innerText = Math.round(data.heading_deg) + '°';
          document.getElementById('valPoseX').innerText = data.x_cm.toFixed(1);
          document.getElementById('valPoseY').innerText = data.y_cm.toFixed(1);
          document.getElementById('modeBadge').innerText = 'MODE: ' + data.mode;
          
          breadcrumbs.push({ x: data.x_cm, y: data.y_cm });
          if (breadcrumbs.length > 120) breadcrumbs.shift();
        })
        .catch(() => {});
    }
    setInterval(fetchTelemetry, 100);

    // 3D Isometric Canvas Renderer
    const canvas = document.getElementById('isoCanvas');
    const ctx = canvas.getContext('2d');

    function toIso(x, y, z = 0) {
      const cx = canvas.width / 2;
      const cy = canvas.height / 2 + 30;
      const scale = 1.2;
      const isoX = cx + (x - y) * 0.866 * scale;
      const isoY = cy + (x + y) * 0.5 * scale - z * scale;
      return { x: isoX, y: isoY };
    }

    function render3DMap() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw Isometric Grid
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)';
      ctx.lineWidth = 1;
      for (let i = -100; i <= 100; i += 20) {
        let p1 = toIso(i, -100); let p2 = toIso(i, 100);
        ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
        let p3 = toIso(-100, i); let p4 = toIso(100, i);
        ctx.beginPath(); ctx.moveTo(p3.x, p3.y); ctx.lineTo(p4.x, p4.y); ctx.stroke();
      }

      // Draw Trajectory Breadcrumb Trail
      if (breadcrumbs.length > 1) {
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        for (let i = 0; i < breadcrumbs.length; i++) {
          let pt = toIso(breadcrumbs[i].x, breadcrumbs[i].y);
          if (i === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.stroke();
      }

      // Draw Rover Posture
      const rPos = toIso(telemetry.x_cm, telemetry.y_cm, 6);
      ctx.fillStyle = '#38bdf8';
      ctx.beginPath();
      ctx.arc(rPos.x, rPos.y, 8, 0, Math.PI * 2);
      ctx.fill();

      // Heading and LiDAR Cone
      const rad = (telemetry.heading_deg - 90) * Math.PI / 180;
      const fwdX = telemetry.x_cm + Math.cos(rad) * (telemetry.lidar_cm || 40);
      const fwdY = telemetry.y_cm + Math.sin(rad) * (telemetry.lidar_cm || 40);
      const lPos = toIso(fwdX, fwdY);

      // LiDAR Cone
      ctx.fillStyle = 'rgba(245, 158, 11, 0.18)';
      ctx.beginPath();
      ctx.moveTo(rPos.x, rPos.y);
      ctx.lineTo(lPos.x - 14, lPos.y);
      ctx.lineTo(lPos.x + 14, lPos.y);
      ctx.closePath();
      ctx.fill();

      // 3D Obstacle Hazard Pillar
      if (telemetry.lidar_cm > 0 && telemetry.lidar_cm < 40) {
        ctx.strokeStyle = '#ef4444';
        ctx.fillStyle = 'rgba(239, 68, 68, 0.4)';
        ctx.lineWidth = 2;
        let base = toIso(fwdX, fwdY, 0);
        let top = toIso(fwdX, fwdY, 24);
        ctx.beginPath(); ctx.moveTo(base.x, base.y); ctx.lineTo(top.x, top.y); ctx.stroke();
        ctx.beginPath(); ctx.arc(top.x, top.y, 5, 0, Math.PI * 2); ctx.fill();
      }

      requestAnimationFrame(render3DMap);
    }
    render3DMap();
  </script>
</body>
</html>
)rawliteral";
