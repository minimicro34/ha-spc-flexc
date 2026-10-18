/* SPC FlexC Card v1.0.5 extensions: Mapping Gates, door supervision and zone inhibition. */

const spcFlexCBaseLoadActiveTab = SpcFlexCCard.prototype._loadActiveTab;
const spcFlexCBaseGetZones = SpcFlexCCard.prototype._getZones;
const spcFlexCBaseGetDoors = SpcFlexCCard.prototype._getDoors;
const spcFlexCBaseStyles = SpcFlexCCard.prototype._styles;
const spcFlexCBaseRender = SpcFlexCCard.prototype._render;

SpcFlexCCard.prototype._loadActiveTab = function (entityId) {
  const value = spcFlexCBaseLoadActiveTab.call(this, entityId);
  if (value) return value;

  const key = this._activeTabStorageKey(entityId);
  if (!key) return null;

  try {
    return window.localStorage.getItem(key) === "outputs" ? "outputs" : null;
  } catch {
    return null;
  }
};

SpcFlexCCard.prototype._getMappingGates = function () {
  if (!this._hass) return [];

  const scoped = this._scopedStates(true);
  // Never scan all Home Assistant entities if the selected SPC scope is unavailable.
  const candidates = scoped;

  return candidates
    .filter(({ entityId, stateObj, registryEntry }) => {
      if (!entityId.startsWith("switch.")) return false;
      const attrs = stateObj?.attributes || {};
      const uniqueId = String(registryEntry?.unique_id || "");
      return attrs.mg_id != null || /_mapping_gate_\d+$/.test(uniqueId);
    })
    .map(({ entityId, stateObj, registryEntry }) => {
      const attrs = stateObj?.attributes || {};
      const uniqueId = String(registryEntry?.unique_id || "");
      const match = uniqueId.match(/_mapping_gate_(\d+)$/);
      const mgId = attrs.mg_id ?? match?.[1] ?? null;
      return {
        entityId,
        id: mgId,
        name:
          attrs.mg_name ||
          attrs.friendly_name ||
          (mgId != null ? this._t("output.name", { id: mgId }) : entityId),
        state: stateObj.state,
      };
    })
    .sort((a, b) => Number(a.id) - Number(b.id));
};

SpcFlexCCard.prototype._getZones = function () {
  const zones = spcFlexCBaseGetZones.call(this);
  if (!this._hass || !zones.length) return zones;

  const byId = new Map(zones.map((zone) => [String(zone.zoneId), zone]));
  const scoped = this._scopedStates(true);
  // Never scan all Home Assistant entities if the selected SPC scope is unavailable.
  const candidates = scoped;

  for (const { entityId, stateObj, registryEntry } of candidates) {
    const attrs = stateObj?.attributes || {};
    const uniqueId = String(registryEntry?.unique_id || "");

    if (entityId.startsWith("switch.")) {
      const match = uniqueId.match(/_zone_(\d+)_inhibition$/);
      const zoneId = attrs.zone_id ?? match?.[1] ?? null;

      if (zoneId == null || (!match && attrs.zone_id == null)) continue;

      const zone = byId.get(String(zoneId));
      if (!zone) continue;

      zone.inhibited = stateObj.state === "on";
      zone.inhibitionEntityId = entityId;
      continue;
    }

    if (entityId.startsWith("button.")) {
      const match = uniqueId.match(/_zone_(\d+)_restore$/);
      if (!match && attrs.restore_allowed == null) continue;
      const zoneId = attrs.zone_id ?? match?.[1] ?? null;
      if (zoneId == null) continue;

      const zone = byId.get(String(zoneId));
      if (!zone) continue;

      zone.restoreEntityId = entityId;
      zone.restoreAllowed =
        attrs.restore_allowed === true ||
        attrs.restore_allowed === 1 ||
        attrs.restore_allowed === "1";
      zone.restoreAvailable =
        zone.restoreAllowed && stateObj.state !== "unavailable";
    }
  }

  return zones;
};

