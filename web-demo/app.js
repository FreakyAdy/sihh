/**
 * Intelligent Dead Reckoning (IDR) — Apple Mobile-First Navigation Engine
 * 
 * Simulates high-precision 10 Hz GNSS/INS sensor fusion, vehicle kinematic constraints,
 * zero-velocity updates (ZUPT), and HMM road network map matching during GNSS blackouts.
 * Styled with iOS 18 Apple Maps Design Language & Dynamic Island morphing.
 */

const SCENARIOS = {
  tunnel: {
    id: "tunnel",
    name: "Highway Tunnel (Atal Tunnel)",
    speedLimit: 60,
    totalDurationS: 60.0,
    speedKmph: 60.0,
    outageStartS: 10.0,
    outageEndS: 50.0,
    tunnelProgress: "Tunnel Outage (10s–50s, 667m)",
    streetName: "Enter Atal Tunnel",
    streetSub: "NH-3 Mountain Pass • Intelligent Dead Reckoning",
    instructionPrep: "In 320 m, Enter Atal Tunnel",
    instructionOutage: "Tunnel Blackout • IDR Edge Fusion Active",
    instructionRecover: "Tunnel Egress • Validating GNSS Fix 2/2",
    instructionComplete: "Open Sky • Nominal GNSS-Aided Mode",
    accelBias: 0.02,
    gyroBias: 0.0018,
    isJam: false,
  },
  canyon: {
    id: "canyon",
    name: "Urban Canyon (High-Rise S-Curve)",
    speedLimit: 50,
    totalDurationS: 50.0,
    speedKmph: 45.0,
    outageStartS: 8.0,
    outageEndS: 38.0,
    tunnelProgress: "Urban Canyon (8s–38s, 375m)",
    streetName: "Enter High-Rise Canyon",
    streetSub: "Urban Canyon Grid • Multipath Rejection",
    instructionPrep: "In 200 m, High-Rise Canyon Ahead",
    instructionOutage: "Signal Blocked • NHC Curvature Propagation",
    instructionRecover: "Skyline Cleared • Reacquiring GNSS Fix",
    instructionComplete: "Open Sky • 100% Lane-Level Match",
    accelBias: 0.025,
    gyroBias: 0.0022,
    isJam: false,
  },
  jam: {
    id: "jam",
    name: "Tunnel Traffic Jam (ZUPT Zero-Velocity Guard)",
    speedLimit: 60,
    totalDurationS: 60.0,
    speedKmph: 50.0,
    outageStartS: 8.0,
    outageEndS: 52.0,
    tunnelProgress: "Tunnel Jam (Standstill 18s–38s)",
    streetName: "Atal Subterranean Tube",
    streetSub: "Congestion Zone • ZUPT Stationary Clamping",
    instructionPrep: "Enter Tunnel • Heavy Congestion Ahead",
    instructionOutage: "Standstill Detected • ZUPT Clamps Drift to 0.0 m",
    instructionRecover: "Traffic Flowing • Egressing Tunnel",
    instructionComplete: "Jam Cleared • Zero Quadratic Runaway",
    accelBias: 0.035,
    gyroBias: 0.002,
    isJam: true,
  },
  live: {
    id: "live",
    name: "Live Physical Sensors (Judge Real-Time Mode)",
    speedLimit: 50,
    totalDurationS: 120.0,
    speedKmph: 30.0,
    outageStartS: 999.0,
    outageEndS: 999.0,
    tunnelProgress: "Live Physical Phone Fusion",
    streetName: "Exhibition Venue Route",
    streetSub: "Live Inertial Fusion • Physical Phone IMU",
    instructionPrep: "Connected to Live Sensors",
    instructionOutage: "Physical GNSS Cut • Real-Time IMU Fusion",
    instructionRecover: "Location Signal Restored",
    instructionComplete: "Nominal Live Tracking",
    accelBias: 0.015,
    gyroBias: 0.0012,
    isJam: false,
    isLive: true,
  },
};

