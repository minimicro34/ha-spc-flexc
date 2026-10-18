/* SPC FlexC Card X-BUS diagnostics. */

const spcFlexCXBusBaseStyles = SpcFlexCCard.prototype._styles;
const spcFlexCXBusBaseTechnicalSystem = SpcFlexCCard.prototype._renderTechnicalSystem;
const spcFlexCXBusBaseRender = SpcFlexCCard.prototype._render;

SpcFlexCCard.prototype._styles = function () {
  return `${spcFlexCXBusBaseStyles.call(this)}
    <style>
      .xbus-card { overflow:hidden; }
      .xbus-card > summary { list-style:none; }
      .xbus-card > summary::-webkit-details-marker { display:none; }
      .xbus-title { cursor:pointer; user-select:none; }
      .xbus-title-main { display:flex; align-items:center; gap:8px; min-width:0; }
      .xbus-title-main::before { content:"▸"; color:var(--secondary-text-color); font-size:12px; line-height:1; transition:transform 120ms ease; }
      .xbus-card[open] .xbus-title-main::before { transform:rotate(90deg); }
      .xbus-title-text { display:flex; flex-direction:column; min-width:0; }
      .xbus-title-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .xbus-title-model { color:var(--secondary-text-color); font-size:11px; font-weight:500; line-height:1.25; }
      .xbus-card-body { padding-top:4px; }
    </style>`;
};

SpcFlexCCard.prototype._xBusDeviceRegistryMap = function () {
  const scope = this._diagnosticScope;
  const devices = scope?.devices;
  if (!(devices instanceof Map)) return new Map();
  return devices;
};

SpcFlexCCard.prototype._xBusModelFromDiagnostics = function (device) {
  const type = Number(device.deviceType);
  const inputs = Number(device.inputCount);
  const outputs = Number(device.outputCount);

  if (type === 1) return "SPC Keypad";
  if (type === 7) return "SPC Comfort Keypad";
  if (type === 6 && inputs === 4 && outputs === 2) return "SPCA210";
  if (type === 2 && inputs === 8 && outputs === 2) return "SPCE650";
  if (type === 2 && inputs === 0 && outputs === 8) return "SPCE450";
  return null;
};

SpcFlexCCard.prototype._xBusModelLabel = function (model) {
  const value = String(model || "").trim();
  if (!value) return null;

  const language = String(this._hass?.locale?.language || navigator.language || "en")
    .toLowerCase();
  if (!language.startsWith("fr")) return value;

  return {
    "SPC Keypad": "Clavier SPC",
    "SPC Comfort Keypad": "Clavier confort SPC",
    SPCE650: "Transpondeur E/S SPCE650",
    SPCE450: "Transpondeur de sorties SPCE450",
    SPCA210: "Transpondeur de porte SPCA210",
  }[value] || value;
};