SpcFlexCCard.prototype._renderZoneRow = function (zone) {
  const stateInfo = this._zoneStateInfo(zone);
  const inhibited = zone.inhibited === true;
  const visualClass = stateInfo.className;

  return `
    <div class="zone-row${inhibited ? " zone-row-inhibited" : ""}">
      <div class="zone-icon ${visualClass}">
        <ha-icon icon="${this._escapeHtml(this._zoneIcon(zone))}"></ha-icon>
      </div>

      <div class="zone-main">
        <div class="zone-name">${this._escapeHtml(zone.name)}</div>
        <div class="zone-area">
          ${this._escapeHtml(this._areaName(zone.areaId))}
          ${inhibited ? `<span class="zone-operating-badge zone-inhibited">${this._t("zone.inhibited")}</span>` : ""}
        </div>
      </div>

      <div class="zone-state ${visualClass}">
        ${this._escapeHtml(stateInfo.label)}
      </div>

      ${this._config.show_controls === false || !zone.restoreAvailable ? "" : `
        <button type="button" class="zone-restore-button"
          data-zone-restore-entity="${this._escapeHtml(zone.restoreEntityId)}"
          data-zone-restore-name="${this._escapeHtml(zone.name)}">
          ${this._t("action.restore")}
        </button>
      `}
    </div>
  `;
};

SpcFlexCCard.prototype._getDoors = function () {
  const doors = spcFlexCBaseGetDoors.call(this);
  const byId = new Map(doors.map((door) => [String(door.id), door]));

  for (const { stateObj } of this._scopedStates(true)) {
    const attrs = stateObj?.attributes || {};
    if (attrs.door_id == null) continue;
    const door = byId.get(String(attrs.door_id));
    if (!door) continue;
    door.dpsInput = attrs.dps_input ?? door.dpsInput ?? null;
    door.drsInput = attrs.drs_input ?? door.drsInput ?? null;
  }

  return doors;
};

SpcFlexCCard.prototype._doorModeLabel = function (mode) {
  const value = Number(mode);
  if (value === 0) return this._t("state.normal");
  if (value === 1) return this._t("door.access_forbidden");
  if (value === 2) return this._t("door.free_access");
  return mode == null ? "—" : String(mode);
};

SpcFlexCCard.prototype._renderDoors = function () {
  const doors = this._getDoors();
  if (!doors.length) {
    return `
      <div class="empty-state">
        <ha-icon icon="mdi:door-closed-lock"></ha-icon>
        <div>${this._t("door.none")}</div>
      </div>
    `;
  }

  return `
    <div class="door-list">
      ${doors.map((door) => `
        <div class="door-card">
          <div class="door-header">
            <div>
              <div class="door-title">${this._escapeHtml(door.name)}</div>
              <div class="door-areas">${this._escapeHtml(this._doorAreasLabel(door))}</div>
            </div>
            <ha-icon class="door-icon" icon="mdi:door"></ha-icon>
          </div>
          <div class="door-state-grid door-supervision-grid">
            <div class="door-state-card">
              <div class="door-state-label">${this._t("door.status")}</div>
              <div class="door-state-value">${this._escapeHtml(door.status ?? "—")}</div>
            </div>
            <div class="door-state-card">
              <div class="door-state-label">${this._t("door.mode")}</div>
              <div class="door-state-value">${this._escapeHtml(this._doorModeLabel(door.mode))}</div>
            </div>
            <div class="door-state-card">
              <div class="door-state-label">${this._t("door.dps")}</div>
              <div class="door-state-value">${this._escapeHtml(door.dpsInput ?? "—")}</div>
            </div>
            <div class="door-state-card">
              <div class="door-state-label">${this._t("door.drs")}</div>
              <div class="door-state-value">${this._escapeHtml(door.drsInput ?? "—")}</div>
            </div>
          </div>
          ${door.zoneName ? `
            <div class="door-zone">
              <ha-icon icon="mdi:shield-home-outline"></ha-icon>
              <span>${this._t("zone.name", { id: door.zoneId ?? "" })}${door.zoneId != null ? " · " : ""}${this._escapeHtml(door.zoneName)}</span>
            </div>
          ` : ""}
          <div class="door-raw-note">
            ${this._t("door.supervision_note")}
          </div>
        </div>
      `).join("")}
    </div>
  `;
};