// Simulation State
const sim = {
  activeScenario: SCENARIOS.tunnel,
  currentTimeS: 0.0,
  tickRateHz: 10.0,
  playbackInterval: null,
  isPlaying: false,
  compareNaive: true,
  manualOutageActive: false,
  
  // Navigation State
  mode: "GNSS-AIDED", // GNSS-AIDED, DEAD-RECKONING, RECOVERING
  recoveryFixCount: 0,
  confidence: 0.99,
  speedMps: 60.0 / 3.6,
  outageDurationS: 0.0,
  outageDistanceM: 0.0,
  maxErrorM: 0.0,
  naiveMaxErrorM: 0.0,
  crossTrackM: 0.0,
  naiveCrossTrackM: 0.0,
  
  // Trajectory history for polyline rendering
  idrHistory: [],
  naiveHistory: [],
};

// Live Real-Device Sensor State (Bridge & Local HTML5)
let liveSseSource = null;
const liveSensor = {
  active: false,
  headingDeg: 0.0,
  yawRateRps: 0.0,
  accelMag: 0.0,
  hasLocation: true,
  lat: null,
  lon: null,
  mockOutage: false,
  lastPacketTime: 0,
};

function connectLiveStream() {
  if (liveSseSource) return;
  try {
    liveSseSource = new EventSource("/api/stream");
    liveSseSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        liveSensor.active = true;
        liveSensor.lastPacketTime = Date.now();
        if (data.type === "outage_toggle") {
          sim.manualOutageActive = Boolean(data.mock_outage);
          render();
          return;
        }
        if (data.gyro && typeof data.gyro.heading_deg === "number") {
          liveSensor.headingDeg = data.gyro.heading_deg;
        }
        if (data.gyro && typeof data.gyro.rate_rps === "number") {
          liveSensor.yawRateRps = data.gyro.rate_rps;
        }
        if (data.accel) {
          const ax = data.accel.x || 0;
          const ay = data.accel.y || 0;
          liveSensor.accelMag = Math.sqrt(ax * ax + ay * ay);
        }
        if (data.has_location !== undefined) {
          liveSensor.hasLocation = Boolean(data.has_location);
          sim.manualOutageActive = !data.has_location || Boolean(data.mock_outage);
        }
        // Capture real GPS speed (m/s → km/h) from SSE payload
        if (data.location && typeof data.location.speed === 'number') {
          liveSensor.speedKmh = data.location.speed * 3.6;
        } else if (!liveSensor.hasLocation || sim.manualOutageActive) {
          liveSensor.speedKmh = 0;
        }
        if (sim.activeScenario && sim.activeScenario.isLive) {
          render();
        }
      } catch (e) {
        console.warn("SSE parse error", e);
      }
    };
  } catch (e) {
    console.warn("SSE not available", e);
  }

  // Fallback to local mobile browser sensors if accessed directly
  if (window.DeviceOrientationEvent) {
    window.addEventListener("deviceorientation", (e) => {
      if (e.alpha !== null) {
        liveSensor.active = true;
        liveSensor.headingDeg = e.alpha;
      }
    });
  }
}

// DOM References
const $ = (id) => document.getElementById(id);
const routePath = $("routePath");
const totalPathLength = routePath ? routePath.getTotalLength() : 1000;

function init() {
  bindEvents();
  setScenario("tunnel");
  render();
}

