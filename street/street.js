const canvas = document.querySelector("#map");
const context = canvas.getContext("2d");
const hint = document.querySelector("#hint");
const route = document.querySelector("#route");
const vehicleButton = document.querySelector('[data-action="vehicle"]');
const controls = document.querySelector(".controls");
const settingsButton = document.querySelector("#settings");
const settingsPanel = document.querySelector("#settings-panel");
const musicToggle = document.querySelector("#music");
const soundtrack = document.querySelector("#soundtrack");
soundtrack.volume = 0.4;
try {
  musicToggle.checked = localStorage.getItem("foundry-music-enabled") !== "false";
} catch {
  // Private browsing may block storage; the default remains enabled.
}
function playMusic() {
  if (musicToggle.checked && soundtrack.paused && !dialogOpen()) {
    soundtrack.play().catch(() => {
      // Browsers may require a click or key press before playback.
    });
  }
}
settingsButton.addEventListener("click", () => {
  settingsPanel.hidden = !settingsPanel.hidden;
  settingsButton.setAttribute("aria-expanded", String(!settingsPanel.hidden));
});
musicToggle.addEventListener("change", () => {
  try {
    localStorage.setItem("foundry-music-enabled", String(musicToggle.checked));
  } catch {
    // The setting still works for this page when storage is unavailable.
  }
  if (musicToggle.checked) playMusic();
  else soundtrack.pause();
});
for (const page of [document, ...pageDocuments()]) {
  page.addEventListener("pointerdown", playMusic, true);
  page.addEventListener("keydown", playMusic, true);
}
playMusic();
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && musicToggle.checked) playMusic();
  if (document.hidden) {
    soundtrack.pause();
  }
});
// Images are cached by the browser. Python sends art_version, a fingerprint of every picture in street/
// (browser_game.art_version), so changed art gets a new address and players never see stale pictures.
// Images start loading with the first update, once the version is known. (street.js itself is always
// loaded fresh by index.html.)
let artVersion = null;
const asset = (path) => `${path}?v=${artVersion}`;
const day = new Image();
const night = new Image();
const stationArt = { day: new Image(), night: new Image() };
const cityArt = { day: new Image(), night: new Image() };

const directions = {
  arrowleft: "left", a: "left", arrowright: "right", d: "right",
  arrowup: "up", w: "up", arrowdown: "down", s: "down",
};
const actions = { e: "interact", v: "vehicle" };  // V parks the vehicle and brings it back
const vehicleArt = Object.fromEntries(["motorcycle", "car", "van", "f1"].map(key => [key, new Image()]));

function loadArt(version) {
  artVersion = version;
  day.src = asset("world_100_day.webp");
  stationArt.day.src = asset("oriente_day.svg");
  cityArt.day.src = asset("city_day.svg");
  for (const [key, art] of Object.entries(vehicleArt)) art.src = asset(`vehicles/${key}.svg`);
  loadRider();
}
const held = new Map();
const parentOrigin = document.referrer ? new URL(document.referrer).origin : location.origin;
let state;
let productionUpdatedAt = 0;
let player;
let pending = false;
let queuedAction = null;
let queuedKey = null;
const sceneArt = {};
let lastSpinId = null;
let spinAnimation = null;
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
  if (parentOrigin === location.origin && window.frameElement) {
    const main = window.frameElement.closest('[data-testid="stMain"]');
    const top = window.frameElement.getBoundingClientRect().top + (main?.scrollTop || 0);
    const bottom = main?.getBoundingClientRect().bottom ?? window.parent.innerHeight;
    const controlsHeight = document.body.offsetHeight - canvas.offsetHeight;
    // Reserve space for the page's bottom padding and keep the map usable in very short windows.
    const height = Math.max(128, Math.floor(bottom - top - controlsHeight - 8));
    canvas.style.setProperty("--map-height", `${height}px`);
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
  // Python's reply to the map's own movement, as opposed to a page update such as Visit or Leave.
  const ownReply = pending && next.ack === eventId;
  if (artVersion === null) loadArt(next.art_version || "1");
  if (next.night && !night.getAttribute("src")) night.src = asset("world_100_night.webp");
  if (next.night && !stationArt.night.getAttribute("src")) stationArt.night.src = asset("oriente_night.svg");
  if (next.night && !cityArt.night.getAttribute("src")) cityArt.night.src = asset("city_night.svg");
  // A new ferry id means Python just moved the player across the Tejo: play the crossing.
  // The first id this map sees is history (for example after leaving a building), so skip it.
  const ferryId = next.ferry ? next.ferry.id : 0;
  if (lastFerryId !== null && ferryId !== lastFerryId) {
    ferry = { start: performance.now(), heading: next.ferry.heading };
    held.clear();
  }
  lastFerryId = ferryId;
  const spin = next.interior && next.interior.casino && next.interior.casino.spin;
  const spinId = spin ? spin.id : 0;
  if (lastSpinId !== null && spinId !== lastSpinId && spin) spinAnimation = { start: performance.now(), spin };
  lastSpinId = spinId;
  // A new alert id means Python just refused something: show it for a few seconds.
  const alertId = next.alert ? next.alert.id : 0;
  if (lastAlertId !== null && alertId !== lastAlertId) alertBanner = { text: next.alert.text, start: performance.now() };
  lastAlertId = alertId;
  controls.hidden = Boolean(next.interior);
  player = { x: next.x, y: next.y };
  facing = next.facing;
  state = next;
  productionUpdatedAt = performance.now();
  vehicleButton.hidden = !state.vehicle && !state.stowed_vehicle;
  const vehicleLabel = state.vehicle ? "Leave vehicle" : "Bring back vehicle";
  const labelText = vehicleButton.querySelector("span");
  if (labelText.textContent !== vehicleLabel) labelText.textContent = vehicleLabel;
  if (next.ack === eventId) pending = false;
  if (!pending && Number.isInteger(next.ack)) eventId = Math.max(eventId, next.ack);
  // Replay only movement accumulated after the acknowledged batch.
  // Teleports (ferry/Visit) use the new authoritative origin.
  for (const segment of segments) predict(segment);
  if (hint.textContent !== state.hint) hint.textContent = state.hint;
  const instruction = next.interior ? "" : next.route?.instruction || "";
  if (route.textContent !== instruction) route.textContent = instruction;
  frameHeight();
  if (!ownReply) claimKeyboard();
});