SpcFlexCCard.prototype._renderOutputs = function () {
  const outputs = this._getMappingGates();
  if (!outputs.length) {
    return `
      <div class="empty-state">
        <ha-icon icon="mdi:electric-switch"></ha-icon>
        <div>${this._t("output.none")}</div>
      </div>
    `;
  }

  return `
    <div class="outputs-view">
      <div class="group-title">${this._t("tab.outputs")} <span>${outputs.length}</span></div>
      <div class="output-list">
        ${outputs.map((output) => {
          const isOn = output.state === "on";
          const unavailable = ["unknown", "unavailable"].includes(output.state);
          const stateLabel = output.state === "unavailable"
            ? this._t("state.unavailable")
            : output.state === "unknown"
              ? this._t("state.unknown_short")
              : isOn
                ? this._t("state.on")
                : this._t("state.off");
          return `
            <div class="output-row">
              <div class="output-icon ${unavailable ? "muted" : isOn ? "ok" : "muted"}">
                <ha-icon icon="mdi:electric-switch"></ha-icon>
              </div>
              <div class="output-main">
                <div class="output-name">${this._escapeHtml(output.name)}</div>
                <div class="output-id">${this._t("output.mapping_gate")} ${this._escapeHtml(output.id ?? "—")}</div>
              </div>
              <div class="output-state ${unavailable ? "muted" : isOn ? "ok" : "muted"}">
                ${this._escapeHtml(stateLabel)}
              </div>
              ${this._config.show_controls === false ? "" : `
                <div class="output-controls">
                  <button type="button" class="output-button${isOn ? " active" : ""}"
                    data-mg-entity="${this._escapeHtml(output.entityId)}"
                    data-mg-name="${this._escapeHtml(output.name)}" data-mg-action="on">${this._t("state.on")}</button>
                  <button type="button" class="output-button${!isOn && !unavailable ? " active" : ""}"
                    data-mg-entity="${this._escapeHtml(output.entityId)}"
                    data-mg-name="${this._escapeHtml(output.name)}" data-mg-action="off">${this._t("state.off")}</button>
                </div>
              `}
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
};

SpcFlexCCard.prototype._renderTabs = function () {
  const hasDoors = this._getDoors().length > 0;
  const hasOutputs = this._getMappingGates().length > 0;
  if (this._activeTab === "doors" && !hasDoors) this._activeTab = "system";
  if (this._activeTab === "outputs" && !hasOutputs) this._activeTab = "system";

  const tabs = [
    ["system", this._t("tab.general")],
    ["areas", this._t("tab.areas")],
    ["zones", this._t("tab.detectors")],
    ...(hasDoors ? [["doors", this._t("tab.doors")]] : []),
    ...(hasOutputs ? [["outputs", this._t("tab.outputs")]] : []),
    ["technical", this._t("tab.system")],
  ];

  return `<div class="tabs">${tabs.map(([id, label]) => `
    <button type="button" class="tab ${this._activeTab === id ? "active" : ""}" data-tab="${id}">
      ${this._escapeHtml(label)}
    </button>
  `).join("")}</div>`;
};

SpcFlexCCard.prototype._renderActiveView = function () {
  switch (this._activeTab) {
    case "areas": return this._renderAreas();
    case "zones": return this._renderZones();
    case "doors": return this._getDoors().length ? this._renderDoors() : this._renderSystem();
    case "outputs": return this._getMappingGates().length ? this._renderOutputs() : this._renderSystem();
    case "technical": return this._renderTechnicalSystem();
    case "system":
    default: return this._renderSystem();
  }
};

SpcFlexCCard.prototype._callZoneRestore = async function (entityId, name) {
  if (!this._hass || !entityId) return;
  if (!this._panelEntityIds()?.has(entityId)) {
    console.warn("SPC FlexC Card: blocked cross-panel action", entityId);
    return;
  }
  const prompt = this._t("confirm.restore_zone", { name });
  if (this._config.confirm_actions && !window.confirm(prompt)) return;
  await this._hass.callService("button", "press", { entity_id: entityId });
};

