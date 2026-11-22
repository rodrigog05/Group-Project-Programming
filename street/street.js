const canvas = document.querySelector("#map");
const context = canvas.getContext("2d");
const hint = document.querySelector("#hint");
const feedback = document.querySelector("#feedback");
const day = new Image();
const night = new Image();
day.src = "world_100_day.webp";

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
let lastFrame = 0;
let lastSend = 0;
let segments = [];
let bufferedSeconds = 0;
let facing = 1;
let ferry = null;
let lastFerryId = null;
const ferryArt = { day: new Image(), night: new Image() };
let reportedHeight;

function send(type, data = {}) {
  window.parent.postMessage({ isStreamlitMessage: true, type, ...data }, parentOrigin);
}

function frameHeight() {
  if (parentOrigin === location.origin && Number.isFinite(window.parent.innerHeight)) {
    const height = Math.max(350, Math.floor(window.parent.innerHeight * 0.8));
    document.body.style.setProperty("--map-height", `${height}px`);
  }
  const height = document.body.offsetHeight;
  if (height !== reportedHeight) {
    reportedHeight = height;
    send("streamlit:setFrameHeight", { height });
  }
}

window.addEventListener("message", (event) => {
  if (event.source !== window.parent || event.origin !== parentOrigin ||
      event.data?.type !== "streamlit:render") return;
  const next = event.data.args;
  // Ignore rerenders while an older request is still in flight.
  if (pending && next.ack !== eventId) return;
  if (next.night && !night.getAttribute("src")) night.src = "world_100_night.webp";
  // A new ferry id means Python just moved the player across the Tejo: play the crossing.
  // The first id this map sees is history (for example after leaving a building), so skip it.
  const ferryId = next.ferry ? next.ferry.id : 0;
  if (lastFerryId !== null && ferryId !== lastFerryId) {
    ferry = { start: performance.now(), heading: next.ferry.heading };
    held.clear();
  }
  lastFerryId = ferryId;
  player = { x: next.x, y: next.y };
  facing = next.facing;
  state = next;
  if (next.ack === eventId) pending = false;
  if (!pending && Number.isInteger(next.ack)) eventId = Math.max(eventId, next.ack);
  // Replay only movement accumulated after the acknowledged batch.
  // Teleports (ferry/Visit) use the new authoritative origin.
  for (const segment of segments) predict(segment);
  if (hint.textContent !== state.hint) hint.textContent = state.hint;
  if (feedback.textContent !== state.message) feedback.textContent = state.message;
  frameHeight();
});

// Collision checks mirror Town.can_walk in tycoon.py, using the geometry Python sends.
// Python stays the authority: it replays every step and corrects the position if needed.
function sandEdge(x) {
  const [west, east, bottom] = state.collision.sand;
  const top = state.collision.river[0];
  const fraction = (x - west) / (east - west);
  if (fraction < 0 || fraction > 1) return top;
  const curve = Math.sin(Math.PI * fraction) ** 0.55;
  const scallops = 1 + 0.045 * Math.sin(fraction * Math.PI * 2 * 3);
  return top + (bottom - top) * curve * scallops;
}

function onSand(x, y, r) {
  const [west, east] = state.collision.sand;
  return west + r <= x && x <= east - r && state.collision.river[0] - 3 <= y &&
    y + r <= Math.min(sandEdge(x - r), sandEdge(x), sandEdge(x + r));
}

function onBridge(x, y, r) {
  const eastern = state.collision.vasco - 0.32 * (y - state.collision.river[0]);
  return Math.abs(x - 300) <= 31 - r || Math.abs(x - eastern) <= 27 - r;
}

function insideAny(boxes, x, y, r) {
  return boxes.some(([left, top, right, bottom]) =>
    left - r < x && x < right + r && top - r < y && y < bottom + r);
}

function walkableTerrain(x, y, r, onFoot) {
  const [riverTop, riverBottom] = state.collision.river;
  if (riverTop - r < y && y < riverBottom + r) {
    if (onFoot && onSand(x, y, r)) return !insideAny([state.collision.tower], x, y, r);
    return !onFoot && onBridge(x, y, r);
  }
  return true;
}

