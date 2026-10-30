import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Script } from "node:vm";
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