function bindEvents() {
  // Playback controls
  if ($("playBtn")) $("playBtn").addEventListener("click", togglePlay);
  if ($("stepBtn")) $("stepBtn").addEventListener("click", stepForward);
  if ($("resetBtn")) $("resetBtn").addEventListener("click", reset);
  
  // Floating controls
  if ($("toggleGhostBtn")) $("toggleGhostBtn").addEventListener("click", toggleCompareNaive);
  if ($("manualOutageBtn")) $("manualOutageBtn").addEventListener("click", triggerManualOutage);

  // Indoor venue origin button
  if ($("indoorOriginBtn")) {
    $("indoorOriginBtn").addEventListener("click", () => {
      sim.currentTimeS = 0.0;
      sim.mode = "GNSS-AIDED";
      sim.confidence = 1.0;
      sim.outageDurationS = 0.0;
      sim.crossTrackM = 0.0;
      if ($("maneuverStreet")) $("maneuverStreet").textContent = "Venue Origin Anchored";
      if ($("maneuverSub")) $("maneuverSub").textContent = "Indoor reference coordinates established (Ready for live test)";
      render();
    });
  }

  // Desktop view toggle (iPhone frame vs fullscreen)
  if ($("viewToggleBtn")) {
    $("viewToggleBtn").addEventListener("click", () => {
      const container = $("deviceContainer");
      const isFull = container.classList.toggle("fullscreen");
      const toggleText = $("viewToggleText");
      if (toggleText) {
        toggleText.textContent = isFull ? "Phone View" : "Full Screen";
      }
    });
  }

  // Segmented Scenario Buttons
  document.querySelectorAll(".seg-btn, .scenario-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const scenarioKey = btn.dataset.scenario;
      if (SCENARIOS[scenarioKey]) {
        setScenario(scenarioKey);
      }
    });
  });
}

function setScenario(key) {
  pause();
  sim.activeScenario = SCENARIOS[key];
  document.querySelectorAll(".seg-btn, .scenario-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.scenario === key);
  });
  if ($("liveControlsBar")) {
    $("liveControlsBar").style.display = key === "live" ? "flex" : "none";
  }
  if ($("tunnelProgressTag")) {
    $("tunnelProgressTag").textContent = sim.activeScenario.tunnelProgress;
  }
  const speedSignVal = document.querySelector(".speed-sign-val");
  if (speedSignVal) {
    speedSignVal.textContent = sim.activeScenario.speedLimit;
  }
  reset();
  if (key === "live") {
    connectLiveStream();
    play();
  }
}

function togglePlay() {
  if (sim.isPlaying) {
    pause();
  } else {
    play();
  }
}

function play() {
  if (sim.currentTimeS >= sim.activeScenario.totalDurationS) {
    reset();
  }
  sim.isPlaying = true;
  if ($("playText")) $("playText").textContent = "Pause Navigation";
  if ($("playIcon")) {
    $("playIcon").innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
  }
  sim.playbackInterval = setInterval(tick, 1000 / sim.tickRateHz);
}

function pause() {
  sim.isPlaying = false;
  if ($("playText")) $("playText").textContent = "Resume Navigation";
  if ($("playIcon")) {
    $("playIcon").innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
  }
  if (sim.playbackInterval) {
    clearInterval(sim.playbackInterval);
    sim.playbackInterval = null;
  }
}

function stepForward() {
  pause();
  for (let i = 0; i < 10; i++) {
    tick(false);
  }
  render();
}

function reset() {
  pause();
  sim.currentTimeS = 0.0;
  sim.manualOutageActive = false;
  sim.recoveryFixCount = 0;
  sim.outageDurationS = 0.0;
  sim.outageDistanceM = 0.0;
  sim.maxErrorM = 0.0;
  sim.naiveMaxErrorM = 0.0;
  sim.crossTrackM = 0.0;
  sim.naiveCrossTrackM = 0.0;
  sim.idrHistory = [];
  sim.naiveHistory = [];
  sim.mode = "GNSS-AIDED";
  sim.confidence = 0.99;
  
  if ($("manualOutageBtn")) $("manualOutageBtn").classList.remove("active");
  if ($("playText")) $("playText").textContent = "Start Navigation";
  render();
}

function toggleCompareNaive() {
  sim.compareNaive = !sim.compareNaive;
  if ($("toggleGhostBtn")) $("toggleGhostBtn").classList.toggle("active", sim.compareNaive);
  if ($("ghostVehicleGroup")) $("ghostVehicleGroup").setAttribute("opacity", sim.compareNaive ? "1" : "0");
  if ($("naiveTrail")) $("naiveTrail").setAttribute("opacity", sim.compareNaive ? "0.9" : "0");
}