function parkBlocked(x, y, r) {
  const [left, right, centerY, halfWidth] = state.collision.tunnel;
  if (left <= x && x <= right && Math.abs(y - centerY) <= halfWidth - r) return false;
  return insideAny(state.collision.parks, x, y, r);
}

function canWalk(x, y) {
  const { radius: r, world: [width, mapTop, bottom], boxes } = state.collision;
  if (state.vehicle && parkBlocked(x, y, r)) return false;
  return r <= x && x <= width - r && mapTop + r <= y && y <= bottom - r &&
    walkableTerrain(x, y, r, !state.vehicle) && !insideAny(boxes, x, y, r);
}

function predict({ dx, dy, seconds }) {
  const length = Math.hypot(dx, dy);
  if (!length) return;
  if (dx) facing = dx < 0 ? -1 : 1;
  const [width, mapTop, bottom] = state.collision.world;
  // Same 1/60 s steps and x-then-y order as street_input and Town.move, so walls stop the player.
  const steps = Math.max(1, Math.ceil(seconds * 60));
  const distance = state.speed * seconds / steps / length;
  for (let step = 0; step < steps; step += 1) {
    const nextX = Math.max(17, Math.min(width - 17, player.x + dx * distance));
    const nextY = Math.max(mapTop + 15, Math.min(bottom - 15, player.y + dy * distance));
    if (canWalk(nextX, player.y)) player.x = nextX;
    if (!tollBlocks(nextY) && canWalk(player.x, nextY)) player.y = nextY;
  }
}

// Mirrors Town.toll_blocks: no driving onto a bridge from Almada without the toll in cash.
function tollBlocks(nextY) {
  const { radius: r, river, toll } = state.collision;
  const south = river[1] + r;
  return Boolean(state.vehicle) && !state.on_bridge && state.cash < toll &&
    player.y >= south && nextY < south && onBridge(player.x, nextY, r);
}

function update(now) {
  const seconds = lastFrame ? Math.min(0.05, (now - lastFrame) / 1000) : 0;
  lastFrame = now;
  if (!state) return;
  const active = !ferry && !document.hidden && document.hasFocus() && document.activeElement === canvas;
  if (active && !queuedAction && seconds && bufferedSeconds < 2 && segments.length < 120) {
    const values = new Set(held.values());
    const dx = Number(values.has("right")) - Number(values.has("left"));
    const dy = Number(values.has("down")) - Number(values.has("up"));
    const duration = Math.min(seconds, 2 - bufferedSeconds);
    const segment = { dx, dy, seconds: duration };
    const previous = segments.at(-1);
    if (previous && previous.dx === dx && previous.dy === dy && previous.seconds + duration <= 0.25) {
      previous.seconds += duration;
    } else {
      segments.push({ ...segment });
    }
    bufferedSeconds += duration;
    predict(segment);
  }
  // One request at a time. Continue predicting while Python handles the batch.
  // Freeze at an action boundary so trades happen at the validated location.
  if (pending || (!segments.length && !queuedAction)) return;
  if (!queuedAction && active && now - lastSend < 200) return;
  const batch = segments.length ? segments : [{ dx: 0, dy: 0, seconds: 0 }];
  segments = [];
  bufferedSeconds = 0;
  lastSend = now;
  pending = true;
  send("streamlit:setComponentValue", {
    dataType: "json",
    value: { segments: batch, action: queuedAction, id: ++eventId },
  });
  queuedAction = null;
}

function draw() {
  if (state && ferry) {
    drawFerry();
    return;
  }
  if (!state || !day.complete || !day.naturalWidth) return;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
  }
  const scale = Math.min(1.15, Math.max(0.55, width / 1000));
  const viewWidth = width / scale;
  const viewHeight = height / scale;
  const left = Math.max(0, Math.min(day.naturalWidth - viewWidth, player.x - viewWidth / 2));
  const top = Math.max(0, Math.min(day.naturalHeight - viewHeight, player.y - viewHeight / 2));
  context.setTransform(ratio * scale, 0, 0, ratio * scale, -left * ratio * scale, -top * ratio * scale);
  context.drawImage(state.night && night.naturalWidth ? night : day, 0, 0);

  drawStreetLife(performance.now() / 1000, left, top, viewWidth, viewHeight);

  for (const site of state.locations) {
    const near = Math.hypot(site.x - player.x, site.y - player.y) < 170;
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
  context.scale(facing < 0 ? -1 : 1, 1);
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
    drawWalker();
  }
  context.restore();
}