SpcFlexCCard.prototype._getXBusDevices = function () {
  const devices = new Map();
  const registryDevices = Array.isArray(this._diagnosticScope?.devices)
    ? this._diagnosticScope.devices
    : [];
  const registryDeviceMap = new Map(
    registryDevices.map((device) => [device.id, device])
  );

  const ensureDevice = (identity, deviceId) => {
    const key = String(identity);
    if (!devices.has(key)) {
      devices.set(key, {
        key,
        id: deviceId,
        name: null,
        model: null,
        deviceType: null,
        inputCount: null,
        outputCount: null,
        serialNumber: null,
        version: null,
        siaAddress: null,
        tamperFault: null,
        tamperInhibited: null,
        tamperIsolated: null,
        entities: [],
      });
    }
    return devices.get(key);
  };

  for (const { entityId, stateObj, registryEntry } of this._scopedStates(true)) {
    const attrs = stateObj?.attributes || {};
    const uniqueId = String(registryEntry?.unique_id || "");
    const match = uniqueId.match(/_xbus_([0-9A-Fa-f]+)_(.+)$/);
    const registryDevice = registryDeviceMap.get(registryEntry?.device_id);
    const serialNumber =
      attrs.serial_number ?? registryDevice?.serial_number ?? match?.[1] ?? null;
    const deviceId = attrs.xbus_device_id ?? null;
    const identity = serialNumber ?? deviceId;

    if (identity === null || identity === undefined) continue;

    const device = ensureDevice(identity, deviceId);
    const field = match?.[2] || null;

    device.name = attrs.xbus_device_name || attrs.name || device.name;
    device.model = registryDevice?.model || attrs.model || device.model;
    device.deviceType = attrs.device_type ?? device.deviceType;
    device.inputCount = attrs.input_count ?? device.inputCount;
    device.outputCount = attrs.output_count ?? device.outputCount;
    device.serialNumber = serialNumber ?? device.serialNumber;
    device.version = attrs.version ?? registryDevice?.sw_version ?? device.version;
    device.siaAddress = attrs.sia_address ?? device.siaAddress;

    if (attrs.tamper_fault !== undefined && attrs.tamper_fault !== null) device.tamperFault = attrs.tamper_fault === true;
    if (attrs.tamper_inhibited !== undefined && attrs.tamper_inhibited !== null) device.tamperInhibited = attrs.tamper_inhibited === true;
    if (attrs.tamper_isolated !== undefined && attrs.tamper_isolated !== null) device.tamperIsolated = attrs.tamper_isolated === true;
    if (field === "tamper_fault") {
      if (stateObj.state === "on") device.tamperFault = true;
      if (stateObj.state === "off") device.tamperFault = false;
    }
    if (field === "tamper_inhibited") {
      if (stateObj.state === "on") device.tamperInhibited = true;
      if (stateObj.state === "off") device.tamperInhibited = false;
    }
    if (field === "tamper_isolated") {
      if (stateObj.state === "on") device.tamperIsolated = true;
      if (stateObj.state === "off") device.tamperIsolated = false;
    }

    device.entities.push({ entityId, stateObj, field });
  }

  for (const device of devices.values()) {
    device.model ||= this._xBusModelFromDiagnostics(device);
  }

  return Array.from(devices.values()).sort((a, b) => {
    const idOrder =
      Number(a.id ?? Number.MAX_SAFE_INTEGER) -
      Number(b.id ?? Number.MAX_SAFE_INTEGER);
    if (idOrder) return idOrder;
    return String(a.serialNumber || a.key).localeCompare(
      String(b.serialNumber || b.key)
    );
  });
};

SpcFlexCCard.prototype._xBusEntityValue = function (entity) {
  const { field, stateObj } = entity;
  if (field === "tamper_fault") {
    if (stateObj.state === "on") return { value:this._t("state.fault"), className:"danger" };
    if (stateObj.state === "off") return { value:this._t("state.ok"), className:"ok" };
  }
  if (field === "tamper_inhibited") {
    if (stateObj.state === "on") return { value:this._t("state.inhibited"), className:"zone-inhibited" };
    if (stateObj.state === "off") return { value:this._t("state.not_inhibited"), className:"ok" };
  }
  if (field === "tamper_isolated") {
    if (stateObj.state === "on") return { value:this._t("state.isolated"), className:"warning" };
    if (stateObj.state === "off") return { value:this._t("state.not_isolated"), className:"ok" };
  }
  return { value:this._valueWithUnit(stateObj), className:"" };
};

SpcFlexCCard.prototype._xBusEntityLabel = function (device, entity) {
  const friendlyName = String(entity.stateObj?.attributes?.friendly_name || entity.entityId).trim();
  if (!device.name) return friendlyName;
  const prefix = `${device.name} `;
  return friendlyName.startsWith(prefix) ? friendlyName.slice(prefix.length) : friendlyName;
};

