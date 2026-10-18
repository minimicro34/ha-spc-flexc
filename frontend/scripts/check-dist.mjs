import { readFile } from "node:fs/promises";

const packageMetadata = JSON.parse(await readFile("package.json", "utf8"));
const CARD_VERSION = packageMetadata.version;
const [
  coreSource,
  outputs,
  zoneIsolation,
  zoneGroups,
  translations,
  areaCards,
  communication,
  xbus,
  responsive,
  renderScheduler,
  distribution,
] = await Promise.all([
  readFile("src/ha-spc-flexc-card.js", "utf8"),
  readFile("src/spc-flexc-outputs.js", "utf8"),
  readFile("src/spc-flexc-zone-isolation.js", "utf8"),
  readFile("src/spc-flexc-zone-groups.js", "utf8"),
  readFile("src/spc-flexc-i18n.js", "utf8"),
  readFile("src/spc-flexc-area-cards.js", "utf8"),
  readFile("src/spc-flexc-communication.js", "utf8"),
  readFile("src/spc-flexc-xbus.js", "utf8"),
  readFile("src/spc-flexc-responsive.js", "utf8"),
  readFile("src/spc-flexc-render-scheduler.js", "utf8"),
  readFile("../custom_components/spc_flexc/www/ha-spc-flexc-card.js", "utf8"),
]);

const core = coreSource.replace(
  /^const CARD_VERSION = "[^"]+";/,
  `const CARD_VERSION = "${CARD_VERSION}";`
);
const source = `${core.trimEnd()}\n\n${outputs.trim()}\n\n${zoneIsolation.trim()}\n\n${zoneGroups.trim()}\n\n${translations.trim()}\n\n${areaCards.trim()}\n\n${communication.trim()}\n\n${xbus.trim()}\n\n${responsive.trim()}\n\n${renderScheduler.trimStart()}`;

if (source !== distribution) {
  console.error(
    "ha-spc-flexc-card.js is out of date. Run: npm run build"
  );
  process.exit(1);
}

console.log(`Distribution file v${CARD_VERSION} is up to date.`);