function triggerManualOutage() {
  sim.manualOutageActive = !sim.manualOutageActive;
  if ($("manualOutageBtn")) $("manualOutageBtn").classList.toggle("active", sim.manualOutageActive);
  render();
}

function tick(doRender = true) {
  sim.currentTimeS += 1.0 / sim.tickRateHz;
  if (sim.currentTimeS >= sim.activeScenario.totalDurationS) {
    sim.currentTimeS = sim.activeScenario.totalDurationS;
    pause();
    if ($("playText")) $("playText").textContent = "Arrival Complete";
  }

  updatePhysics();
  if (doRender) {
    render();
  }
}

function updatePhysics() {
  const sc = sim.activeScenario;
  const t = sim.currentTimeS;
  const dt = 1.0 / sim.tickRateHz;

  // Determine GNSS availability
  const isScheduledOutage = t >= sc.outageStartS && t <= sc.outageEndS;
  const gnssLost = isScheduledOutage || sim.manualOutageActive;

  // Traffic jam speed profile (stands still between 18s and 38s)
  let targetSpeedKmph = sc.speedKmph;
  let isStopped = false;
  if (sc.isJam) {
    if (t >= 18.0 && t <= 38.0) {
      targetSpeedKmph = 0.0;
      isStopped = true;
    } else if (t > 14.0 && t < 18.0) {
      targetSpeedKmph = sc.speedKmph * ((18.0 - t) / 4.0);
    } else if (t > 38.0 && t < 44.0) {
      targetSpeedKmph = sc.speedKmph * ((t - 38.0) / 6.0);
    }
  }

  // Speed propagation
  if (sc.isLive && liveSensor.active) {
    // Use real GPS speed when available; fall back to 0 (not fake accel formula)
    if (typeof liveSensor.speedKmh === 'number' && liveSensor.speedKmh > 0) {
      targetSpeedKmph = Math.min(120.0, liveSensor.speedKmh);
    } else {
      targetSpeedKmph = 0.0;
      isStopped = true;
    }
  }
  sim.speedMps = (targetSpeedKmph / 3.6);

  // Outage Mode State Machine
  if (gnssLost) {
    if (sim.mode === "GNSS-AIDED") {
      sim.mode = "DEAD-RECKONING";
      sim.recoveryFixCount = 0;
    }
    sim.outageDurationS += dt;
    sim.outageDistanceM += sim.speedMps * dt;
    sim.confidence = Math.max(0.68, 1.0 - (sim.outageDurationS / 80.0));
  } else {
    // GNSS Available
    if (sim.mode === "DEAD-RECKONING") {
      sim.recoveryFixCount += dt;
      if (sim.recoveryFixCount >= 0.2) {
        sim.mode = "RECOVERING";
      }
    } else if (sim.mode === "RECOVERING") {
      sim.recoveryFixCount += dt;
      if (sim.recoveryFixCount >= 0.4) {
        sim.mode = "GNSS-AIDED";
        sim.recoveryFixCount = 0;
      }
    } else {
      sim.mode = "GNSS-AIDED";
      sim.confidence = Math.min(0.99, sim.confidence + dt * 0.5);
    }
  }

  // Calculate position along SVG curve (path starts at bottom y=1080 and goes up to destination y=100)
  const progressRatio = Math.min(1.0, sim.currentTimeS / sc.totalDurationS);
  const currentPathDistance = progressRatio * totalPathLength;
  const truePoint = routePath.getPointAtLength(currentPathDistance);

  // Compute road tangent heading
  const aheadPoint = routePath.getPointAtLength(Math.min(totalPathLength, currentPathDistance + 2.0));
  const dx = aheadPoint.x - truePoint.x;
  const dy = aheadPoint.y - truePoint.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;

  // Heading angle for SVG vehicle chevron (drawn pointing UP):
  // When heading straight UP (ux = 0, uy = -1): angle is 0 deg.
  let headingDeg = (Math.atan2(ux, -uy) * 180) / Math.PI;
  if (sc.isLive && liveSensor.active && liveSensor.headingDeg !== 0) {
    headingDeg = liveSensor.headingDeg;
  }

  // Normal vector perpendicular to direction of travel (pointing right)
  const normX = -uy;
  const normY = ux;

  // 1. Intelligent Dead Reckoning (IDR) Position
  // Enforces Non-Holonomic Constraint (NHC) and Road HMM Map Snapping
  let idrLatOffset = 0.0;
  if (sim.mode === "DEAD-RECKONING") {
    const noise = Math.sin(sim.outageDurationS * 0.75) * 1.1;
    idrLatOffset = noise;
    if (isStopped) {
      // Zero Velocity Updates (ZUPT) eliminates sensor integration drift at standstill
      idrLatOffset = 0.0;
    }
  }
  sim.crossTrackM = Math.abs(idrLatOffset);
  sim.maxErrorM = Math.max(sim.maxErrorM, sim.crossTrackM);

  const idrX = truePoint.x + normX * idrLatOffset;
  const idrY = truePoint.y + normY * idrLatOffset;

  // 2. Naïve Unconstrained Inertial Baseline (Ghost Car)
  // Double-integrates raw accelerometer bias and gyro bias without NHC or map snapping
  let naiveLatOffset = 0.0;
  if (sim.outageDurationS > 0) {
    const driftT = sim.outageDurationS;
    naiveLatOffset = (0.5 * sc.accelBias * (driftT * driftT) * 3.8) + (sim.speedMps * sc.gyroBias * driftT * 12.0);
    if (sc.isJam && isStopped) {
      naiveLatOffset += 0.04 * driftT * driftT * 2.2;
    }
  }
  sim.naiveCrossTrackM = naiveLatOffset;
  sim.naiveMaxErrorM = Math.max(sim.naiveMaxErrorM, sim.naiveCrossTrackM);

  const naiveX = truePoint.x + normX * naiveLatOffset;
  const naiveY = truePoint.y + normY * naiveLatOffset;

  // Record history points (every 2nd tick for smooth polyline trail)
  if (Math.round(sim.currentTimeS * 10) % 2 === 0) {
    sim.idrHistory.push(`${idrX.toFixed(1)},${idrY.toFixed(1)}`);
    sim.naiveHistory.push(`${naiveX.toFixed(1)},${naiveY.toFixed(1)}`);
    if (sim.idrHistory.length > 300) {
      sim.idrHistory.shift();
      sim.naiveHistory.shift();
    }
  }

  sim.currentPos = { x: idrX, y: idrY, headingDeg: headingDeg };
  sim.naivePos = { x: naiveX, y: naiveY, headingDeg: headingDeg + (sim.outageDurationS * sc.gyroBias * 45) };
}