// Keep the keyboard on the game view, so walking and building keys work without clicking.
// Streamlit removes clicked buttons and the start menu on reruns; the browser then drops the
// keyboard onto the empty page. Whenever nothing else holds it, the map takes it back. It never
// takes it from a field or button the player is using, and a click on an empty part of the page
// pauses street play until the player clicks the map again.
let userPaused = false;
const INTERACTIVE = 'button, a, input, select, textarea, label, iframe, [role="button"], [role="option"], ' +
  '[role="combobox"], [role="listbox"], [role="tab"], [tabindex]';

function pageDocuments() {
  const documents = [];
  try {
    for (let view = window.parent; view && view !== window; view = view === view.parent ? null : view.parent) {
      documents.push(view.document);
    }
  } catch {
    // A cross-origin page above the game; only the documents we can read are checked.
  }
  return documents;
}

for (const page of pageDocuments()) {
  page.addEventListener("pointerdown", (event) => {
    userPaused = !(event.target instanceof page.defaultView.Element && event.target.closest(INTERACTIVE));
  }, true);
}
canvas.addEventListener("pointerdown", () => { userPaused = false; });

function keyboardIsFree() {
  if (document.hidden || userPaused) return false;
  if (document.activeElement === canvas && document.hasFocus()) return false;
  const pages = pageDocuments();
  if (pages.length && !pages.at(-1).hasFocus()) return false;  // Another window or tab is in use
  // Free when every page above the map has only its body (or a frame on the way down) focused.
  return pages.every((page) => {
    const active = page.activeElement;
    return !active || active === page.body || active.tagName === "IFRAME";
  });
}

function typingOnPage() {
  return pageDocuments().some((page) => {
    const active = page.activeElement;
    return active && (active.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName));
  });
}

function dialogOpen(selector = '[role="dialog"]') {
  // The start menu and Basics are dialogs; their buttons keep the keyboard.
  return pageDocuments().some((page) => page.querySelector(selector));
}

function claimKeyboard() {
  if (dialogOpen()) return;
  // A page update the player caused (Continue, Visit, Leave, a page button) resumes play.
  userPaused = false;
  if (!typingOnPage() && !document.hidden) canvas.focus({ preventScroll: true });
}

function focusMap() {
  if (keyboardIsFree() && !dialogOpen()) canvas.focus({ preventScroll: true });
}

setInterval(focusMap, 300);

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
  if (state.collision.lake) {
    const [cx, cy, rx, ry] = state.collision.lake;
    if (((x - cx) / (rx + r)) ** 2 + ((y - cy) / (ry + r)) ** 2 <= 1) return false;
  }
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

function onRoad(x, y) {
  const { roads, road_exclusions, tunnel } = state.collision;
  const [left, right, center, half] = tunnel;
  const inTunnel = left <= x && x <= right && Math.abs(y - center) <= half;
  if (!inTunnel && insideAny(road_exclusions, x, y, 0)) return false;
  return roads.some(([x1, y1, x2, y2, width]) => {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const fraction = Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)));
    return (x - (x1 + fraction * dx)) ** 2 + (y - (y1 + fraction * dy)) ** 2 <= width ** 2;
  });
}

function canWalk(x, y) {
  const { radius: r, world: [width, mapTop, bottom], boxes } = state.collision;
  if (state.vehicle && (parkBlocked(x, y, r) || !onRoad(x, y))) return false;
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
    const walking = !state.interior;
    const dx = walking ? Number(values.has("right")) - Number(values.has("left")) : 0;
    const dy = walking ? Number(values.has("down")) - Number(values.has("up")) : 0;
    const duration = Math.min(seconds, 2 - bufferedSeconds);
    const segment = { dx, dy, seconds: duration };
    const previous = segments.at(-1);
    if (previous && previous.dx === dx && previous.dy === dy && previous.seconds + duration <= 0.25) {
      previous.seconds += duration;
    } else {
      segments.push({ ...segment });
    }
    bufferedSeconds += duration;
    if (walking) predict(segment);
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
    value: { segments: batch, action: queuedAction, key: queuedKey, id: ++eventId },
  });
  queuedAction = null;
  queuedKey = null;
}

function roundedRect(x, y, width, height, radius) {
  if (typeof context.roundRect === "function") {
    context.roundRect(x, y, width, height, radius);
  } else {
    context.rect(x, y, width, height);
  }
}

