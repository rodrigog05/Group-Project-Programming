const canvas = document.querySelector("#map");
const context = canvas.getContext("2d");
const hint = document.querySelector("#hint");
const feedback = document.querySelector("#feedback");
const day = new Image();
const night = new Image();
day.src = "world_100_day.png";
night.src = "world_100_night.png";

const directions = {
  arrowleft: "left", a: "left", arrowright: "right", d: "right",
  arrowup: "up", w: "up", arrowdown: "down", s: "down",
};
const actions = { e: "interact", q: "bulk", f: "egg", r: "eggs" };
const held = new Map();
const parentOrigin = document.referrer ? new URL(document.referrer).origin : location.origin;
let state;
let player;
let pending = false;
let queuedAction = null;
let eventId = 0;
let lastUpdate = 0;

function send(type, data = {}) {
  window.parent.postMessage({ isStreamlitMessage: true, type, ...data }, parentOrigin);
}

function frameHeight() {
  send("streamlit:setFrameHeight", { height: document.body.offsetHeight });
}

window.addEventListener("message", (event) => {
  if (event.source !== window.parent || event.origin !== parentOrigin ||
      event.data?.type !== "streamlit:render") return;
  const next = event.data.args;
  if (!player || Math.hypot(next.x - player.x, next.y - player.y) > 155) {
    player = { x: next.x, y: next.y };
  }
  state = next;
  if (next.ack === eventId) pending = false;
  if (!pending && Number.isInteger(next.ack)) eventId = Math.max(eventId, next.ack);
  if (hint.textContent !== state.hint) hint.textContent = state.hint;
  if (feedback.textContent !== state.message) feedback.textContent = state.message;
  frameHeight();
});

function update(now) {
  if (!state || pending || document.hidden || !document.hasFocus()) return;
  const focused = document.activeElement === canvas;
  const values = new Set(held.values());
  const dx = Number(values.has("right")) - Number(values.has("left"));
  const dy = Number(values.has("down")) - Number(values.has("up"));
  const moving = dx || dy;
  if (!focused && !moving && !queuedAction) {
    lastUpdate = 0;
    return;
  }
  const elapsed = lastUpdate ? now - lastUpdate : moving ? 35 : 0;
  if (!lastUpdate && !moving && !queuedAction) {
    lastUpdate = now;
    return;
  }
  if (!queuedAction && elapsed < (moving ? 100 : 240) && lastUpdate) return;
  lastUpdate = now;
  pending = true;
  send("streamlit:setComponentValue", {
    dataType: "json",
    value: { dx, dy, seconds: Math.min(0.25, elapsed / 1000), action: queuedAction, id: ++eventId },
  });
  queuedAction = null;
}

function draw() {
  if (!state || !day.complete || !day.naturalWidth) return;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
  }
  const scale = Math.min(1.15, Math.max(0.55, width / 1000));
  player.x += (state.x - player.x) * 0.26;
  player.y += (state.y - player.y) * 0.26;
  const viewWidth = width / scale;
  const viewHeight = height / scale;
  const left = Math.max(0, Math.min(day.naturalWidth - viewWidth, player.x - viewWidth / 2));
  const top = Math.max(0, Math.min(day.naturalHeight - viewHeight, player.y - viewHeight / 2));
  context.setTransform(ratio * scale, 0, 0, ratio * scale, -left * ratio * scale, -top * ratio * scale);
  context.drawImage(state.night && night.naturalWidth ? night : day, 0, 0);

  for (const site of state.locations) {
    const near = Math.hypot(site.x - state.x, site.y - state.y) < 170;
    context.beginPath();
    context.arc(site.x, site.y + 4, near ? 6 : 4, 0, Math.PI * 2);
    context.fillStyle = site.color;
    context.fill();
    context.lineWidth = 2;
    context.strokeStyle = "#142e33";
    context.stroke();
    if (near) {
      context.font = "bold 15px system-ui";
      context.textAlign = "center";
      context.lineWidth = 4;
      context.strokeText(site.name, site.x, site.y - 9);
      context.fillStyle = "#fff8ea";
      context.fillText(site.name, site.x, site.y - 9);
    }
  }

  context.save();
  context.translate(player.x, player.y);
  context.scale(state.facing < 0 ? -1 : 1, 1);
  context.fillStyle = "#1b292788";
  context.beginPath();
  context.ellipse(0, 2, 14, 5, 0, 0, Math.PI * 2);
  context.fill();
  if (state.vehicle) {
    context.fillStyle = "#25435a";
    context.fillRect(-16, -10, 33, 13);
    context.fillStyle = "#8fd5df";
    context.fillRect(-8, -16, 16, 9);
    context.fillStyle = "#f7d37a";
    context.fillRect(12, -8, 5, 4);
  } else {
    context.fillStyle = "#192c39";
    context.fillRect(-6, -8, 5, 9);
    context.fillRect(2, -8, 5, 9);
    context.fillStyle = "#397fa0";
    context.fillRect(-8, -19, 16, 12);
    context.fillStyle = "#eeb181";
    context.fillRect(-5, -27, 11, 9);
    context.fillStyle = "#ffd072";
    context.fillRect(-7, -30, 13, 5);
    context.fillRect(4, -27, 6, 3);
  }
  context.restore();
}

function frame(now) {
  update(now);
  draw();
  requestAnimationFrame(frame);
}

canvas.addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  if (!Object.hasOwn(directions, key) && !Object.hasOwn(actions, key)) return;
  event.preventDefault();
  if (directions[key]) held.set(key, directions[key]);
  if (actions[key] && !event.repeat) queuedAction = actions[key];
});

window.addEventListener("keyup", (event) => held.delete(event.key.toLowerCase()));
function pause() {
  held.clear();
  lastUpdate = 0;
}
window.addEventListener("blur", pause);
canvas.addEventListener("blur", pause);
document.addEventListener("visibilitychange", pause);

for (const button of document.querySelectorAll("[data-direction]")) {
  button.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    canvas.focus();
    button.setPointerCapture(event.pointerId);
    held.set(event.pointerId, button.dataset.direction);
  });
  for (const eventName of ["pointerup", "pointercancel", "lostpointercapture"]) {
    button.addEventListener(eventName, (event) => held.delete(event.pointerId));
  }
}

for (const button of document.querySelectorAll("[data-action]")) {
  button.addEventListener("click", () => {
    canvas.focus();
    queuedAction = button.dataset.action;
  });
}

new ResizeObserver(frameHeight).observe(document.body);
send("streamlit:componentReady", { apiVersion: 1 });
frameHeight();
requestAnimationFrame(frame);