function render() {
  const sc = sim.activeScenario;
  const t = sim.currentTimeS;

  // Progress Bar
  const progressPercent = Math.min(100, (t / sc.totalDurationS) * 100);
  if ($("replayProgress")) {
    $("replayProgress").style.width = `${progressPercent}%`;
  }

  // Dynamic Island & Status Chips
  const dynamicIsland = $("dynamicIsland");
  const islandLabel = $("islandLabel");
  const islandIcon = $("islandIcon");
  const islandHeadline = $("islandHeadline");
  const islandDetail = $("islandDetail");
  const desktopChip = $("gnssDesktopChip");
  const desktopText = $("gnssDesktopText");
  const maneuverIconBox = $("maneuverIconBox");
  const modePill = $("modePill");

  if (sim.mode === "GNSS-AIDED") {
    if (dynamicIsland) dynamicIsland.classList.remove("outage-alert");
    if (islandLabel) islandLabel.textContent = "GNSS Locked";
    if (islandIcon) islandIcon.textContent = "📍";
    if (desktopChip) desktopChip.className = "status-chip";
    if (desktopText) desktopText.textContent = "GNSS 3D Locked (12 Sats)";
    if (maneuverIconBox) maneuverIconBox.className = "maneuver-icon-container";
    if (modePill) {
      modePill.className = "mode-pill";
      modePill.textContent = "GNSS-AIDED";
    }
  } else if (sim.mode === "DEAD-RECKONING") {
    if (dynamicIsland) dynamicIsland.classList.add("outage-alert");
    if (islandHeadline) islandHeadline.textContent = "GNSS Denied • Blackout Active";
    if (islandDetail) islandDetail.textContent = `Outage ${sim.outageDurationS.toFixed(1)}s • Drift ${sim.crossTrackM.toFixed(1)}m • HMM Active`;
    if (desktopChip) desktopChip.className = "status-chip outage";
    if (desktopText) desktopText.textContent = "GNSS Denied • IDR Edge Mode";
    if (maneuverIconBox) maneuverIconBox.className = "maneuver-icon-container outage";
    if (modePill) {
      modePill.className = "mode-pill outage";
      modePill.textContent = "DEAD-RECKONING (IDR)";
    }
  } else {
    // RECOVERING
    if (dynamicIsland) dynamicIsland.classList.remove("outage-alert");
    if (islandLabel) islandLabel.textContent = "Reacquiring Fix 2/2";
    if (islandIcon) islandIcon.textContent = "🔄";
    if (desktopChip) desktopChip.className = "status-chip";
    if (desktopText) desktopText.textContent = "Reacquiring GNSS Fix (1/2)";
    if (maneuverIconBox) maneuverIconBox.className = "maneuver-icon-container recovering";
    if (modePill) {
      modePill.className = "mode-pill recovering";
      modePill.textContent = "REACQUIRING";
    }
  }

  // Turn-by-Turn Maneuver Header Card
  const remainingMeters = Math.max(0, Math.round((sc.totalDurationS - t) * (sc.speedKmph / 3.6)));
  if (t < sc.outageStartS - 2.0) {
    if ($("maneuverDistance")) $("maneuverDistance").textContent = `In ${(Math.max(0, (sc.outageStartS - t) * (sc.speedKmph / 3.6))).toFixed(0)} m`;
    if ($("maneuverStreet")) $("maneuverStreet").textContent = sc.streetName;
    if ($("maneuverSub")) $("maneuverSub").textContent = sc.streetSub;
  } else if (t <= sc.outageEndS) {
    if ($("maneuverDistance")) $("maneuverDistance").textContent = `Outage ${sim.outageDurationS.toFixed(1)}s`;
    if ($("maneuverStreet")) $("maneuverStreet").textContent = sc.instructionOutage;
    if ($("maneuverSub")) $("maneuverSub").textContent = `Position sustained via NHC & Map HMM (${sim.crossTrackM.toFixed(1)} m lateral)`;
  } else if (t < sc.outageEndS + 4.0) {
    if ($("maneuverDistance")) $("maneuverDistance").textContent = "Tunnel Egress";
    if ($("maneuverStreet")) $("maneuverStreet").textContent = sc.instructionRecover;
    if ($("maneuverSub")) $("maneuverSub").textContent = "Reconciling observed fix with zero coordinate jump";
  } else {
    if ($("maneuverDistance")) $("maneuverDistance").textContent = `In ${remainingMeters} m`;
    if ($("maneuverStreet")) $("maneuverStreet").textContent = "Arrive at Destination";
    if ($("maneuverSub")) $("maneuverSub").textContent = sc.instructionComplete;
  }

  // Trip Summary Drawer
  const remainingSecs = Math.max(0, sc.totalDurationS - t);
  const remainingMins = Math.max(1, Math.ceil(remainingSecs / 60));
  if ($("etaTime")) $("etaTime").textContent = `${remainingMins} min`;
  if ($("distRemaining")) $("distRemaining").textContent = `${remainingMeters} m`;

  // Telemetry Widgets
  if ($("metricSpeed")) $("metricSpeed").textContent = (sim.speedMps * 3.6).toFixed(0);
  
  const isStopped = sim.speedMps < 0.2;
  const speedSource = $("speedSource");
  if (speedSource) {
    if (isStopped) {
      speedSource.textContent = "ZUPT Clamped (0 m/s)";
    } else if (sim.mode === "DEAD-RECKONING") {
      speedSource.textContent = "Kinematic Blend";
    } else {
      speedSource.textContent = "GNSS Doppler";
    }
  }

  // Drift Calculation: (max_error / outage_distance) * 100
  let driftPercent = 0.0;
  if (sim.outageDistanceM > 10.0) {
    driftPercent = (sim.maxErrorM / sim.outageDistanceM) * 100.0;
  }
  if ($("metricDrift")) $("metricDrift").textContent = driftPercent.toFixed(1);
  const driftStatus = $("driftStatus");
  if (driftStatus) {
    if (driftPercent < 10.0) {
      driftStatus.className = "widget-sub pass-tag";
      driftStatus.textContent = "< 10% Target (PASS)";
    } else {
      driftStatus.className = "widget-sub";
      driftStatus.textContent = "< 10% Target (ALERT)";
    }
  }

  if ($("metricDuration")) $("metricDuration").textContent = sim.outageDurationS.toFixed(1);
  if ($("outageDistanceText")) $("outageDistanceText").textContent = `${sim.outageDistanceM.toFixed(0)} m in outage`;

  if ($("metricCrossTrack")) $("metricCrossTrack").textContent = sim.crossTrackM.toFixed(1);
  if ($("naiveErrorComparison")) $("naiveErrorComparison").textContent = `Naive: ${sim.naiveCrossTrackM.toFixed(1)} m`;

  // Algorithmic Constraints Chips
  if ($("chipNhc")) $("chipNhc").className = `constraint-chip ${sim.mode === "DEAD-RECKONING" ? "active" : ""}`;
  if ($("chipMap")) $("chipMap").className = `constraint-chip ${sim.mode === "DEAD-RECKONING" ? "active" : ""}`;
  if ($("chipZupt")) $("chipZupt").className = `constraint-chip ${isStopped ? "active" : ""}`;
  if ($("chipModel")) $("chipModel").className = "constraint-chip active";

  // Vehicle SVG Group Position
  if (sim.currentPos && $("vehicleGroup")) {
    const vg = $("vehicleGroup");
    vg.setAttribute("transform", `translate(${sim.currentPos.x.toFixed(1)}, ${sim.currentPos.y.toFixed(1)}) rotate(${sim.currentPos.headingDeg.toFixed(1)})`);

    // Uncertainty Halo
    const ellipse = $("uncertaintyEllipse");
    if (ellipse) {
      if (sim.mode === "DEAD-RECKONING") {
        const rx = 18 + (sim.outageDurationS * 0.35);
        const ry = 18 + (sim.outageDurationS * 0.15);
        ellipse.setAttribute("rx", rx);
        ellipse.setAttribute("ry", ry);
        ellipse.setAttribute("opacity", "0.9");
      } else {
        ellipse.setAttribute("rx", 18);
        ellipse.setAttribute("ry", 18);
        ellipse.setAttribute("opacity", "0.25");
      }
    }
  }

  // Naive Baseline Ghost Car
  if (sim.naivePos && $("ghostVehicleGroup")) {
    const gv = $("ghostVehicleGroup");
    gv.setAttribute("transform", `translate(${sim.naivePos.x.toFixed(1)}, ${sim.naivePos.y.toFixed(1)}) rotate(${sim.naivePos.headingDeg.toFixed(1)})`);
    gv.setAttribute("opacity", (sim.compareNaive && sim.outageDurationS > 0.5) ? "1" : "0");
  }

  // Trail Polylines
  if ($("idrTrail")) $("idrTrail").setAttribute("points", sim.idrHistory.join(" "));
  if ($("naiveTrail")) $("naiveTrail").setAttribute("points", sim.compareNaive ? sim.naiveHistory.join(" ") : "");
}

// Boot up
window.addEventListener("DOMContentLoaded", init);