function draw() {
  if (state && ferry) {
    drawFerry();
    return;
  }
  if (state && state.interior) {
    drawInterior();
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
  const city = state.night && night.naturalWidth ? cityArt.night : cityArt.day;
  const station = state.night && night.naturalWidth ? stationArt.night : stationArt.day;
  if (station.complete && station.naturalWidth && state.station_bounds) context.drawImage(station, ...state.station_bounds);
  if (city.complete && city.naturalWidth) context.drawImage(city, 0, 0);

  if (state.route?.points?.length > 1) {
    context.save();
    context.beginPath();
    // Use the same predicted position as the sprite, even between server replies.
    context.moveTo(player.x, player.y);
    const points = state.route.points;
    let first = 1;
    while (first < points.length - 1) {
      const [x, y] = points[first];
      const [nextX, nextY] = points[first + 1];
      const dx = nextX - x, dy = nextY - y;
      const length = Math.hypot(dx, dy);
      const px = player.x - x, py = player.y - y;
      // Drop a passed vertex only while following its outgoing segment.
      if (length && (px * dx + py * dy < 0 || Math.abs(px * dy - py * dx) > 3 * length)) break;
      first++;
    }
    for (let i = first; i < points.length; i++) context.lineTo(...points[i]);
    context.strokeStyle = "#89e3ff";
    context.lineWidth = 4;
    context.lineCap = "round";
    context.setLineDash([11, 9]);
    context.stroke();
    context.restore();
  }

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
    if (near && !site.label_on_map) {
      context.font = "bold 15px system-ui";
      context.textAlign = "center";
      context.lineWidth = 4;
      context.strokeText(site.name, site.x, site.y - 9);
      context.fillStyle = "#fff8ea";
      context.fillText(site.name, site.x, site.y - 9);
    }
  }

  if (state.vehicle && underTunnel(player.x, player.y)) return;
  context.save();
  context.translate(player.x, player.y);
  context.scale(facing < 0 ? -1 : 1, 1);
  context.fillStyle = "#1b292788";
  context.beginPath();
  if (state.vehicle) {
    // A flat shadow right under the wheels, which touch the ground at y = 1 (the art's wheels end at
    // 107 of its 120-pixel height), so thin vehicles like the motorcycle don't look like they float.
    context.ellipse(0, 1, 17, 3, 0, 0, Math.PI * 2);
    context.fill();
    const lamp = HEADLAMPS[state.vehicle] || HEADLAMPS.car;
    if (state.night) drawBeam(lamp[0], lamp[1], lamp[2], 70);  // Starts right at the vehicle's headlamp
    const art = vehicleImage(state.vehicle);
    if (art?.complete && art.naturalWidth) context.drawImage(art, -30, -31, 60, 36);
  } else {
    context.ellipse(0, 2, 14, 5, 0, 0, Math.PI * 2);
    context.fill();
    drawWalker();
  }
  context.restore();
  if (state.player_name) {  // The player's name above their head (or their vehicle), as in the desktop game
    const nameY = player.y - (state.vehicle ? 38 : 50);
    context.font = "bold 9px system-ui, sans-serif";
    context.textAlign = "center";
    context.lineWidth = 3;
    context.strokeStyle = "#1b2927cc";
    context.strokeText(state.player_name, player.x, nameY);
    context.fillStyle = "#fff8ea";
    context.fillText(state.player_name, player.x, nameY);
  }
  drawTimer();
  drawHint("street");
  drawAlert();
}

// Decorative street life from the desktop game. Nothing here blocks the player.
function underTunnel(x, y) {
  const [left, right, center, half] = state.life.tunnel;
  return x > left && x < right && Math.abs(y - center) <= half;
}

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
  roundedRect(x - 34, 655, 68, 41, 7);
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

// A soft cone of headlight, pointing along +x from the car's front (callers flip x for direction).
// Where each vehicle's headlamp sits on the map, from its art (drawn 60x36 at -30, -31): [x, y, beam half-width].
const HEADLAMPS = { motorcycle: [15, -15, 4], car: [21, -9, 7], van: [22, -9, 7], f1: [27, -8, 5] };

function drawBeam(front, centre, halfWidth, reach = 58) {
  const glow = context.createLinearGradient(front, 0, front + reach, 0);
  glow.addColorStop(0, "rgba(255, 238, 170, 0.55)");
  glow.addColorStop(1, "rgba(255, 238, 170, 0)");
  context.fillStyle = glow;
  context.beginPath();
  context.moveTo(front, centre - halfWidth * 0.6);
  context.lineTo(front + reach, centre - halfWidth * 2.1);
  context.lineTo(front + reach, centre + halfWidth * 2.1);
  context.lineTo(front, centre + halfWidth * 0.6);
  context.closePath();
  context.fill();
}

