/* SPC FlexC Card v1.0.5 zone grouping extension. */

const spcFlexCZoneGroupsBaseStyles = SpcFlexCCard.prototype._styles;
const spcFlexCZoneGroupsBaseRender = SpcFlexCCard.prototype._render;

SpcFlexCCard.prototype._zoneGroupsStorageKey = function () {
  const entity = this._config?.entity;
  return entity ? `spc-flexc-card:${entity}:zone-groups` : null;
};

SpcFlexCCard.prototype._loadZoneGroupStates = function () {
  if (this._spcZoneGroupStates) return this._spcZoneGroupStates;

  this._spcZoneGroupStates = {};
  const key = this._zoneGroupsStorageKey();
  if (!key) return this._spcZoneGroupStates;

  try {
    const raw = window.localStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        this._spcZoneGroupStates = parsed;
      }
    }
  } catch {
    // Keep in-memory state when persistent browser storage is unavailable.
  }

  return this._spcZoneGroupStates;
};

SpcFlexCCard.prototype._saveZoneGroupStates = function () {
  const key = this._zoneGroupsStorageKey();
  if (!key) return;

  try {
    window.localStorage.setItem(
      key,
      JSON.stringify(this._spcZoneGroupStates || {})
    );
  } catch {
    // Home Assistant can still keep the state until the card is recreated.
  }
};

SpcFlexCCard.prototype._zoneGroupExpanded = function (areaId) {
  const states = this._loadZoneGroupStates();
  const key = String(areaId);

  if (Object.prototype.hasOwnProperty.call(states, key)) {
    return states[key] === true;
  }

  // Start every group collapsed until the user explicitly opens it.
  return false;
};

SpcFlexCCard.prototype._setZoneGroupExpanded = function (areaId, expanded) {
  const states = this._loadZoneGroupStates();
  states[String(areaId)] = Boolean(expanded);
  this._saveZoneGroupStates();
};

SpcFlexCCard.prototype._zoneIsInhibited = function (zone) {
  return zone?.inhibited === true;
};

SpcFlexCCard.prototype._getZoneGroups = function () {
  const zones = this._getZones();
  const areas = this._getAreas();
  const groups = new Map();

  for (const area of areas) {
    groups.set(String(area.id), {
      id: String(area.id),
      name: area.name,
      numericId: area.numericId,
      zones: [],
    });
  }

  for (const zone of zones) {
    const key = String(zone.areaId);
    if (!groups.has(key)) {
      groups.set(key, {
        id: key,
        name: this._areaName(zone.areaId),
        numericId: Number(zone.areaId),
        zones: [],
      });
    }
    groups.get(key).zones.push(zone);
  }

  return Array.from(groups.values())
    .filter((group) => group.zones.length > 0)
    .sort((a, b) => {
      if (Number.isFinite(a.numericId) && Number.isFinite(b.numericId)) {
        return a.numericId - b.numericId;
      }
      return a.name.localeCompare(b.name);
    });
};

