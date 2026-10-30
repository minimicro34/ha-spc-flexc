import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Script, runInNewContext } from "node:vm";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const packageInfo = JSON.parse(read("../frontend/package.json"));
const frontend = read("../custom_components/spc_flexc/www/ha-spc-flexc-card.js");
const source = read("../frontend/src/ha-spc-flexc-card.js");
const registration = read("../custom_components/spc_flexc/frontend.py");

test("bundled Lovelace card is valid JavaScript", () => {
  assert.doesNotThrow(() => new Script(frontend));
});

test("bundled card version matches frontend package", () => {
  assert.match(frontend, new RegExp('^const CARD_VERSION = "' + packageInfo.version.replaceAll(".", "\\.") + '";'));
});

test("bundled card exposes its custom element", () => {
  assert.match(frontend, /customElements\.define\(/);
  assert.match(frontend, /spc-flexc-card/);
});

test("bundled card preserves panel-specific registry scoping", () => {
  assert.match(source, /_scopedStates\(includeIntegration = false\)/);
  assert.match(source, /_scopeEntityIds\(/);
});

test("bundled card includes existing communication and X-BUS diagnostics", () => {
  assert.match(frontend, /_renderFlexcCommunication/);
  assert.match(frontend, /_getXBusDevices/);
});

test("bundled resource is registered from the integration", () => {
  assert.match(registration, /\/spc_flexc\/ha-spc-flexc-card\.js/);
  assert.match(registration, /www" \/ "ha-spc-flexc-card\.js"/);
});

test("bundled card does not depend on standalone HACS resource", () => {
  assert.match(registration, /_LEGACY_PATHS/);
  assert.match(registration, /Migrated standalone SPC FlexC Card Lovelace resource/);
});

function cardClass() {
  const registered = new Map();
  class MockElement {
    constructor() { this.innerHTML = ""; this.style = { minHeight: "" }; }
    getBoundingClientRect() { return { height: 0 }; }
    querySelector() { return null; }
    querySelectorAll() { return []; }
    addEventListener() {}
    removeEventListener() {}
  }
  const document = {
    createElement(tag) {
      if (tag === "template") {
        return {
          set innerHTML(html) {
            this.content = { querySelector: () => ({
              innerHTML: html,
              querySelector: () => null,
              querySelectorAll: () => [],
            }) };
          },
        };
      }
      return new MockElement();
    },
  };
  const context = {
    HTMLElement: MockElement,
    customElements: {
      define(name, klass) { registered.set(name, klass); },
      get(name) { return registered.get(name); },
    },
    document,
    navigator: { language: "en" },
    window: { customCards: [], setTimeout(callback) { callback(); return 0; }, clearTimeout() {} },
    console,
    Intl,
    Date,
    Map,
    Set,
    Promise,
    setTimeout() { return 0; },
    clearTimeout() {},
  };
  runInNewContext(frontend, context);
  const Card = registered.get("spc-flexc-card");
  assert.ok(Card, "bundled card must register its custom element");
  return Card;
}

test("card selects a system alarm entity for its default config", () => {
  const Card = cardClass();
  const config = Card.getStubConfig({ states: {
    "alarm_control_panel.garage": { attributes: {} },
    "alarm_control_panel.spc": { attributes: { areas: { 1: {} } } },
  } });
  assert.equal(config.entity, "alarm_control_panel.spc");
});

test("card rejects configuration without an alarm entity", () => {
  const Card = cardClass();
  const card = new Card();
  assert.throws(() => card.setConfig({}), /requires an alarm_control_panel entity/);
});

test("card escapes untrusted text before HTML rendering", () => {
  const Card = cardClass();
  const card = new Card();
  assert.equal(card._escapeHtml('<script a="x">&</script>'), "&lt;script a=&quot;x&quot;&gt;&amp;&lt;/script&gt;");
});

test("card treats missing alarm entity as an error rather than arming another panel", () => {
  const Card = cardClass();
  const card = new Card();
  card._config = { entity: "alarm_control_panel.missing" };
  card._hass = { states: {}, locale: { language: "en" } };
  card._t = (key) => key;
  card._render();
  assert.match(card.innerHTML, /card\.entity_not_found/);
});

test("card state labels distinguish triggered and disarmed", () => {
  const Card = cardClass();
  const card = new Card();
  card._t = (key) => key;
  assert.equal(card._stateLabel("triggered"), "state.alarm");
  assert.equal(card._stateLabel("disarmed"), "state.disarmed");
  assert.equal(card._stateClass("triggered"), "danger");
  assert.equal(card._stateClass("disarmed"), "ok");
});

test("card does not show empty technical diagnostic fields", () => {
  const Card = cardClass();
  const card = new Card();
  assert.equal(card._technicalLine("Battery", null), "");
  assert.equal(card._technicalLine("Battery", "  "), "");
  assert.match(card._technicalLine("Battery", "<5"), /&lt;5/);
});

test("system diagnostics never include faults from a different panel", () => {
  const Card = cardClass();
  const card = new Card();
  card._hass = { states: {
    "binary_sensor.panel_fault": { state: "on", attributes: { device_class: "problem", friendly_name: "Panel fault" } },
    "binary_sensor.other_fault": { state: "on", attributes: { device_class: "problem", friendly_name: "Other fault" } },
  }, locale: { language: "en" } };
  card._diagnosticScope = {
    entityIds: new Set(["binary_sensor.panel_fault"]),
    entryMap: new Map(),
  };
  const diagnostics = card._getSystemDiagnostics();
  assert.equal(diagnostics.scopeAvailable, true);
  assert.equal(diagnostics.faults.length, 1);
  assert.equal(diagnostics.faults[0].entityId, "binary_sensor.panel_fault");
});

test("missing registry scope is not interpreted as a healthy system", () => {
  const Card = cardClass();
  const card = new Card();
  card._hass = { states: {}, locale: { language: "en" } };
  const diagnostics = card._getSystemDiagnostics();
  assert.equal(diagnostics.scopeAvailable, false);
  assert.equal(diagnostics.connection, null);
  assert.equal(diagnostics.engineerMode, null);
  assert.equal(diagnostics.faults.length, 0);
});

test("technical diagnostic lines escape both labels and values", () => {
  const Card = cardClass();
  const card = new Card();
  const html = card._technicalLine("<Panel>", '"><img>');
  assert.match(html, /&lt;Panel&gt;/);
  assert.match(html, /&quot;&gt;&lt;img&gt;/);
  assert.doesNotMatch(html, /<img>/);
});

test("unknown alarm states never receive the armed or disarmed styling", () => {
  const Card = cardClass();
  const card = new Card();
  assert.equal(card._stateClass("unknown"), "muted");
  assert.equal(card._stateClass("unavailable"), "muted");
  assert.equal(card._stateClass("triggered"), "danger");
});

test("release metadata keeps bundled card and integration versions synchronized", () => {
  const manifest = JSON.parse(read("../custom_components/spc_flexc/manifest.json"));
  const lock = JSON.parse(read("../frontend/package-lock.json"));
  assert.equal(manifest.version, "1.1.5-beta.4");
  assert.equal(packageInfo.version, "1.0.20");
  assert.equal(lock.version, packageInfo.version);
  assert.equal(lock.packages[""].version, packageInfo.version);
  assert.match(registration, /_CARD_VERSION = "1\\.0\\.20"/);
});