function drawStreetLife(t, left, top, width, height) {
  if (!state.life) return;
  drawTram(t, left, top, width, height);
  drawShuttle(t, left, top, width, height);
  for (const [start, y, end, speed, phase, direction, color] of state.life.cars) {
    const length = end - start;
    const progress = (t * speed / length + phase) % 1;
    const x = direction > 0 ? start + length * progress : end - length * progress;
    if (underTunnel(x, y) || !seen(x, y, left, top, width, height)) continue;
    context.save();
    context.translate(x, y);
    context.scale(direction, 1);
    if (state.night) drawBeam(15, 0, 9);  // Headlights reach ahead of the car
    context.fillStyle = color;
    context.strokeStyle = "#435c5c";
    context.lineWidth = 1;
    context.beginPath();
    roundedRect(-15, -8, 30, 16, 5);
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

// Of the vehicles, only the motorcycle shows its rider: repaint their jacket, hand and helmet in the player's
// colours (the car, van and F1 car hide the driver). Each look is built once from the SVG's text.
const RIDER_COLOURS = { "#3d7eaa": "outfit", "#efb78c": "skin", "#20343f": "accent" };
const riderArt = new Map();
let riderSource = null;
function loadRider() {
  if (typeof fetch !== "function") return;
  fetch(asset("vehicles/motorcycle.svg")).then(response => response.text()).then(text => { riderSource = text; })
    .catch(() => {});  // Without it, the motorcycle keeps its original rider
}

function vehicleImage(key) {
  const colours = state.player_colors;
  if (key !== "motorcycle" || !riderSource || !colours) return vehicleArt[key];
  const look = [colours.outfit, colours.skin, colours.accent].join();
  if (!riderArt.has(look)) {
    let svg = riderSource;
    for (const [original, part] of Object.entries(RIDER_COLOURS)) svg = svg.split(original).join(colours[part]);
    const image = new Image();
    image.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    riderArt.set(look, image);
  }
  const art = riderArt.get(look);
  return art.complete && art.naturalWidth ? art : vehicleArt[key];
}

// The player's look comes from Python (browser_game.player_shapes), which also draws the character editor's
// preview from the same list. This is the original figure, used until the first update arrives.
const DEFAULT_PLAYER = [
  ["rect", -6, -8, 5, 9, "#192c39"], ["rect", 2, -8, 5, 9, "#192c39"], ["rect", -8, -19, 16, 12, "#397fa0"],
  ["rect", -5, -27, 11, 9, "#eeb181"], ["rect", -7, -30, 13, 5, "#ffd072"], ["rect", 4, -27, 6, 3, "#ffd072"],
];

function drawWalker() {
  const shapes = (state && state.player) || DEFAULT_PLAYER;
  for (const shape of shapes) {
    const [kind] = shape;
    if (kind === "rect") {
      const [, x, y, w, h, colour] = shape;
      context.fillStyle = colour;
      context.fillRect(x, y, w, h);
    } else if (kind === "poly") {
      context.fillStyle = shape[2];
      context.beginPath();
      shape[1].forEach(([x, y], index) => (index ? context.lineTo(x, y) : context.moveTo(x, y)));
      context.closePath();
      context.fill();
    } else if (kind === "ring") {  // A see-through helmet visor
      const [, x, y, w, h, colour] = shape;
      context.beginPath();
      context.roundRect(x, y, w, h, 5);
      context.globalAlpha = 0.25;
      context.fillStyle = colour;
      context.fill();
      context.globalAlpha = 1;
      context.strokeStyle = colour;
      context.lineWidth = 1.5;
      context.stroke();
    }
  }
}

// ----- Inside a building: the desktop game's scene, the vendor's words and the keys -----
const SPIN_SECONDS = 4.5;
const POCKETS = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14,
                 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
const REDS = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

let sceneOnScreen = null;

function fitScene(width, height) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (canvas.width !== Math.round(w * ratio) || canvas.height !== Math.round(h * ratio)) {
    canvas.width = Math.round(w * ratio);
    canvas.height = Math.round(h * ratio);
  }
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.fillStyle = "#1f2a30";
  context.fillRect(0, 0, w, h);
  const scale = Math.min(w / width, h / height);
  sceneOnScreen = { scale, left: (w - width * scale) / 2, top: (h - height * scale) / 2, width };
  context.setTransform(ratio * scale, 0, 0, ratio * scale, ratio * (w - width * scale) / 2,
                       ratio * (h - height * scale) / 2);
}

// The garage showroom (800 x 400): a card under each vehicle's turntable.
const SHOWROOM_X = [85, 245, 405, 565];

function drawShowroom(showroom) {
  showroom.forEach((ride, index) => {
    const x = SHOWROOM_X[index];
    const left = x - 74;
    const top = 333;
    const border = ride.status === "current" ? "#ffc66c" : ride.status === "owned" ? "#7ee0a1" : "#9aaeb3";
    context.fillStyle = "#16303aee";
    context.strokeStyle = border;
    context.lineWidth = ride.status === "buy" ? 1.5 : 2.5;
    context.beginPath();
    roundedRect(left, top, 148, 41, 7);
    context.fill();
    context.stroke();
    // Key to press, then the name.
    context.fillStyle = "#fff3dc";
    context.beginPath();
    roundedRect(left + 6, top + 5, 15, 15, 3);
    context.fill();
    context.fillStyle = "#1f2a30";
    context.font = "bold 10px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(String(ride.number), left + 13.5, top + 13);
    context.textAlign = "left";
    context.fillStyle = "#fff3dc";
    context.font = "bold 10.5px system-ui, sans-serif";
    context.fillText(ride.label, left + 26, top + 13);
    // The price, or a badge on the card's top edge for a vehicle the player already has.
    if (ride.status === "buy") {
      context.textAlign = "right";
      context.fillStyle = ride.affordable ? "#ffc66c" : "#ff9b8f";
      context.font = "bold 12px system-ui, sans-serif";
      context.fillText("$" + ride.price, left + 142, top + 13);
    } else {
      const badge = ride.status === "owned" ? "ALREADY OWNED" : "YOUR RIDE";
      context.font = "bold 8.5px system-ui, sans-serif";
      const badgeWidth = context.measureText(badge).width + 14;
      context.fillStyle = border;
      context.beginPath();
      roundedRect(x - badgeWidth / 2, top - 7, badgeWidth, 13, 6);
      context.fill();
      context.fillStyle = "#16303a";
      context.textAlign = "center";
      context.fillText(badge, x, top - 0.5);
    }
    // What it does for you.
    context.textAlign = "left";
    context.fillStyle = "#c8d6d8";
    context.font = "500 8.5px system-ui, sans-serif";
    context.fillText(`Trunk +${ride.trunk}  ·  ${ride.cargo} cargo slots`, left + 8, top + 26);
    context.fillText(`Road ${ride.road}  ·  Off-road ${ride.offroad}`, left + 8, top + 36);
    context.textBaseline = "alphabetic";
  });
}

function wrapLines(text, width) {
  const lines = [];
  let line = "";
  for (const word of String(text).split(/\s+/)) {
    const trial = line ? `${line} ${word}` : word;
    if (line && context.measureText(trial).width > width) {
      lines.push(line);
      line = word;
    } else {
      line = trial;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function textInBox(text, [left, top, right, bottom], size, color, weight = "bold") {
  if (!text) return;
  context.font = `${weight} ${size}px system-ui, sans-serif`;
  context.fillStyle = color;
  context.textAlign = "center";
  context.textBaseline = "middle";
  const lines = wrapLines(text, right - left - size * 2);
  const lineHeight = size * 1.25;
  const startY = (top + bottom) / 2 - (lines.length - 1) * lineHeight / 2;
  lines.forEach((line, index) => context.fillText(line, (left + right) / 2, startY + index * lineHeight));
  context.textBaseline = "alphabetic";
}

// ----- The building's buttons: a bar under the scene (so they never cover it), clickable, each with its key -----
let sceneButtons = [];  // [{key, left, top, width, height}] in scene pixels, for clicks
let hoveredKey = null;
const KEY_NAMES = { escape: "Esc", "shift+f": "Shift+F" };
const BUTTON_BAR = 32;  // Height of the bar under the scene, in 640-wide scene pixels
const BUTTON_STYLES = {
  secondary: { fill: "#1b1f27", border: "#4b505a", text: "#fafafa" },
  red: { fill: "#ff4b4b", border: "#ff4b4b", text: "#ffffff" },
  green: { fill: "#1f8a4c", border: "#46be79", text: "#ffffff" },
  selected: { fill: "#1b1f27", border: "#ff4b4b", text: "#ff4b4b" },
};

function keycapWidth(name, unit) {
  context.font = `700 ${7 * unit}px system-ui, sans-serif`;
  return Math.max(13 * unit, context.measureText(name).width + 8 * unit);
}

// A small keyboard key with the key's name on it, its left edge at x, centred on y.
function keycap(name, x, y, unit) {
  const width = keycapWidth(name, unit);
  const height = 13 * unit;
  context.fillStyle = "#a9a49a";  // The key's lower edge
  context.beginPath();
  roundedRect(x, y - height / 2 + 1.5 * unit, width, height, 3 * unit);
  context.fill();
  context.fillStyle = "#f4f1ea";
  context.beginPath();
  roundedRect(x, y - height / 2, width, height - 1 * unit, 3 * unit);
  context.fill();
  context.fillStyle = "#2b2f36";
  context.textAlign = "center";
  context.fillText(name, x + width / 2, y - 0.2 * unit);
}

function drawButton({ key, label, keyName = KEY_NAMES[key] || key.toUpperCase(), style = "secondary", disabled = false },
                    left, top, width, height, unit) {
  const look = BUTTON_STYLES[style];
  const hovered = !disabled && hoveredKey === key;
  context.globalAlpha = disabled ? 0.45 : 1;
  context.fillStyle = look.fill;
  context.strokeStyle = hovered ? "#ffffff" : look.border;
  context.lineWidth = (hovered ? 1.6 : 1) * unit;
  context.beginPath();
  roundedRect(left, top, width, height, 6 * unit);
  context.fill();
  context.stroke();
  context.textBaseline = "middle";
  const capWidth = keyName ? keycapWidth(keyName, unit) + 6 * unit : 0;
  context.font = `500 ${9 * unit}px system-ui, sans-serif`;
  const labelWidth = context.measureText(label).width;
  const start = left + (width - labelWidth - capWidth) / 2;
  context.textAlign = "left";
  context.fillStyle = look.text;
  context.fillText(label, start, top + height / 2 + 0.5 * unit);
  if (keyName) keycap(keyName, start + labelWidth + 6 * unit, top + height / 2, unit);
  context.textBaseline = "alphabetic";
  context.globalAlpha = 1;
  if (!disabled) sceneButtons.push({ key, left, top, width, height });
}

// A row of equal buttons between left and right, like Streamlit columns.
function buttonRow(buttons, left, right, top, height, unit, gap = 8 * unit) {
  const width = (right - left - gap * (buttons.length - 1)) / buttons.length;
  buttons.forEach((button, index) => drawButton(button, left + index * (width + gap), top, width, height, unit));
}

function drawButtons(room, unit, spinning) {
  const [width, height] = room.size;
  sceneButtons = [];
  const bar = BUTTON_BAR * unit;
  const size = 21 * unit;
  const margin = 10 * unit;
  const top = height + (bar - size) / 2;
  context.fillStyle = "#11161c";
  context.fillRect(0, height, width, bar);
  // Leave always sits at the right end of the bar.
  const capWidth = keycapWidth("Esc", unit);
  context.font = `500 ${9 * unit}px system-ui, sans-serif`;
  const leaveWidth = context.measureText("Leave").width + capWidth + 30 * unit;
  const leaveLeft = width - margin - leaveWidth;
  drawButton({ key: "escape", label: "Leave" }, leaveLeft, top, leaveWidth, size, unit);
  if (room.showroom) {  // The vehicle cards themselves are the buttons
    room.showroom.forEach((ride, index) => {
      if (ride.status !== "current") {
        sceneButtons.push({ key: String(ride.number), left: SHOWROOM_X[index] - 74, top: 333, width: 148, height: 41 });
      }
    });
    return;
  }
  const actions = room.keys.filter(([key]) => key !== "escape");
  const right = leaveLeft - margin * 1.5;
  if (room.casino) {
    const chips = room.casino.chips.map(value => ({
      key: `chip-${value}`, label: `$${value}`, keyName: "", disabled: spinning,
      style: value === room.casino.chip ? "selected" : "secondary",
    }));
    const chipRight = margin + width * 0.26;
    buttonRow(chips, margin, chipRight, top, size, unit, 3 * unit);
    const styles = { 1: "red", 2: "secondary", 3: "green" };
    buttonRow(actions.map(([key, label]) => ({ key, label, style: styles[key], disabled: spinning })),
              chipRight + margin * 1.5, right, top, size, unit);
    return;
  }
  if (actions.length) buttonRow(actions.map(([key, label]) => ({ key, label })), margin, right, top, size, unit);
}

function sceneButtonAt(event) {
  if (!state || !state.interior || !sceneOnScreen) return null;
  const rect = canvas.getBoundingClientRect();
  const x = (event.clientX - rect.left - sceneOnScreen.left) / sceneOnScreen.scale;
  const y = (event.clientY - rect.top - sceneOnScreen.top) / sceneOnScreen.scale;
  return sceneButtons.find(b => x >= b.left && x <= b.left + b.width && y >= b.top && y <= b.top + b.height) || null;
}

canvas.addEventListener("pointermove", (event) => {
  const button = sceneButtonAt(event);
  hoveredKey = button ? button.key : null;
  canvas.style.cursor = button ? "pointer" : "";
});
canvas.addEventListener("pointerdown", (event) => {
  const button = sceneButtonAt(event);
  if (!button || !state.interior.accepts.includes(button.key)) return;
  event.preventDefault();
  canvas.focus({ preventScroll: true });
  queuedAction = button.key === "escape" ? "leave" : "building";
  queuedKey = button.key;
});

function drawInterior() {
  const room = state.interior;
  const [width, height] = room.size;
  fitScene(width, height + BUTTON_BAR * width / 640);  // Room for the button bar under the scene
  if (room.scene) {
    if (!sceneArt[room.scene]) {
      sceneArt[room.scene] = new Image();
      sceneArt[room.scene].src = asset(`scenes/${room.scene}.webp`);
    }
    const art = sceneArt[room.scene];
    if (art.complete && art.naturalWidth) context.drawImage(art, 0, 0, width, height);
  } else {
    context.fillStyle = "#16303a";
    context.fillRect(0, 0, width, height);
    textInBox(room.speech, [40, 120, width - 40, height - 120], 18, "#fff3dc", "600");
  }
  const unit = width / 640;
  const spinning = room.casino && spinAnimation && performance.now() - spinAnimation.start < SPIN_SECONDS * 1000;
  if (room.casino) {
    drawWheel(room.casino);
    if (!spinning) {
      context.shadowColor = "#000";
      context.shadowBlur = 4;
      textInBox(room.speech, [0, height * 0.78, width, height * 0.88], 15 * unit, "#fff7e6");
      context.shadowBlur = 0;
    }
  } else if (room.bubble) {
    textInBox(room.speech, room.bubble, 12 * (640 / width) * unit, "#1f2a30");
  }
  if (room.board && room.board_text) {
    const [left, top, right, bottom] = room.board;
    textInBox(room.board_text, [left + 6, top + 22, right - 6, bottom - 4], 8.5, "#eef3ea", "500");
  }
  if (room.showroom) drawShowroom(room.showroom);
  // Title and the keys that work here. The garage has its own sign board for its name.
  context.font = `bold ${11 * unit}px system-ui, sans-serif`;
  const title = room.title;
  if (room.scene === "garage") {
    context.font = "bold 15px system-ui, sans-serif";
    context.textAlign = "center";
    context.fillStyle = "#f6e7b4";
    context.fillText(title.toUpperCase(), 157, 38);
  } else {
    context.textAlign = "left";
    context.fillStyle = "#1f2a30d9";
    context.fillRect(8 * unit, 8 * unit, context.measureText(title).width + 16 * unit, 20 * unit);
    context.fillStyle = "#f6e7b4";
    context.fillText(title, 16 * unit, 22 * unit);
  }
  drawButtons(room, unit, spinning);
  if (room.scene === "monastery" || room.scene === "nova_presentation") return;
  drawTimer();
  drawHint("interior");
  drawAlert();
}

// ----- Overlays in screen pixels: the production countdown and the next-move hint -----
let alertBanner = null;
let lastAlertId = null;
const ALERT_SECONDS = 3.5;

function drawAlert() {
  if (!alertBanner) return;
  const age = (performance.now() - alertBanner.start) / 1000;
  if (age > ALERT_SECONDS) {
    alertBanner = null;
    return;
  }
  const { width } = screenSpace();
  context.globalAlpha = Math.min(1, (ALERT_SECONDS - age) / 0.5);  // Fade out at the end
  context.font = "bold 16px system-ui, sans-serif";
  const boxWidth = Math.min(width - 28, context.measureText(alertBanner.text).width + 40);
  const x = (width - boxWidth) / 2;
  context.fillStyle = "#b3261ef2";
  context.strokeStyle = "#ffb4ab";
  context.lineWidth = 2;
  context.beginPath();
  roundedRect(x, 14, boxWidth, 40, 10);
  context.fill();
  context.stroke();
  context.fillStyle = "#ffffff";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(alertBanner.text, width / 2, 35, boxWidth - 24);
  context.textBaseline = "alphabetic";
  context.globalAlpha = 1;
}

function screenSpace() {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { width: canvas.clientWidth, height: canvas.clientHeight };
}

function card(x, y, width, height, border) {
  context.fillStyle = "#101f28e6";
  context.strokeStyle = border;
  context.lineWidth = 2;
  context.beginPath();
  roundedRect(x, y, width, height, 10);
  context.fill();
  context.stroke();
}

function productionSecondsLeft(timer) {
  return Math.max(0, timer.seconds - (performance.now() - productionUpdatedAt) / 1000);
}

function drawTimer() {
  const timers = state.production || [];
  if (!timers.length) return;
  const { width } = screenSpace();
  timers.forEach((timer, index) => {
    const left = productionSecondsLeft(timer);
    const ready = left <= 0;
    const text = timer.quantity + " " + timer.product + (ready ? " · Ready to collect" : " · " + Math.ceil(left) + "s left");
    context.font = "bold 17px system-ui, sans-serif";
    const boxWidth = Math.min(width - 28, context.measureText(text).width + 62);
    const x = width - boxWidth - 14;
    const top = 14 + index * 54;
    card(x, top, boxWidth, 46, ready ? "#7ee0a1" : "#ffc66c");
    // A small clock whose hand sweeps once per second.
    const cx = x + 24;
    const cy = top + 23;
    context.strokeStyle = ready ? "#7ee0a1" : "#ffc66c";
    context.lineWidth = 2.5;
    context.beginPath();
    context.arc(cx, cy, 11, 0, Math.PI * 2);
    context.stroke();
    const angle = ready ? -Math.PI / 2 : (left % 1) * Math.PI * 2 - Math.PI / 2;
    context.beginPath();
    context.moveTo(cx, cy);
    context.lineTo(cx + 8 * Math.cos(angle), cy + 8 * Math.sin(angle));
    context.stroke();
    context.fillStyle = "#fff3dc";
    context.textAlign = "left";
    context.textBaseline = "middle";
    context.fillText(text, x + 44, top + 24, boxWidth - 54);
    context.textBaseline = "alphabetic";
  });
}

function drawHint(where) {
  if (!state.next_move || ferry) return;
  const { width } = screenSpace();
  const boxWidth = Math.min(340, width * 0.42);
  context.font = "600 14px system-ui, sans-serif";
  const lines = wrapLines(state.next_move.text, boxWidth - 62);
  const boxHeight = 22 + lines.length * 19;
  // Always on the left, so it doesn't jump sides when entering or leaving. Inside it sits just under
  // the building name (the garage's name is on its sign board), clear of the vendor's speech bubble.
  const x = 14;
  let y = 14;
  if (where === "interior" && sceneOnScreen) {
    const unit = sceneOnScreen.width / 640;
    const nameBottom = state.interior.scene === "garage" ? 52 : 30 * unit;
    y = sceneOnScreen.top + nameBottom * sceneOnScreen.scale + 6;
  }
  card(x, y, boxWidth, boxHeight, "#ffd072");
  // The light bulb.
  const bx = x + 24;
  const by = y + 22;
  context.fillStyle = "#ffd072";
  context.beginPath();
  context.arc(bx, by, 10, Math.PI * 0.8, Math.PI * 2.2);
  context.lineTo(bx + 5, by + 12);
  context.lineTo(bx - 5, by + 12);
  context.closePath();
  context.fill();
  context.fillStyle = "#c9cfd2";
  context.fillRect(bx - 5, by + 13, 10, 5);
  context.fillStyle = "#fff3dc";
  context.textAlign = "left";
  context.textBaseline = "middle";
  lines.forEach((line, index) => context.fillText(line, x + 46, y + 20 + index * 19));
  context.textBaseline = "alphabetic";
}

function drawWheel(casino) {
  const seg = (Math.PI * 2) / POCKETS.length;
  const spin = casino.spin;
  let angle = spin ? spin.angle : 0;
  let ball = 0;
  if (spinAnimation && spin && spinAnimation.spin.id === spin.id) {
    const t = Math.min(1, (performance.now() - spinAnimation.start) / (SPIN_SECONDS * 1000));
    const ease = 1 - (1 - t) ** 3;
    angle = spin.from + (spin.angle - spin.from) * ease;
    ball = 1440 * (1 - ease);
  }
  context.save();
  context.translate(600, 268);
  context.scale(1.2, 1.2);
  const ring = (radius, color) => {
    context.fillStyle = color;
    context.beginPath();
    context.arc(0, 0, radius, 0, Math.PI * 2);
    context.fill();
  };
  ring(198, "#4a2614");
  ring(192, "#7a4424");
  context.save();
  context.rotate((angle * Math.PI) / 180);
  POCKETS.forEach((number, index) => {
    const a0 = index * seg - seg / 2 - Math.PI / 2;
    const a1 = index * seg + seg / 2 - Math.PI / 2;
    context.fillStyle = number === 0 ? "#1f8a4c" : REDS.has(number) ? "#c8313c" : "#1b1d22";
    context.strokeStyle = "#c9a24a";
    context.lineWidth = 1;
    context.beginPath();
    context.arc(0, 0, 190, a0, a1);
    context.arc(0, 0, 140, a1, a0, true);
    context.closePath();
    context.fill();
    context.stroke();
    context.save();
    context.rotate(index * seg);
    context.fillStyle = "#fff";
    context.font = "bold 13px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(String(number), 0, -166);
    context.restore();
  });
  ring(140, "#6b3d22");
  ring(100, "#8a5a33");
  ring(55, "#b07a45");
  context.strokeStyle = "#ffc66c";
  context.lineWidth = 6;
  context.lineCap = "round";
  context.beginPath();
  context.moveTo(0, -60); context.lineTo(0, 60); context.moveTo(-60, 0); context.lineTo(60, 0);
  context.stroke();
  ring(16, "#ffc66c");
  context.restore();
  context.save();
  context.rotate((ball * Math.PI) / 180);
  context.fillStyle = "#f7f7f2";
  context.strokeStyle = "#9aa3a6";
  context.beginPath();
  context.arc(0, spin ? -152 : -178, 7, 0, Math.PI * 2);
  context.fill();
  context.stroke();
  context.restore();
  context.fillStyle = "#ffc66c";
  context.beginPath();
  context.moveTo(-8, -196); context.lineTo(8, -196); context.lineTo(0, -182);
  context.closePath();
  context.fill();
  context.restore();
  context.textBaseline = "alphabetic";
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
  if (!art.getAttribute("src")) art.src = asset(night ? "scenes/ferry_night.webp" : "scenes/ferry_day.webp");
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
// These buttons live outside the map iframe, but their shortcuts work in both places.
const HUD_SHORTCUTS = {
  i: ".st-key-inventory button",
  f: ".st-key-show_suggested_route button",
  g: ".st-key-destination button",
};

function handleHudShortcut(event) {
  const key = event.key.toLowerCase();
  const selector = HUD_SHORTCUTS[key];
  if (!selector || event.defaultPrevented || event.repeat || event.ctrlKey || event.metaKey || event.altKey) return false;
  if (event.shiftKey && key !== "i") return false;
  if (ferry) return false;
  for (const page of pageDocuments()) {
    const button = page.querySelector(selector);
    if (!button || button.disabled) continue;
    const expanded = button.getAttribute?.("aria-expanded") === "true";
    const closingDestination = key === "g" && expanded &&
      page.activeElement === page.querySelector(".st-key-destination [role=combobox]");
    const dialogs = key === "i" && expanded
      ? '[role="dialog"]:not([data-testid="stPopoverBody"][aria-label="Inventory"])' : undefined;
    if ((!closingDestination && typingOnPage()) || dialogOpen(dialogs)) return false;
    if (key === "f") {
      if (queuedAction) return false;
      queuedAction = "toggle_suggested_route";
    } else {
      button.click();
      if (expanded) canvas.focus({ preventScroll: true });
    }
    event.preventDefault();
    return true;
  }
  return false;
}

function handleInteriorEscape(event) {
  if (event.key !== "Escape" || event.defaultPrevented || event.repeat ||
      event.ctrlKey || event.metaKey || event.altKey || event.shiftKey ||
      ferry || !state?.interior?.accepts.includes("escape") || dialogOpen()) return;
  if (pageDocuments().some(page => page.querySelector('[role="combobox"][aria-expanded="true"]'))) return;
  event.preventDefault();
  queuedAction = "leave";
  queuedKey = "escape";
}

const shortcutPages = pageDocuments();
for (const page of shortcutPages) {
  page.addEventListener("keydown", handleHudShortcut, true);
  page.addEventListener("keydown", handleInteriorEscape, true);
}
document.addEventListener("keydown", handleInteriorEscape);
window.addEventListener("pagehide", (event) => {
  if (event.persisted) return;
  for (const page of shortcutPages) {
    page.removeEventListener("keydown", handleHudShortcut, true);
    page.removeEventListener("keydown", handleInteriorEscape, true);
  }
});

canvas.addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  if (key === "m" && !ferry && shortcutPages.some(page => page.defaultView?.foundryMenuShortcut?.(event))) return;
  if (handleHudShortcut(event)) return;
  if (ferry) {
    if (key === "escape") ferry = null;
    event.preventDefault();
    return;
  }
  if (state && state.interior) {
    const name = event.shiftKey && key === "f" ? "shift+f" : key;
    if (name === "escape" || !state.interior.accepts.includes(name)) return;
    event.preventDefault();
    if (event.repeat) return;
    queuedAction = "building";
    queuedKey = name;
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
    canvas.focus({ preventScroll: true });
    button.setPointerCapture(event.pointerId);
    held.set(event.pointerId, button.dataset.direction);
  });
  for (const eventName of ["pointerup", "pointercancel", "lostpointercapture"]) {
    button.addEventListener(eventName, (event) => held.delete(event.pointerId));
  }
}

for (const button of document.querySelectorAll("[data-action]")) {
  button.addEventListener("click", () => {
    canvas.focus({ preventScroll: true });
    queuedAction = button.dataset.action;
  });
}

new ResizeObserver(frameHeight).observe(document.body);
if (parentOrigin === location.origin && window.parent !== window) {
  const layout = window.frameElement?.closest(".st-key-foundry_play");
  const layoutObserver = new ResizeObserver(frameHeight);
  if (layout) layoutObserver.observe(layout);
  window.parent.addEventListener?.("resize", frameHeight);
  window.addEventListener("pagehide", () => {
    layoutObserver.disconnect();
    window.parent.removeEventListener?.("resize", frameHeight);
  });
}
send("streamlit:componentReady", { apiVersion: 1 });
frameHeight();
requestAnimationFrame(frame);