SpcFlexCCard.prototype._callMappingGate = async function (entityId, name, action) {
  if (!this._hass || !entityId || !["on", "off"].includes(action)) return;
  if (!this._panelEntityIds()?.has(entityId)) {
    console.warn("SPC FlexC Card: blocked cross-panel action", entityId);
    return;
  }
  const actionLabel = action === "on" ? this._t("action.activate") : this._t("action.deactivate");
  const prompt = this._t("confirm.mapping_gate", { action: actionLabel, name });
  if (this._config.confirm_actions && !window.confirm(prompt)) return;
  await this._hass.callService("switch", action === "on" ? "turn_on" : "turn_off", {
    entity_id: entityId,
  });
};

SpcFlexCCard.prototype._styles = function () {
  return `${spcFlexCBaseStyles.call(this)}
    <style>
      .zone-operating-badge {
        display:inline-flex;
        align-items:center;
        margin-left:7px;
        padding:1px 6px;
        border:1px solid currentColor;
        border-radius:999px;
        font-size:9px;
        font-weight:800;
        letter-spacing:.04em;
        line-height:1.5;
        vertical-align:1px;
      }
      .zone-row-inhibited {
        box-shadow:inset 3px 0 0 color-mix(in srgb,currentColor 55%,transparent);
      }
      .zone-restore-button {
        appearance:none;
        padding:7px 10px;
        border:1px solid var(--warning-color,#ff9800);
        border-radius:8px;
        background:var(--card-background-color);
        color:var(--warning-color,#ff9800);
        cursor:pointer;
        font:inherit;
        font-size:12px;
        font-weight:700;
      }
      .outputs-view { display:grid; gap:12px; }
      .output-list { display:grid; gap:7px; }
      .output-row {
        display:grid;
        grid-template-columns:46px minmax(0,1fr) auto auto;
        align-items:center;
        gap:12px;
        min-height:58px;
        padding:8px 12px;
        border-radius:10px;
        background:var(--secondary-background-color,rgba(127,127,127,.08));
      }
      .output-icon { display:flex; align-items:center; justify-content:center; }
      .output-icon ha-icon { --mdc-icon-size:28px; }
      .output-main { min-width:0; }
      .output-name { overflow:hidden; font-weight:600; text-overflow:ellipsis; white-space:nowrap; }
      .output-id { margin-top:2px; color:var(--secondary-text-color); font-size:11px; }
      .output-state { min-width:34px; font-weight:700; text-align:right; }
      .output-controls { display:flex; gap:6px; }
      .output-button {
        appearance:none;
        min-width:48px;
        padding:7px 10px;
        border:1px solid var(--divider-color);
        border-radius:8px;
        background:var(--card-background-color);
        color:var(--primary-text-color);
        cursor:pointer;
        font:inherit;
        font-size:12px;
        font-weight:700;
      }
      .output-button.active { border-color:var(--primary-color); color:var(--primary-color); }
      .door-supervision-grid { grid-template-columns:repeat(4,minmax(0,1fr)); }
      @media (max-width:700px) {
        .output-row { grid-template-columns:40px minmax(0,1fr) auto; }
        .output-controls { grid-column:2 / -1; }
        .door-supervision-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
      }
    </style>`;
};

SpcFlexCCard.prototype._render = function () {
  spcFlexCBaseRender.call(this);
  this.querySelectorAll("[data-zone-restore-entity]").forEach((button) => {
    button.addEventListener("click", () => {
      this._callZoneRestore(
        button.dataset.zoneRestoreEntity,
        button.dataset.zoneRestoreName || this._t("zone.name", { id: "" })
      );
    });
  });
  this.querySelectorAll("[data-mg-entity]").forEach((button) => {
    button.addEventListener("click", () => {
      this._callMappingGate(
        button.dataset.mgEntity,
        button.dataset.mgName || this._t("output.fallback_name"),
        button.dataset.mgAction
      );
    });
  });
};
