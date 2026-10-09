const state = {
  step: 0,
  timer: null,
  total: 24,
  modes: ["GNSS-AIDED", "GNSS-AIDED", "DEAD-RECKONING", "DEAD-RECKONING", "RECOVERING", "GNSS-AIDED"],
};

const $ = (id) => document.getElementById(id);
function render() {
  const progress = Math.min(state.step / state.total, 1);
  const phase = state.step < 8 ? 0 : state.step < 18 ? 2 : state.step < 21 ? 4 : 5;
  const mode = state.step === 0 ? "READY" : state.modes[phase];
  $("mode").textContent = mode;
  $("confidence").textContent = `Confidence ${state.step === 0 ? "--" : Math.max(.58, 1 - Math.max(0, state.step - 8) * .025).toFixed(2)}`;
  $("speed").textContent = state.step === 0 ? "0" : "48";
  $("distance").textContent = (state.step * .042).toFixed(1);
  $("instruction").textContent = mode === "DEAD-RECKONING" ? "GNSS unavailable" : mode === "RECOVERING" ? "Reacquiring signal" : "Continue on route";
  $("subline").textContent = mode === "DEAD-RECKONING" ? "Inertial tracking active. Map constraints are maintaining the route." : "Lane guidance is ready for the next maneuver.";
  $("progress").style.width = `${progress * 100}%`;
  $("vehicle").setAttribute("cx", 42 + progress * 232);
  $("vehicle").setAttribute("cy", 585 - progress * 493);
  $("diagnostics").textContent = state.step === 0 ? "Replay is idle." : `Replay sample ${state.step}/${state.total} at 10 Hz.`;
  $("replay").textContent = state.step >= state.total ? "Replay complete" : state.step ? "Replay running" : "Start replay";
}

function tick() {
  state.step += 1;
  render();
  if (state.step >= state.total) {
    clearInterval(state.timer);
    state.timer = null;
  }
}

$("replay").addEventListener("click", () => {
  if (state.timer || state.step >= state.total) return;
  state.timer = setInterval(tick, 450);
  tick();
});
$("reset").addEventListener("click", () => {
  clearInterval(state.timer);
  state.timer = null;
  state.step = 0;
  render();
});
render();