// Decorative street life from the desktop game. Nothing here blocks the player.
function seen(x, y, left, top, width, height) {
  return x > left - 60 && x < left + width + 60 && y > top - 60 && y < top + height + 60;
}

function drawTram(t, left, top, width, height) {
  const [from, to, period] = state.life.tram;
  const phase = t % period;
  const half = period / 2;
  // Run, then wait at each end, like the desktop tram.
  const fraction = phase < half ? Math.min(1, phase / (half - 3)) : Math.max(0, 1 - (phase - half) / (half - 3));
  const x = from + (to - from) * fraction;
  if (!seen(x, 680, left, top, width, height)) return;
  context.fillStyle = "#b4ac92";
  context.beginPath();
  context.ellipse(x + 2, 697, 36, 5, 0, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "#d8a32f";
  context.strokeStyle = "#a47931";
  context.lineWidth = 1;
  context.beginPath();
  context.roundRect(x - 34, 655, 68, 41, 7);
  context.fill();
  context.stroke();
  context.fillStyle = "#f7e8c3";
  context.fillRect(x - 30, 660, 60, 5);
  context.fillStyle = state.night ? "#f2d69a" : "#55777c";
  context.strokeStyle = "#f4e7bd";
  for (const offset of [-25, -10, 5, 20]) {
    context.fillRect(x + offset, 668, 10, 13);
    context.strokeRect(x + offset, 668, 10, 13);
  }
  context.strokeStyle = "#f4e4b4";
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(x - 30, 684);
  context.lineTo(x + 30, 684);
  context.stroke();
  context.beginPath();
  context.moveTo(x - 8, 655);
  context.lineTo(x + 2, 645);
  context.lineTo(x + 12, 655);
  context.strokeStyle = "#4a5d5e";
  context.stroke();
  context.fillStyle = "#3c4c4f";
  for (const wheel of [-20, 20]) {
    context.beginPath();
    context.arc(x + wheel, 694, 4.5, 0, Math.PI * 2);
    context.fill();
  }
  context.font = "bold 7px system-ui";
  context.textAlign = "center";
  context.fillStyle = "#fff5dc";
  context.fillText("TEJO", x, 690);
}

function drawShuttle(t, left, top, width, height) {
  const [x1, y1, x2, y2, speed] = state.life.ferry;
  const length = Math.hypot(x2 - x1, y2 - y1);
  let progress = (t * speed / length) % 2;
  const outbound = progress <= 1;
  progress = outbound ? progress : 2 - progress;
  const x = x1 + (x2 - x1) * progress;
  const y = y1 + (y2 - y1) * progress + Math.sin(t * 0.7) * 1.5;
  if (!seen(x, y, left, top, width, height)) return;
  context.save();
  context.translate(x, y);
  context.rotate(Math.atan2(y2 - y1, x2 - x1) + (outbound ? 0 : Math.PI));
  context.strokeStyle = "#abd0ce";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(-36, 3); context.lineTo(-24, 0); context.lineTo(-35, -3);
  context.stroke();
  context.fillStyle = "#e07a2e";
  context.strokeStyle = "#879d9a";
  context.beginPath();
  context.ellipse(0, 0, 30, 9, 0, 0, Math.PI * 2);
  context.fill();
  context.stroke();
  context.fillStyle = "#f5efe2";
  context.fillRect(-12, -5, 24, 10);
  context.fillStyle = state.night ? "#ffd682" : "#688b98";
  context.fillRect(-8, -3, 16, 6);
  context.restore();
}

function drawStreetLife(t, left, top, width, height) {
  if (!state.life) return;
  drawTram(t, left, top, width, height);
  drawShuttle(t, left, top, width, height);
  const [tunnelLeft, tunnelRight, tunnelY, tunnelHalf] = state.life.tunnel;
  for (const [start, y, end, speed, phase, direction, color] of state.life.cars) {
    const length = end - start;
    const progress = (t * speed / length + phase) % 1;
    const x = direction > 0 ? start + length * progress : end - length * progress;
    const underground = x > tunnelLeft && x < tunnelRight && Math.abs(y - tunnelY) <= tunnelHalf;
    if (underground || !seen(x, y, left, top, width, height)) continue;
    context.save();
    context.translate(x, y);
    context.scale(direction, 1);
    context.fillStyle = color;
    context.strokeStyle = "#435c5c";
    context.lineWidth = 1;
    context.beginPath();
    context.roundRect(-15, -8, 30, 16, 5);
    context.fill();
    context.stroke();
    context.fillStyle = state.night ? "#f2d69a" : "#aac5c8";
    context.fillRect(-7, -5, 14, 9);
    if (state.night) {
      context.fillStyle = "#fff1b8";
      context.fillRect(13, -6, 3, 3);
      context.fillRect(13, 3, 3, 3);
    }
    context.restore();
  }
  for (const [x1, y1, x2, y2, speed, offset, color] of state.life.people) {
    const length = Math.max(1, Math.hypot(x2 - x1, y2 - y1));
    let progress = (t * speed / length + offset) % 2;
    progress = progress <= 1 ? progress : 2 - progress;
    const x = x1 + (x2 - x1) * progress;
    const y = y1 + (y2 - y1) * progress + Math.sin(t * 8 + offset) * 0.8;
    if (!seen(x, y, left, top, width, height)) continue;
    context.fillStyle = "#8c947d88";
    context.beginPath();
    context.ellipse(0.5 + x, 5.5 + y, 5.5, 2.5, 0, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = color;
    context.beginPath();
    context.ellipse(x, y - 1, 4, 6, 0, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#dfbb93";
    context.beginPath();
    context.arc(x, y - 9.5, 3.2, 0, Math.PI * 2);
    context.fill();
  }
}

function drawWalker() {
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

// ----- The ferry crossing, ported from the desktop game's ferry scene (640 x 400 scene units) -----
const CROSSING_SECONDS = 4.5;
const WATER_Y = 250;
const PIERS_X = [120, 520];  // Cais do Sodré (Lisboa, left) and Cacilhas (right)

function tint(color, night, lit = false) {
  if (!night || lit) return color;
  const mix = (a, b) => Math.round(a * 0.55 + b * 0.45);
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16));
  return `rgb(${mix(r, 0x17)},${mix(g, 0x22)},${mix(b, 0x3f)})`;
}

function drawFerry() {
  const night = state.night;
  const art = night ? ferryArt.night : ferryArt.day;
  if (!art.getAttribute("src")) art.src = night ? "scenes/ferry_night.webp" : "scenes/ferry_day.webp";
  const elapsed = (performance.now() - ferry.start) / 1000;
  if (elapsed > CROSSING_SECONDS + 0.6) {
    ferry = null;
    return;
  }
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
  }
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.fillStyle = "#1f2a30";
  context.fillRect(0, 0, width, height);
  const scale = Math.min(width / 640, height / 400);
  context.setTransform(ratio * scale, 0, 0, ratio * scale, ratio * (width - 640 * scale) / 2,
                       ratio * (height - 400 * scale) / 2);
  if (art.complete && art.naturalWidth) context.drawImage(art, 0, 0, 640, 400);

  const heading = ferry.heading;
  const progress = Math.min(1, elapsed / CROSSING_SECONDS);
  const eased = progress * progress * (3 - 2 * progress);
  const [start, end] = heading > 0 ? PIERS_X : [PIERS_X[1], PIERS_X[0]];
  const x = start + (end - start) * eased;
  const y = WATER_Y + 34 + Math.sin(elapsed * 2.4) * 2;
  const line = (points, color, width) => {
    context.strokeStyle = color;
    context.lineWidth = width;
    context.beginPath();
    context.moveTo(points[0], points[1]);
    for (let i = 2; i < points.length; i += 2) context.lineTo(points[i], points[i + 1]);
    context.stroke();
  };
  const rect = (x1, y1, x2, y2, color, lit = false) => {
    context.fillStyle = tint(color, night, lit);
    context.fillRect(x1, y1, x2 - x1, y2 - y1);
  };
  for (let index = 0; index < 26; index += 1) {
    const waveX = ((index * 61 + elapsed * 18 * (index % 2 ? 1 : -1)) % 700 + 700) % 700 - 30;
    const waveY = WATER_Y + 30 + (index * 37) % (400 - WATER_Y - 40);
    line([waveX, waveY, waveX + 18 + (index % 3) * 8, waveY], tint("#cfe8ea", night), 1);
  }
  if (progress > 0 && progress < 1) {
    for (let trail = 1; trail < 5; trail += 1) {
      const trailX = x - heading * (48 + trail * 16);
      line([trailX, y + 10 + trail * 2, trailX - heading * 18, y + 12 + trail * 3], tint("#eaf6f4", night), 2);
    }
  }
  // Cabin, then the player at the bow, then the hull in front of their legs.
  rect(x - 38, y - 34, x + 30, y - 8, "#f5efe2");
  for (let window = 0; window < 5; window += 1) {
    const left = x - 32 + window * 12;
    rect(left, y - 28, left + 8, y - 20, night ? "#ffd682" : "#2f4b5a", night);
  }
  rect(x - 6, y - 50, x + 6, y - 34, "#2f3d45");
  rect(x - 6, y - 50, x + 6, y - 45, "#d33a35");
  context.save();
  context.translate(x + heading * 44, y + 3);
  context.scale(heading * 0.9, 0.9);
  drawWalker();
  context.restore();
  context.fillStyle = tint("#e07a2e", night);
  context.beginPath();
  [[x - 58, y - 4], [x + 58, y - 4], [x + 58 + heading * 12, y - 14], [x + 46, y + 16], [x - 46, y + 16]]
    .forEach(([px, py], i) => (i ? context.lineTo(px, py) : context.moveTo(px, py)));
  context.closePath();
  context.fill();
  rect(x - 56, y - 8, x + 56, y - 4, "#f5efe2");
  context.font = "bold 6px system-ui";
  context.textAlign = "center";
  context.fillStyle = tint("#fff5e2", night);
  context.fillText("CACILHEIRO", x - 4, y + 8);
  if (night) {
    context.fillStyle = "#fff3c4";
    context.beginPath();
    context.arc(x, y - 55, 3, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = heading > 0 ? "#7dff9a" : "#ff6a5a";
    context.beginPath();
    context.arc(x + heading * 60, y - 9, 3, 0, Math.PI * 2);
    context.fill();
  } else {
    for (let index = 0; index < 4; index += 1) {
      const gullX = (index * 170 + elapsed * 40) % 680 - 20;
      const gullY = 60 + index * 22 + Math.sin(elapsed * 1.3 + index) * 6;
      const flap = 4 * Math.sin(elapsed * 9 + index);
      line([gullX - 8, gullY, gullX - 3, gullY - flap, gullX, gullY, gullX + 3, gullY - flap, gullX + 8, gullY],
           "#2f3d45", 2);
    }
  }
  const names = heading > 0 ? "Cais do Sodré  →  Cacilhas" : "Cacilhas  →  Cais do Sodré";
  context.fillStyle = "#1f2a30cc";
  context.fillRect(170, 12, 300, 26);
  context.font = "bold 13px system-ui";
  context.fillStyle = "#f6e7b4";
  context.fillText(`Ferry  ·  ${names}`, 320, 30);
  context.font = "10px system-ui";
  context.fillStyle = "#e5d9bd";
  context.fillText("Click or press Esc to skip", 320, 392);
}

function frame(now) {
  update(now);
  draw();
  requestAnimationFrame(frame);
}

canvas.addEventListener("pointerdown", () => { ferry = null; });
canvas.addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  if (ferry) {
    if (key === "escape") ferry = null;
    event.preventDefault();
    return;
  }
  if (!Object.hasOwn(directions, key) && !Object.hasOwn(actions, key)) return;
  event.preventDefault();
  if (directions[key]) held.set(key, directions[key]);
  if (actions[key] && !event.repeat) queuedAction = actions[key];
});

window.addEventListener("keyup", (event) => held.delete(event.key.toLowerCase()));
function pause() {
  held.clear();
  lastFrame = 0;
  queuedAction = null;
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
if (parentOrigin === location.origin && window.parent !== window) {
  window.parent.addEventListener?.("resize", frameHeight);
  window.addEventListener("pagehide", () => window.parent.removeEventListener?.("resize", frameHeight));
}
send("streamlit:componentReady", { apiVersion: 1 });
frameHeight();
requestAnimationFrame(frame);
