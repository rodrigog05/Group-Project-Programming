const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

function browser() {
  const sent = [];
  const listeners = {};
  const canvas = {
    addEventListener() {}, getContext: () => ({}), clientWidth: 800, clientHeight: 450,
    focus() { document.activeElement = canvas; },
  };
  const elements = {
    "#map": canvas,
    "#hint": { textContent: "" },
    "#route": { textContent: "" },
    '[data-action="vehicle"]': { querySelector: () => vehicleLabel },
    ".controls": {},
    "#settings": { addEventListener() {} },
    "#settings-panel": { hidden: true },
    "#music": { addEventListener() {} },
    "#soundtrack": {
      paused: true,
      async play() { this.paused = false; },
      pause() { this.paused = true; },
    },
  };
  const vehicleLabel = { textContent: "" };
  const parent = {
    document: { addEventListener() {}, querySelector: () => null },
    postMessage: message => sent.push(message),
  };
  parent.parent = parent;
  class Image {
    getAttribute() { return this.src; }
  }
  const window = { parent, addEventListener: (name, callback) => { listeners[name] = callback; } };
  const document = {
    referrer: "http://localhost/", hidden: false, activeElement: canvas,
    hasFocus: () => true, body: { offsetHeight: 500 },
    querySelector: selector => elements[selector] ?? null,
    querySelectorAll: () => [],
    addEventListener() {},
  };
  const scope = vm.createContext({
    window, document, Image, URL, location: { origin: "http://localhost" },
    localStorage: { getItem: () => null },
    ResizeObserver: class { observe() {} }, requestAnimationFrame() {}, setTimeout() {}, setInterval() {},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../street/street.js"), "utf8"), scope);
  const run = code => vm.runInContext(code, scope);
  const receive = args => listeners.message({
    source: parent, origin: "http://localhost",
    data: { type: "streamlit:render", args: {
      x: 480, y: 321, speed: 228, facing: 1, night: false,
      collision: { radius: 10, world: [2400, 114, 1780], boxes: [], parks: [],
        river: [740, 1160], tunnel: [0, 0, 0, 0], sand: [40, 260, 850],
        tower: [90, 735, 190, 850], vasco: 2070, toll: 3 },
      locations: [], hint: "", message: "", ...args,
    } },
  });
  receive({ ack: null });
  return { run, receive, sent, document };
}

test("movement continues during Python latency, then replays unacknowledged input", () => {
  const b = browser();
  b.run('held.set("d", "right"); update(100); update(120);');
  const first = b.run("player.x");
  assert.ok(first > 480);
  b.run("update(140); update(160);");
  assert.ok(b.run("player.x") > first);
  b.run("update(300);"); // send the first batch
  assert.equal(b.run("pending"), true);
  b.run("update(320); update(340);");
  const buffered = b.run("bufferedSeconds");
  b.receive({ ack: b.run("eventId"), x: 490 });
  assert.ok(Math.abs(b.run("player.x") - (490 + buffered * 228)) < .000001);
});

test("night image is deferred and only requested at night", () => {
  const b = browser();
  assert.equal(b.run("night.src"), undefined);
  b.receive({ night: true });
  assert.match(b.run("night.src"), /^world_100_night\.webp(?:\?v=[^&]+)?$/);
});

test("F activates the suggested route only when the button is available", () => {
  const b = browser();
  b.run(`
    const routeButton = { disabled: false };
    window.parent.document.querySelector = selector =>
      selector === ".st-key-show_suggested_route button" ? routeButton : null;
    const pressRoute = (options = {}) => handleHudShortcut({
      key: "f", preventDefault() {}, ...options,
    });
  `);
  assert.equal(b.run("pressRoute()"), true);
  assert.equal(b.run("queuedAction"), "toggle_suggested_route");
  b.run("update(100)");
  assert.equal(b.sent.at(-1).value.action, "toggle_suggested_route");
  assert.equal(b.run("pressRoute({ ctrlKey: true })"), false);
  assert.equal(b.run("pressRoute({ shiftKey: true })"), false);
  assert.equal(b.run("pressRoute({ repeat: true })"), false);
  assert.equal(b.run('window.parent.document.activeElement = { tagName: "INPUT" }; pressRoute()'), false);
  assert.equal(b.run("window.parent.document.activeElement = null; routeButton.disabled = true; pressRoute()"), false);
  assert.equal(b.run("queuedAction"), null);
});

test("G opens Destination without activating Show route", () => {
  const b = browser();
  b.run(`
    let opened = 0;
    const destination = { click() { opened++; } };
    window.parent.document.querySelector = selector =>
      selector === ".st-key-destination button" ? destination : null;
    const press = (key, options = {}) => handleHudShortcut({ key, preventDefault() {}, ...options });
  `);
  assert.equal(b.run('press("g")'), true);
  assert.equal(b.run('press("f")'), false);
  assert.equal(b.run('press("g", { repeat: true })'), false);
  assert.equal(b.run('press("g", { ctrlKey: true })'), false);
  assert.equal(b.run('window.parent.document.activeElement = { tagName: "INPUT" }; press("g")'), false);
  assert.equal(b.run("opened"), 1);
});

test("G and I can close their own control after it takes keyboard focus", () => {
  const b = browser();
  b.run(`
    const page = window.parent.document;
    const destinationInput = { tagName: "INPUT" };
    const inventoryDialog = {};
    const destination = {
      getAttribute() { return "true"; },
      click() { this.closed = true; },
    };
    const inventory = {
      getAttribute() { return "true"; },
      click() { this.closed = true; },
    };
    page.querySelector = selector => ({
      ".st-key-destination button": destination,
      ".st-key-destination [role=combobox]": destinationInput,
      ".st-key-inventory button": inventory,
      '[role="dialog"]': inventoryOpen ? inventoryDialog : null,
    })[selector] ?? null;
    let inventoryOpen = false;
    const press = key => handleHudShortcut({ key, preventDefault() {} });
    page.activeElement = destinationInput;
  `);
  assert.equal(b.run('press("g")'), true);
  assert.equal(b.run("destination.closed"), true);
  assert.equal(b.document.activeElement, b.run("canvas"));
  assert.equal(b.run('page.activeElement = inventory; inventoryOpen = true; press("i")'), true);
  assert.equal(b.run("inventory.closed"), true);
});

test("bulk buy is available only within reach with cash and cargo room", () => {
  const b = browser();
  const supplier = { x: 480, y: 321, trade: 3, cost: 4 };
  const available = () => b.run('tradeAvailable("bulk")');
  assert.equal(available(), false);
  b.receive({ cash: 60, free_slots: 12, suppliers: [supplier] });
  assert.equal(available(), true);
  b.run("player.x += 36");
  assert.equal(available(), false);
  b.receive({ cash: 60, free_slots: 0, suppliers: [supplier] });
  assert.equal(available(), false);
  b.receive({ cash: 1, free_slots: 12, suppliers: [supplier] });
  assert.equal(available(), false);
  b.receive({ cash: 60, free_slots: 12, suppliers: [{ ...supplier, trade: 0 }] });
  assert.equal(available(), true);
});

test("an action waits behind movement and pause excludes inactive time", () => {
  const b = browser();
  b.run('held.set("d", "right"); update(100); update(300); queuedAction="interact"; update(320);');
  const before = b.run("player.x");
  b.run("update(360);");
  assert.equal(b.run("player.x"), before);
  b.receive({ ack: b.run("eventId"), x: 500 });
  b.run("update(380);");
  assert.equal(b.sent.at(-1).value.action, "interact");
  b.run("pause();");
  b.document.activeElement = null;
  b.run("update(10000);");
  assert.equal(b.run("bufferedSeconds"), 0);
});

test("lake water blocks predicted movement while the shore stays walkable", () => {
  const { run } = browser();
  run("state.collision.lake = [905, 1650, 185, 40]");
  assert.equal(run("canWalk(905, 1650)"), false);
  assert.equal(run("canWalk(905, 1699)"), false);
  assert.equal(run("canWalk(905, 1715)"), true);
  assert.equal(run("canWalk(667, 1650)"), true);
});