SpcFlexCCard.prototype._renderXBusDevices = function () {
  const devices = this._getXBusDevices();
  if (!devices.length) return "";
  const fieldOrder = ["tamper_fault","tamper_inhibited","tamper_isolated","aux_voltage","aux_current","device_type","hardware_id","input_count","output_count","rf_type","rf_version","reader_type","position_1","position_2","psu_type","sia_address","status_raw","input_raw","alert_raw","inhibit_raw","isolate_raw"];
  const order = new Map(fieldOrder.map((field, index) => [field, index]));

  return `<div class="technical-section xbus-section"><div class="technical-section-title">${this._t("system.xbus")}</div><div class="xbus-list">${devices.map((device) => {
    const title = device.name || `X-BUS ${device.id}`;
    const model = this._xBusModelLabel(device.model);
    const fault = device.tamperFault === true;
    const inhibited = device.tamperInhibited === true;
    const isolated = device.tamperIsolated === true;
    const headerStates = [
      device.tamperFault === true ? `<span class="danger">${this._t("state.fault")}</span>` : "",
      device.tamperInhibited === true ? `<span class="zone-inhibited">${this._t("state.inhibited")}</span>` : "",
      device.tamperIsolated === true ? `<span class="danger">${this._t("state.isolated")}</span>` : "",
    ].filter(Boolean).join(" ");
    const rows = device.entities.filter((entity) => entity.field && entity.field !== "diagnostics").sort((a,b) => {
      const aOrder=order.get(a.field) ?? Number.MAX_SAFE_INTEGER;
      const bOrder=order.get(b.field) ?? Number.MAX_SAFE_INTEGER;
      return aOrder-bOrder || a.field.localeCompare(b.field);
    }).map((entity) => {
      const state=this._xBusEntityValue(entity);
      if (state.value === null || state.value === undefined) return "";
      return this._technicalLine(this._xBusEntityLabel(device,entity),state.value,state.className);
    }).join("");

    return `<details class="xbus-card" data-xbus-key="${this._escapeHtml(String(device.key))}"><summary class="xbus-title"><span class="xbus-title-main"><span class="xbus-title-text"><span class="xbus-title-name">${this._escapeHtml(title)}</span>${model ? `<span class="xbus-title-model">${this._escapeHtml(model)}</span>` : ""}</span></span>${headerStates || (device.tamperFault === false && device.tamperInhibited !== true && device.tamperIsolated !== true ? `<span class="ok">${this._t("state.ok")}</span>` : "")}</summary><div class="xbus-card-body">${this._technicalLine(this._t("system.xbus_id"),device.id)}${this._technicalLine(this._t("system.serial"),device.serialNumber)}${this._technicalLine(this._t("system.firmware"),device.version)}${rows}</div></details>`;
  }).join("")}</div></div>`;
};

SpcFlexCCard.prototype._renderTechnicalSystem = function () {
  const html = spcFlexCXBusBaseTechnicalSystem.call(this);
  const deviceNames = this._getXBusDevices().map((device) => String(device.name || "").trim()).filter(Boolean);
  if (!html || !deviceNames.length || typeof DOMParser === "undefined") return html;
  const documentNode = new DOMParser().parseFromString(`<body>${html}</body>`,"text/html");
  for (const section of documentNode.querySelectorAll(".technical-section")) {
    const title=section.querySelector(".technical-section-title")?.textContent?.trim();
    if (title !== this._t("system.rf")) continue;
    for (const row of section.querySelectorAll(".technical-row")) {
      const label=row.querySelector(".technical-label")?.textContent?.trim() || "";
      const belongsToXBus=deviceNames.some((deviceName) => label === deviceName || label.startsWith(`${deviceName} `));
      if (belongsToXBus) row.remove();
    }
    if (!section.querySelector(".technical-row")) section.remove();
  }
  return documentNode.body.innerHTML;
};

SpcFlexCCard.prototype._render = function () {
  const openXBusDevices = new Set(Array.from(this.querySelectorAll("details.xbus-card[open][data-xbus-key]")).map((details) => details.dataset.xbusKey).filter(Boolean));
  spcFlexCXBusBaseRender.call(this);
  if (!openXBusDevices.size) return;
  for (const details of this.querySelectorAll("details.xbus-card[data-xbus-key]")) {
    if (openXBusDevices.has(details.dataset.xbusKey)) details.open = true;
  }
};
