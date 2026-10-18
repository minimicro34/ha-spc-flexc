/* SPC FlexC Card zone isolation extension. */

const spcFlexCZoneIsolationBaseGetZones = SpcFlexCCard.prototype._getZones;
const spcFlexCZoneIsolationBaseRenderZoneRow = SpcFlexCCard.prototype._renderZoneRow;
const spcFlexCZoneIsolationBaseStyles = SpcFlexCCard.prototype._styles;
const spcFlexCZoneIsolationBaseRender = SpcFlexCCard.prototype._render;

SpcFlexCCard.prototype._getZones = function () {
  const zones = spcFlexCZoneIsolationBaseGetZones.call(this);
  if (!this._hass || !zones.length) return zones;

  const byId = new Map(zones.map((zone) => [String(zone.zoneId), zone]));
  const scoped = this._scopedStates(true);
  // Never scan all Home Assistant entities if the selected SPC scope is unavailable.
  const candidates = scoped;

  // spc-flexc-outputs predates the isolation switch and historically accepted
  // every switch carrying zone_id as an inhibition switch. Once isolation was
  // added, that allowed the two switch states to overwrite each other depending
  // on registry iteration order. Rebuild both operating states from their exact
  // integration unique IDs so inhibition and isolation remain independent.
  for (const zone of zones) {
    zone.inhibited = false;
    zone.inhibitionEntityId = null;
    zone.isolated = false;
    zone.isolationEntityId = null;
  }

  for (const { entityId, stateObj, registryEntry } of candidates) {
    if (!entityId.startsWith("switch.")) continue;

    const attrs = stateObj?.attributes || {};
    const uniqueId = String(registryEntry?.unique_id || "");
    const inhibitionMatch = uniqueId.match(/_zone_(\d+)_inhibition$/);
    const isolationMatch = uniqueId.match(/_zone_(\d+)_isolation$/);

    if (!inhibitionMatch && !isolationMatch) continue;

    const zoneId = attrs.zone_id ?? inhibitionMatch?.[1] ?? isolationMatch?.[1];
    const zone = byId.get(String(zoneId));
    if (!zone) continue;

    if (inhibitionMatch) {
      zone.inhibited = stateObj.state === "on";
      zone.inhibitionEntityId = entityId;
    }

    if (isolationMatch) {
      zone.isolated = stateObj.state === "on";
      zone.isolationEntityId = entityId;
    }
  }

  return zones;
};

SpcFlexCCard.prototype._zoneIsIsolated = function (zone) {
  return zone?.isolated === true;
};

SpcFlexCCard.prototype._renderZoneRow = function (zone) {
  if (!this._zoneIsIsolated(zone)) {
    return spcFlexCZoneIsolationBaseRenderZoneRow.call(this, zone);
  }

  return `
    <div class="zone-row zone-row-isolated">
      <div class="zone-icon danger">
        <ha-icon icon="${this._escapeHtml(this._zoneIcon(zone))}"></ha-icon>
      </div>

      <div class="zone-main">
        <div class="zone-name">${this._escapeHtml(zone.name)}</div>
        <div class="zone-area">
          ${this._escapeHtml(this._areaName(zone.areaId))}
          <span class="zone-operating-badge zone-isolated">${this._t("state.isolated")}</span>
        </div>
      </div>

      <div class="zone-state danger">
        ${this._escapeHtml(this._t("state.isolated"))}
      </div>
    </div>
  `;
};

SpcFlexCCard.prototype._zoneOperatingCounts = function (zones) {
  const normalZones = zones.filter(
    (zone) => zone.zoneType !== "tamper" && zone.deviceClass !== "tamper"
  );
  const isolated = normalZones.filter((zone) => this._zoneIsIsolated(zone)).length;
  const inhibited = normalZones.filter(
    (zone) => zone.inhibited === true && !this._zoneIsIsolated(zone)
  ).length;
  const active = normalZones.filter(
    (zone) => zone.state === "on" && !this._zoneIsIsolated(zone)
  ).length;

  return { normalZones, isolated, inhibited, active };
};

SpcFlexCCard.prototype._renderZoneOperatingBadges = function (counts) {
  return [
    counts.isolated
      ? `<span class="danger">${counts.isolated} ${this._t("state.isolated")}</span>`
      : "",
    counts.inhibited
      ? `<span class="zone-inhibited">${this._tCount("group.inhibited_count", counts.inhibited)}</span>`
      : "",
  ].join("");
};

