const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

function browser() {
  const sent = [];
  const listeners = {};
  const canvas = { addEventListener() {}, getContext: () => ({}), clientWidth: 800, clientHeight: 450 };
  const parent = { postMessage: message => sent.push(message) };
  class Image {
    getAttribute() { return this.src; }
  }
  const window = { parent, addEventListener: (name, callback) => { listeners[name] = callback; } };
  const document = {
    referrer: "http://localhost/", hidden: false, activeElement: canvas,
    hasFocus: () => true, body: { offsetHeight: 500 },
    querySelector: selector => selector === "#map" ? canvas : { textContent: "" },
    querySelectorAll: () => [],
    addEventListener() {},
  };
  const scope = vm.createContext({
    window, document, Image, URL, location: { origin: "http://localhost" },
    ResizeObserver: class { observe() {} }, requestAnimationFrame() {}, setTimeout() {},
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
  assert.equal(b.run("night.src"), "world_100_night.webp");
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
