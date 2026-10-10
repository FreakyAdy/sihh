/* =========================================================================
 *  AgYaan Command HUD — Master Logic & 3D Isometric Hazard Renderer
 * ========================================================================= */

(function () {
  "use strict";

  // System State
  const state = {
    mode: "MANUAL", // MANUAL, AUTONOMOUS, SCAN_BYPASS
    dataSource: "SIMULATION", // SIMULATION or LIVE
    espIp: "192.168.4.1",
    pose: { x: 0, y: 0, heading: 0 },
    speed: 0,
    lidarDist: 85,
    lidarStrength: 1420,
    ticksL: 0,
    ticksR: 0,
    gyroRate: 0,
    breadcrumbs: [],
    obstacles: [
      { x: 30, y: 70, radius: 14, height: 28 },
      { x: -50, y: 120, radius: 18, height: 35 },
      { x: 10, y: 180, radius: 22, height: 42 },
      { x: 65, y: -40, radius: 12, height: 22 },
      { x: -40, y: -80, radius: 16, height: 30 }
    ],
    autonomousStep: 0,
    autonomousTimer: 0
  };

  // DOM Elements
  const canvas = document.getElementById("iso3dCanvas");
  const ctx = canvas.getContext("2d");
  const portCanvas = document.getElementById("portSimCanvas");
  const portCtx = portCanvas.getContext("2d");
  const starCanvas = document.getElementById("starSimCanvas");
  const starCtx = starCanvas.getContext("2d");

  const valLidarDist = document.getElementById("valLidarDist");
  const valLidarStatus = document.getElementById("valLidarStatus");
  const valHeading = document.getElementById("valHeading");
  const valGyroRate = document.getElementById("valGyroRate");
  const valTicksL = document.getElementById("valTicksL");
  const valTicksR = document.getElementById("valTicksR");
  const valSpeed = document.getElementById("valSpeed");
  const valZuptTag = document.getElementById("valZuptTag");
  const poseReadout = document.getElementById("poseReadout");
  const hazardAlertBanner = document.getElementById("hazardAlertBanner");
  const autoStatusBadge = document.getElementById("autoStatusBadge");
  const connStatusTag = document.getElementById("connStatusTag");
  const connStatusText = document.getElementById("connStatusText");

  // Arch Modal Elements
  const archModal = document.getElementById("archModal");
  const openArchModalBtn = document.getElementById("openArchModalBtn");
  const closeArchModalBtn = document.getElementById("closeArchModalBtn");

  openArchModalBtn.addEventListener("click", () => archModal.classList.add("open"));
  closeArchModalBtn.addEventListener("click", () => archModal.classList.remove("open"));
  archModal.addEventListener("click", (e) => {
    if (e.target === archModal) archModal.classList.remove("open");
  });

  // Data Source Buttons
  const srcSimBtn = document.getElementById("srcSimBtn");
  const srcLiveBtn = document.getElementById("srcLiveBtn");

  srcSimBtn.addEventListener("click", () => {
    state.dataSource = "SIMULATION";
    srcSimBtn.classList.add("active");
    srcLiveBtn.classList.remove("active");
    connStatusText.innerText = "SIMULATED TESTBED";
    connStatusTag.style.color = "var(--green-neon)";
  });

  srcLiveBtn.addEventListener("click", () => {
    state.dataSource = "LIVE";
    srcLiveBtn.classList.add("active");
    srcSimBtn.classList.remove("active");
    connStatusText.innerText = "CONNECTING ESP32...";
    connStatusTag.style.color = "var(--amber-neon)";
  });

  // -------------------------------------------------------------------------
  // 1. ISOMETRIC 3D TRANSFORMATION MATH
  // -------------------------------------------------------------------------
  function toIso(x, y, z = 0) {
    const cx = canvas.width / 2;
    const cy = canvas.height / 2 + 60;
    const scale = 1.6;
    // 30-degree isometric projection matrix
    const isoX = cx + (x - y) * 0.866 * scale;
    const isoY = cy + (x + y) * 0.5 * scale - z * scale;
    return { x: isoX, y: isoY };
  }

  // -------------------------------------------------------------------------
  // 2. SIMULATION DYNAMICS & KINEMATICS
  // -------------------------------------------------------------------------
  let targetVelocity = 0; // cm/s
  let targetYawRate = 0;   // deg/s

  function updateSimulation(dt) {
    if (state.dataSource !== "SIMULATION") return;

    if (state.mode === "AUTONOMOUS") {
      runAutonomousScanAndBypass(dt);
    }

    // Kinematic integration
    state.pose.heading += targetYawRate * dt;
    if (state.pose.heading >= 360) state.pose.heading -= 360;
    if (state.pose.heading < 0) state.pose.heading += 360;

    const rad = (state.pose.heading - 90) * (Math.PI / 180);
    const dx = Math.cos(rad) * targetVelocity * dt;
    const dy = Math.sin(rad) * targetVelocity * dt;

    state.pose.x += dx;
    state.pose.y += dy;
    state.speed = targetVelocity;
    state.gyroRate = targetYawRate;

    // Encoder ticks calculation (330 PPR, 6.5 cm diameter = 20.42 cm circum)
    const cmPerTick = 20.42 / 330.0;
    const dTicks = Math.round((targetVelocity * dt) / cmPerTick);
    state.ticksL += dTicks;
    state.ticksR += dTicks;

    // Record breadcrumbs
    if (Math.abs(targetVelocity) > 0.1 || Math.abs(targetYawRate) > 0.1) {
      state.breadcrumbs.push({ x: state.pose.x, y: state.pose.y });
      if (state.breadcrumbs.length > 200) state.breadcrumbs.shift();
    }

    // Compute Raycast TF-LiDAR distance to closest obstacle in forward cone
    let minDist = 180; // max range cm
    const headingRad = (state.pose.heading - 90) * (Math.PI / 180);

    state.obstacles.forEach((obs) => {
      const relX = obs.x - state.pose.x;
      const relY = obs.y - state.pose.y;
      const distToCenter = Math.hypot(relX, relY);

      // Angle between forward ray and obstacle center
      const angleToObs = Math.atan2(relY, relX);
      let angleDiff = Math.abs(angleToObs - headingRad);
      while (angleDiff > Math.PI) angleDiff = Math.abs(angleDiff - 2 * Math.PI);

      if (angleDiff < 0.25) { // inside 15-degree LiDAR FOV cone
        const surfaceDist = Math.max(5, distToCenter - obs.radius);
        if (surfaceDist < minDist) {
          minDist = surfaceDist;
        }
      }
    });

    state.lidarDist = Math.round(minDist);
  }

  // -------------------------------------------------------------------------
  // 3. AUTONOMOUS SCAN-AND-BYPASS BEHAVIOR TREE
  // -------------------------------------------------------------------------
  function runAutonomousScanAndBypass(dt) {
    state.autonomousTimer += dt;

    switch (state.autonomousStep) {
      case 0: // Forward Crawl
        targetVelocity = 14;
        targetYawRate = 0;
        if (state.lidarDist < 30) {
          // Hazard triggered!
          targetVelocity = 0;
          state.autonomousStep = 1;
          state.autonomousTimer = 0;
        }
        break;

      case 1: // Halt & Scan Right
        targetVelocity = 0;
        targetYawRate = 35; // pivot right
        if (state.autonomousTimer > 1.2) {
          state.autonomousStep = 2;
          state.autonomousTimer = 0;
        }
        break;

      case 2: // Scan Left
        targetVelocity = 0;
        targetYawRate = -35; // pivot left
        if (state.autonomousTimer > 2.4) {
          state.autonomousStep = 3;
          state.autonomousTimer = 0;
        }
        break;

      case 3: // Re-aim right to bypass flank
        targetVelocity = 0;
        targetYawRate = 35;
        if (state.autonomousTimer > 1.2) {
          state.autonomousStep = 4;
          state.autonomousTimer = 0;
        }
        break;

      case 4: // Advance past flank
        targetVelocity = 16;
        targetYawRate = 0;
        if (state.autonomousTimer > 2.2) {
          // Return to original mission heading
          state.autonomousStep = 0;
          state.autonomousTimer = 0;
        }
        break;
    }
  }

  // -------------------------------------------------------------------------
  // 4. RENDER 3D ISOMETRIC LUNAR HAZARD MAP
  // -------------------------------------------------------------------------
  function render3dMap() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Draw Isometric Terrain Mesh
    ctx.strokeStyle = "rgba(56, 189, 248, 0.12)";
    ctx.lineWidth = 1;

    for (let x = -140; x <= 140; x += 20) {
      const p1 = toIso(x, -140);
      const p2 = toIso(x, 140);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }
    for (let y = -140; y <= 140; y += 20) {
      const p1 = toIso(-140, y);
      const p2 = toIso(140, y);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }

    // 2. Draw Lunar Crater Rings
    ctx.strokeStyle = "rgba(148, 163, 184, 0.18)";
    ctx.lineWidth = 1.5;
    [-60, 40].forEach((cx) => {
      [50, -40].forEach((cy) => {
        const center = toIso(cx, cy);
        ctx.beginPath();
        ctx.ellipse(center.x, center.y, 28, 16, 0, 0, Math.PI * 2);
        ctx.stroke();
      });
    });

    // 3. Draw Trajectory Breadcrumb Trail
    if (state.breadcrumbs.length > 1) {
      ctx.strokeStyle = "rgba(56, 189, 248, 0.9)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      for (let i = 0; i < state.breadcrumbs.length; i++) {
        const pt = toIso(state.breadcrumbs[i].x, state.breadcrumbs[i].y, 2);
        if (i === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.stroke();
    }

    // 4. Draw 3D Lunar Hazard Obstacles / Rocks
    state.obstacles.forEach((obs) => {
      const base = toIso(obs.x, obs.y, 0);
      const top = toIso(obs.x, obs.y, obs.height);

      // Check if inside forward cone to light up in Red
      const relX = obs.x - state.pose.x;
      const relY = obs.y - state.pose.y;
      const headingRad = (state.pose.heading - 90) * (Math.PI / 180);
      const angleToObs = Math.atan2(relY, relX);
      let angleDiff = Math.abs(angleToObs - headingRad);
      while (angleDiff > Math.PI) angleDiff = Math.abs(angleDiff - 2 * Math.PI);

      const isScanned = angleDiff < 0.28 && Math.hypot(relX, relY) < 140;

      // Base footprint
      ctx.fillStyle = isScanned ? "rgba(239, 68, 68, 0.35)" : "rgba(30, 41, 59, 0.6)";
      ctx.beginPath();
      ctx.ellipse(base.x, base.y, obs.radius * 1.2, obs.radius * 0.7, 0, 0, Math.PI * 2);
      ctx.fill();

      // Vertical 3D Extrusion Pillars
      ctx.strokeStyle = isScanned ? "#ef4444" : "#475569";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(base.x - obs.radius, base.y);
      ctx.lineTo(top.x - obs.radius * 0.8, top.y);
      ctx.moveTo(base.x + obs.radius, base.y);
      ctx.lineTo(top.x + obs.radius * 0.8, top.y);
      ctx.moveTo(base.x, base.y);
      ctx.lineTo(top.x, top.y);
      ctx.stroke();

      // Top Hazard Cap
      ctx.fillStyle = isScanned ? "#ef4444" : "#64748b";
      ctx.beginPath();
      ctx.ellipse(top.x, top.y, obs.radius * 0.8, obs.radius * 0.45, 0, 0, Math.PI * 2);
      ctx.fill();
    });

    // 5. Draw Target Waypoint Flag
    const targetPos = toIso(20, 160, 0);
    const targetFlagTop = toIso(20, 160, 32);
    ctx.strokeStyle = "#10b981";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(targetPos.x, targetPos.y);
    ctx.lineTo(targetFlagTop.x, targetFlagTop.y);
    ctx.stroke();

    ctx.fillStyle = "#10b981";
    ctx.beginPath();
    ctx.moveTo(targetFlagTop.x, targetFlagTop.y);
    ctx.lineTo(targetFlagTop.x + 18, targetFlagTop.y + 6);
    ctx.lineTo(targetFlagTop.x, targetFlagTop.y + 12);
    ctx.closePath();
    ctx.fill();

    // 6. Draw Rover Chassis & Directional Arrow
    const roverPos = toIso(state.pose.x, state.pose.y, 6);

    // Rover Ground Shadow
    const shadowPos = toIso(state.pose.x, state.pose.y, 0);
    ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
    ctx.beginPath();
    ctx.ellipse(shadowPos.x, shadowPos.y, 16, 9, 0, 0, Math.PI * 2);
    ctx.fill();

    // Rover 3D Body Box
    ctx.fillStyle = "#0284c7";
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(roverPos.x, roverPos.y, 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Inner Core Glow
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(roverPos.x, roverPos.y, 4, 0, Math.PI * 2);
    ctx.fill();

    // 7. Draw TF-LiDAR Raycast Beam & Warning Cone
    const rad = (state.pose.heading - 90) * (Math.PI / 180);
    const fwdDist = Math.max(15, state.lidarDist);
    const fwdX = state.pose.x + Math.cos(rad) * fwdDist;
    const fwdY = state.pose.y + Math.sin(rad) * fwdDist;
    const lidarTarget = toIso(fwdX, fwdY, 4);

    // LiDAR Cone Field of View
    const leftAngle = rad - 0.22;
    const rightAngle = rad + 0.22;
    const leftX = state.pose.x + Math.cos(leftAngle) * fwdDist;
    const leftY = state.pose.y + Math.sin(leftAngle) * fwdDist;
    const rightX = state.pose.x + Math.cos(rightAngle) * fwdDist;
    const rightY = state.pose.y + Math.sin(rightAngle) * fwdDist;

    const leftPt = toIso(leftX, leftY, 4);
    const rightPt = toIso(rightX, rightY, 4);

    const isHazard = state.lidarDist < 30;
    ctx.fillStyle = isHazard ? "rgba(239, 68, 68, 0.25)" : "rgba(245, 158, 11, 0.16)";
    ctx.beginPath();
    ctx.moveTo(roverPos.x, roverPos.y);
    ctx.lineTo(leftPt.x, leftPt.y);
    ctx.lineTo(rightPt.x, rightPt.y);
    ctx.closePath();
    ctx.fill();

    // Central Laser Ray
    ctx.strokeStyle = isHazard ? "#ef4444" : "#f59e0b";
    ctx.lineWidth = isHazard ? 3 : 1.5;
    ctx.beginPath();
    ctx.moveTo(roverPos.x, roverPos.y);
    ctx.lineTo(lidarTarget.x, lidarTarget.y);
    ctx.stroke();

    // Laser Dot at Hit Point
    ctx.fillStyle = isHazard ? "#ef4444" : "#f59e0b";
    ctx.beginPath();
    ctx.arc(lidarTarget.x, lidarTarget.y, isHazard ? 6 : 4, 0, Math.PI * 2);
    ctx.fill();
  }

  // -------------------------------------------------------------------------
  // 5. SYNTHETIC DUAL HAZ-CAM SURFACE GENERATORS
  // -------------------------------------------------------------------------
  let camFrame = 0;

  function renderSimulatedCams() {
    camFrame++;

    [
      { ctx: portCtx, label: "PORT HAZ-CAM (LEFT)", offset: -6 },
      { ctx: starCtx, label: "STARBOARD HAZ-CAM (RIGHT)", offset: 6 }
    ].forEach(({ ctx: c, offset }) => {
      // Dark lunar sky & dusty regolith horizon
      const grad = c.createLinearGradient(0, 0, 0, 200);
      grad.addColorStop(0, "#030712");
      grad.addColorStop(0.42, "#0b1120");
      grad.addColorStop(0.43, "#1e293b");
      grad.addColorStop(1, "#334155");
      c.fillStyle = grad;
      c.fillRect(0, 0, 320, 200);

      // Craters & boulders on ground
      c.fillStyle = "#1e293b";
      c.beginPath();
      c.ellipse(160 + offset * 2, 120, 90, 22, 0, 0, Math.PI * 2);
      c.fill();

      // Approaching hazard rock if within range
      if (state.lidarDist < 70) {
        const rockSize = Math.max(8, (80 - state.lidarDist) * 0.9);
        c.fillStyle = state.lidarDist < 30 ? "rgba(239, 68, 68, 0.7)" : "#475569";
        c.beginPath();
        c.ellipse(160 + offset, 140, rockSize * 1.2, rockSize * 0.8, 0, 0, Math.PI * 2);
        c.fill();
      }

      // Optical scan raster sweep
      const scanY = (camFrame * 2.5) % 200;
      c.strokeStyle = "rgba(56, 189, 248, 0.45)";
      c.lineWidth = 1.5;
      c.beginPath();
      c.moveTo(0, scanY);
      c.lineTo(320, scanY);
      c.stroke();
    });
  }

  // -------------------------------------------------------------------------
  // 6. UI HUD UPDATES
  // -------------------------------------------------------------------------
  function updateHudGauges() {
    valLidarDist.innerText = state.lidarDist;
    valHeading.innerText = state.pose.heading.toFixed(1);
    valGyroRate.innerText = `Rate: ${state.gyroRate.toFixed(1)} °/s`;
    valTicksL.innerText = state.ticksL;
    valTicksR.innerText = state.ticksR;
    valSpeed.innerText = Math.abs(state.speed).toFixed(1);

    if (Math.abs(state.speed) < 0.1) {
      valZuptTag.innerText = "ZUPT Clamping Active";
      valZuptTag.style.color = "var(--green-neon)";
    } else {
      valZuptTag.innerText = "Inertial Integration";
      valZuptTag.style.color = "var(--cyan-neon)";
    }

    poseReadout.innerText = `X: ${state.pose.x.toFixed(1)} cm | Y: ${state.pose.y.toFixed(1)} cm | YAW: ${state.pose.heading.toFixed(1)}°`;

    if (state.lidarDist < 30) {
      valLidarStatus.innerText = "CRITICAL HAZARD (<30 cm)";
      valLidarStatus.style.color = "var(--red-neon)";
      hazardAlertBanner.classList.add("active");
    } else {
      valLidarStatus.innerText = "Clear Ahead (>30 cm)";
      valLidarStatus.style.color = "var(--text-muted)";
      hazardAlertBanner.classList.remove("active");
    }

    autoStatusBadge.innerText = `MODE: ${state.mode}`;
    if (state.mode === "AUTONOMOUS") {
      autoStatusBadge.style.color = "var(--green-neon)";
      autoStatusBadge.style.borderColor = "rgba(16, 185, 129, 0.3)";
    } else {
      autoStatusBadge.style.color = "var(--cyan-neon)";
      autoStatusBadge.style.borderColor = "rgba(56, 189, 248, 0.2)";
    }
  }

  // -------------------------------------------------------------------------
  // 7. TELEOPERATION CONTROLS (D-PAD & KEYBOARD)
  // -------------------------------------------------------------------------
  function setDriveCommand(fwd, turn) {
    if (state.mode === "AUTONOMOUS") return;
    targetVelocity = fwd;
    targetYawRate = turn;

    if (state.dataSource === "LIVE") {
      let cmd = "stop";
      if (fwd > 0) cmd = "forward";
      else if (fwd < 0) cmd = "reverse";
      else if (turn < 0) cmd = "left";
      else if (turn > 0) cmd = "right";

      fetch(`http://${state.espIp}/cmd?cmd=${cmd}`).catch(() => {});
    }
  }

  document.getElementById("btnFwd").addEventListener("mousedown", () => setDriveCommand(22, 0));
  document.getElementById("btnRev").addEventListener("mousedown", () => setDriveCommand(-18, 0));
  document.getElementById("btnLeft").addEventListener("mousedown", () => setDriveCommand(0, -32));
  document.getElementById("btnRight").addEventListener("mousedown", () => setDriveCommand(0, 32));
  document.getElementById("btnStop").addEventListener("click", () => setDriveCommand(0, 0));

  window.addEventListener("mouseup", () => {
    if (state.mode === "MANUAL") setDriveCommand(0, 0);
  });

  // Keyboard binding (Arrow Keys / WASD)
  window.addEventListener("keydown", (e) => {
    if (state.mode === "AUTONOMOUS") return;
    if (e.key === "ArrowUp" || e.key === "w") setDriveCommand(22, 0);
    else if (e.key === "ArrowDown" || e.key === "s") setDriveCommand(-18, 0);
    else if (e.key === "ArrowLeft" || e.key === "a") setDriveCommand(0, -32);
    else if (e.key === "ArrowRight" || e.key === "d") setDriveCommand(0, 32);
    else if (e.key === " ") setDriveCommand(0, 0);
  });

  window.addEventListener("keyup", () => {
    if (state.mode === "MANUAL") setDriveCommand(0, 0);
  });

  // Autonomous Mode Toggle
  const btnToggleAuto = document.getElementById("btnToggleAuto");
  btnToggleAuto.addEventListener("click", () => {
    if (state.mode === "AUTONOMOUS") {
      state.mode = "MANUAL";
      btnToggleAuto.innerText = "⚡ AUTONOMOUS (SCAN & BYPASS)";
      btnToggleAuto.style.background = "rgba(16, 185, 129, 0.2)";
      setDriveCommand(0, 0);
    } else {
      state.mode = "AUTONOMOUS";
      state.autonomousStep = 0;
      state.autonomousTimer = 0;
      btnToggleAuto.innerText = "■ DISENGAGE AUTONOMOUS";
      btnToggleAuto.style.background = "rgba(239, 68, 68, 0.2)";
    }
  });

  // -------------------------------------------------------------------------
  // 8. LIVE TELEMETRY INGESTION LOOP (WHEN ESP32 HARDWARE ONLINE)
  // -------------------------------------------------------------------------
  function pollLiveEsp32() {
    if (state.dataSource !== "LIVE") return;

    fetch(`http://${state.espIp}/telemetry`, { signal: AbortSignal.timeout(600) })
      .then((res) => res.json())
      .then((data) => {
        connStatusText.innerText = "ESP32 CONNECTED";
        connStatusTag.style.color = "var(--green-neon)";

        state.pose.x = data.x_cm || state.pose.x;
        state.pose.y = data.y_cm || state.pose.y;
        state.pose.heading = data.heading_deg || state.pose.heading;
        state.lidarDist = data.lidar_cm || state.lidarDist;
        state.ticksL = data.ticks_l || state.ticksL;
        state.ticksR = data.ticks_r || state.ticksR;
        state.mode = data.mode || state.mode;

        state.breadcrumbs.push({ x: state.pose.x, y: state.pose.y });
        if (state.breadcrumbs.length > 200) state.breadcrumbs.shift();
      })
      .catch(() => {
        connStatusText.innerText = "ESP32 DISCONNECTED";
        connStatusTag.style.color = "var(--red-neon)";
      });
  }
  setInterval(pollLiveEsp32, 100);

  // -------------------------------------------------------------------------
  // 9. ANIMATION ENGINE LOOP
  // -------------------------------------------------------------------------
  let lastTime = performance.now();

  function engineLoop(now) {
    const dt = Math.min(0.1, (now - lastTime) / 1000);
    lastTime = now;

    updateSimulation(dt);
    render3dMap();
    renderSimulatedCams();
    updateHudGauges();

    requestAnimationFrame(engineLoop);
  }

  requestAnimationFrame(engineLoop);
})();