SpcFlexCCard.prototype._updateZoneOperatingSummaries = function () {
  const zones = this._getZones();
  if (!zones.length) return;

  const globalCounts = this._zoneOperatingCounts(zones);
  const globalBadges = this._renderZoneOperatingBadges(globalCounts);

  // General view: keep detector activity visible for inhibited zones, suppress
  // isolated-zone activity, and surface both operating states explicitly.
  const systemSummary = this.querySelector(".system-view .system-summary");
  if (systemSummary && globalBadges) {
    systemSummary.insertAdjacentHTML(
      "beforeend",
      `<span class="zone-operating-summary"> · ${globalBadges}</span>`
    );
  }

  const detectorCard = this.querySelectorAll(".system-view .summary-card")[1];
  const detectorLabel = detectorCard?.querySelector(".summary-label");
  if (detectorLabel) {
    detectorLabel.innerHTML = `
      ${this._t("tab.detectors")}
      ${globalCounts.active ? `<span class="warning"> · ${this._tCount("group.active_count", globalCounts.active)}</span>` : ""}
      ${globalCounts.inhibited ? `<span class="zone-inhibited"> · ${this._tCount("group.inhibited_count", globalCounts.inhibited)}</span>` : ""}
      ${globalCounts.isolated ? `<span class="danger"> · ${globalCounts.isolated} ${this._t("state.isolated")}</span>` : ""}
    `;
  }

  // Areas view: operating states are informational only. They never hide or
  // disable the area's alarm controls; the SPC panel remains authoritative.
  this.querySelectorAll(".area-card").forEach((card) => {
    const areaId = card.querySelector("[data-area-id]")?.dataset.areaId;
    if (areaId == null) return;

    const areaZones = zones.filter(
      (zone) => String(zone.areaId) === String(areaId)
    );
    const counts = this._zoneOperatingCounts(areaZones);
    const badges = this._renderZoneOperatingBadges(counts);

    const headerState = card.querySelector(".area-card-toggle-state");
    if (headerState && badges) {
      headerState.insertAdjacentHTML(
        "afterbegin",
        `<span class="area-zone-operating-summary">${badges}</span>`
      );
    }

    const meta = card.querySelector(".area-meta");
    if (meta) {
      const tampers = areaZones.filter(
        (zone) => zone.zoneType === "tamper" || zone.deviceClass === "tamper"
      );
      const activeTampers = tampers.filter(
        (zone) =>
          !this._zoneIsIsolated(zone) &&
          (zone.state === "on" || zone.eventTamper === true)
      ).length;

      meta.innerHTML = `
        <span>${this._tCount("group.detector_count", counts.normalZones.length)}</span>
        ${counts.active ? `<span class="warning">${this._tCount("group.active_count", counts.active)}</span>` : ""}
        ${counts.inhibited ? `<span class="zone-inhibited">${this._tCount("group.inhibited_count", counts.inhibited)}</span>` : ""}
        ${counts.isolated ? `<span class="danger">${counts.isolated} ${this._t("state.isolated")}</span>` : ""}
        ${!counts.active && !counts.inhibited && !counts.isolated ? `<span class="ok">${this._t("group.rest")}</span>` : ""}
        ${activeTampers ? `<span class="danger">${this._t("area.tamper")}</span>` : ""}
      `;
    }
  });
};

SpcFlexCCard.prototype._styles = function () {
  return `${spcFlexCZoneIsolationBaseStyles.call(this)}
    <style>
      .zone-row-isolated {
        box-shadow:inset 3px 0 0 var(--error-color,#db4437);
        background:color-mix(in srgb,var(--error-color,#db4437) 9%,transparent);
      }
      .zone-row-isolated .zone-name,
      .zone-row-isolated .zone-area,
      .zone-isolated {
        color:var(--error-color,#db4437);
      }
      .zone-operating-summary,
      .area-zone-operating-summary {
        display:inline-flex;
        align-items:center;
        gap:6px;
      }
      .area-zone-operating-summary {
        flex-wrap:wrap;
        justify-content:flex-end;
        font-size:12px;
        font-weight:700;
      }
    </style>`;
};

SpcFlexCCard.prototype._render = function () {
  spcFlexCZoneIsolationBaseRender.call(this);
  this._updateZoneOperatingSummaries();
};