SpcFlexCCard.prototype._renderZones = function () {
  const groups = this._getZoneGroups();
  const totalZones = groups.reduce((count, group) => count + group.zones.length, 0);

  if (!totalZones) {
    return `
      <div class="empty-state">
        <ha-icon icon="mdi:motion-sensor-off"></ha-icon>
        <div>${this._t("zone.none")}</div>
      </div>
    `;
  }

  const allExpanded = groups.every((group) =>
    this._zoneGroupExpanded(group.id)
  );

  return `
    <div class="zones-view grouped-zones-view">
      <div class="zone-groups-toolbar">
        <div class="group-title">
          ${this._t("group.detectors")}
          <span>${totalZones}</span>
        </div>
        <button
          type="button"
          class="zone-groups-toggle-all"
          data-zone-groups-action="${allExpanded ? "collapse" : "expand"}"
        >
          ${this._t(allExpanded ? "group.collapse_all" : "group.expand_all")}
        </button>
      </div>

      <div class="zone-groups-list">
        ${groups.map((group) => {
          const expanded = this._zoneGroupExpanded(group.id);
          const normalZones = group.zones.filter(
            (zone) => zone.zoneType !== "tamper" && zone.deviceClass !== "tamper"
          );
          const tampers = group.zones.filter(
            (zone) => zone.zoneType === "tamper" || zone.deviceClass === "tamper"
          );
          const isolatedZones = group.zones.filter((zone) =>
            this._zoneIsIsolated?.(zone) === true
          ).length;
          const inhibitedZones = group.zones.filter((zone) =>
            this._zoneIsInhibited(zone) && this._zoneIsIsolated?.(zone) !== true
          ).length;
          // Inhibition does not suppress the detector's physical activity in
          // the UI. Isolation does: an isolated zone is outside normal
          // supervision and its activity is intentionally not summarized.
          const activeZones = normalZones.filter(
            (zone) =>
              zone.state === "on" &&
              this._zoneIsIsolated?.(zone) !== true
          ).length;
          const activeTampers = tampers.filter(
            (zone) =>
              this._zoneIsIsolated?.(zone) !== true &&
              (zone.state === "on" || zone.eventTamper === true)
          ).length;
          const unavailable = group.zones.filter(
            (zone) => ["unknown", "unavailable"].includes(zone.state)
          ).length;

          return `
            <section class="zone-group${expanded ? " expanded" : " collapsed"}">
              <button
                type="button"
                class="zone-group-header"
                data-zone-group-id="${this._escapeHtml(group.id)}"
                aria-expanded="${expanded ? "true" : "false"}"
              >
                <ha-icon
                  class="zone-group-chevron"
                  icon="${expanded ? "mdi:chevron-down" : "mdi:chevron-right"}"
                ></ha-icon>

                <div class="zone-group-title-wrap">
                  <div class="zone-group-title">${this._escapeHtml(group.name)}</div>
                  <div class="zone-group-meta">
                    ${this._tCount("group.detector_count", normalZones.length)}
                    ${tampers.length ? ` · ${this._tCount("group.tamper_count", tampers.length)}` : ""}
                  </div>
                </div>

                <div class="zone-group-summary">
                  ${isolatedZones ? `<span class="danger">${isolatedZones} ${this._t("state.isolated")}</span>` : ""}
                  ${inhibitedZones ? `<span class="zone-inhibited">${this._tCount("group.inhibited_count", inhibitedZones)}</span>` : ""}
                  ${activeZones ? `<span class="warning">${this._tCount("group.active_count", activeZones)}</span>` : ""}
                  ${activeTampers ? `<span class="danger">${this._tCount("group.fault_count", activeTampers)}</span>` : ""}
                  ${unavailable ? `<span class="muted">${this._tCount("group.unavailable_count", unavailable)}</span>` : ""}
                  ${!isolatedZones && !inhibitedZones && !activeZones && !activeTampers && !unavailable ? `<span class="ok">${this._t("group.rest")}</span>` : ""}
                </div>
              </button>

              ${expanded ? `
                <div class="zone-group-content">
                  ${normalZones.length ? `
                    <div class="zone-list">
                      ${normalZones.map((zone) => this._renderZoneRow(zone)).join("")}
                    </div>
                  ` : ""}

                  ${tampers.length ? `
                    <div class="group-title tamper-title">
                      ${this._t("group.tampers")}
                      <span>${tampers.length}</span>
                    </div>
                    <div class="zone-list tamper-list">
                      ${tampers.map((zone) => this._renderZoneRow(zone)).join("")}
                    </div>
                  ` : ""}
                </div>
              ` : ""}
            </section>
          `;
        }).join("")}
      </div>
    </div>
  `;
};

SpcFlexCCard.prototype._styles = function () {
  return `${spcFlexCZoneGroupsBaseStyles.call(this)}
    <style>
      .zone-inhibited { color:var(--spc-flexc-inhibited-color,#f6b73c); }
      .zone-groups-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; }
      .zone-groups-toggle-all, .zone-group-header { appearance:none; border:0; font:inherit; color:inherit; cursor:pointer; }
      .zone-groups-toggle-all { padding:6px 9px; border-radius:8px; background:var(--secondary-background-color,rgba(127,127,127,.08)); color:var(--primary-color); font-size:12px; font-weight:700; }
      .zone-groups-list { display:grid; gap:10px; }
      .zone-group { overflow:hidden; border:1px solid var(--divider-color); border-radius:12px; }
      .zone-group-header { display:grid; grid-template-columns:28px minmax(0,1fr) auto; align-items:center; gap:10px; width:100%; padding:12px; background:var(--secondary-background-color,rgba(127,127,127,.06)); text-align:left; }
      .zone-group-header:hover { background:var(--secondary-background-color,rgba(127,127,127,.1)); }
      .zone-group-chevron { --mdc-icon-size:22px; color:var(--secondary-text-color); }
      .zone-group-title-wrap { min-width:0; }
      .zone-group-title { overflow:hidden; font-size:15px; font-weight:700; text-overflow:ellipsis; white-space:nowrap; }
      .zone-group-meta { margin-top:2px; color:var(--secondary-text-color); font-size:11px; }
      .zone-group-summary { display:flex; justify-content:flex-end; flex-wrap:wrap; gap:4px 9px; font-size:12px; font-weight:700; text-align:right; }
      .zone-group-content { display:grid; gap:8px; padding:9px; }
      .zone-group-content .tamper-title { margin:8px 3px 0; }
      @media (max-width:520px) {
        .zone-group-header { grid-template-columns:24px minmax(0,1fr); }
        .zone-group-summary { grid-column:2; justify-content:flex-start; text-align:left; }
        .zone-groups-toolbar { align-items:flex-start; }
      }
    </style>`;
};

SpcFlexCCard.prototype._render = function () {
  spcFlexCZoneGroupsBaseRender.call(this);

  this.querySelectorAll("[data-zone-group-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const areaId = button.dataset.zoneGroupId;
      const expanded = button.getAttribute("aria-expanded") === "true";
      this._setZoneGroupExpanded(areaId, !expanded);
      this._render();
    });
  });

  this.querySelectorAll("[data-zone-groups-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const expand = button.dataset.zoneGroupsAction === "expand";
      const groups = this._getZoneGroups();
      for (const group of groups) this._setZoneGroupExpanded(group.id, expand);
      this._render();
    });
  });
};
