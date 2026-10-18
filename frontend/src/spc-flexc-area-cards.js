/* SPC FlexC Card responsive area cards and wide-layout helpers. */

const spcFlexCAreaCardsBaseRenderAreas = SpcFlexCCard.prototype._renderAreas;
const spcFlexCAreaCardsBaseStyles = SpcFlexCCard.prototype._styles;
const spcFlexCAreaCardsBaseRender = SpcFlexCCard.prototype._render;

SpcFlexCCard.prototype._areaCardStorageKey = function (
  entityId = this._config?.entity
) {
  if (!entityId) return null;
  return `spc-flexc-card:${entityId}:area-cards`;
};

SpcFlexCCard.prototype._loadAreaCardStates = function () {
  const key = this._areaCardStorageKey();
  if (!key) return {};

  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
};

SpcFlexCCard.prototype._saveAreaCardStates = function (states) {
  const key = this._areaCardStorageKey();
  if (!key) return;

  try {
    window.localStorage.setItem(key, JSON.stringify(states));
  } catch {
    // Keep the current in-memory rendering usable when storage is unavailable.
  }
};

SpcFlexCCard.prototype._areaCardExpanded = function (areaId) {
  const states = this._loadAreaCardStates();
  return states[String(areaId)] === true;
};

SpcFlexCCard.prototype._setAreaCardExpanded = function (areaId, expanded) {
  const states = this._loadAreaCardStates();
  states[String(areaId)] = expanded === true;
  this._saveAreaCardStates(states);
};

SpcFlexCCard.prototype._setAllAreaCardsExpanded = function (expanded) {
  const states = this._loadAreaCardStates();
  for (const area of this._getAreas()) {
    states[String(area.id)] = expanded === true;
  }
  this._saveAreaCardStates(states);
};

SpcFlexCCard.prototype._renderAreas = function () {
  const areas = this._getAreas();
  const zones = this._getZones();

  if (!areas.length) {
    return spcFlexCAreaCardsBaseRenderAreas.call(this);
  }

  return `
    <div class="areas-view">
      <div class="area-toolbar">
        <button type="button" class="area-toolbar-button" data-area-action="expand-all">
          <ha-icon icon="mdi:unfold-more-horizontal"></ha-icon>
          <span>${this._t("group.expand_all")}</span>
        </button>
        <button type="button" class="area-toolbar-button" data-area-action="collapse-all">
          <ha-icon icon="mdi:unfold-less-horizontal"></ha-icon>
          <span>${this._t("group.collapse_all")}</span>
        </button>
      </div>

      <div class="list area-list">
        ${areas
          .map((area) => {
            const areaZones = zones.filter(
              (zone) => String(zone.areaId) === String(area.id)
            );

            const normalZones = areaZones.filter(
              (zone) =>
                zone.zoneType !== "tamper" &&
                zone.deviceClass !== "tamper"
            );

            const tampers = areaZones.filter(
              (zone) =>
                zone.zoneType === "tamper" ||
                zone.deviceClass === "tamper"
            );

            const isolatedZones = normalZones.filter(
              (zone) => this._zoneIsIsolated?.(zone) === true
            ).length;

            const inhibitedZones = normalZones.filter(
              (zone) =>
                zone.inhibited === true &&
                this._zoneIsIsolated?.(zone) !== true
            ).length;

            const activeZones = normalZones.filter(
              (zone) =>
                zone.state === "on" &&
                zone.inhibited !== true &&
                this._zoneIsIsolated?.(zone) !== true
            ).length;

            const activeTampers = tampers.filter(
              (zone) =>
                zone.inhibited !== true &&
                this._zoneIsIsolated?.(zone) !== true &&
                (zone.state === "on" || zone.eventTamper === true)
            ).length;

            const areaEntity = this._getAreaAlarmEntity(area.id);
            const mode =
              areaEntity?.stateObj?.attributes?.mode_name ??
              area.modeName ??
              areaEntity?.stateObj?.attributes?.mode ??
              area.mode ??
              "unknown";

            const renderedState = areaEntity?.stateObj?.state || null;
            const stateClass = renderedState
              ? this._stateClass(renderedState)
              : this._modeClass(mode);

            const icon = renderedState
              ? this._stateIcon(renderedState)
              : stateClass === "ok"
                ? "mdi:lock-open-variant"
                : "mdi:lock";

            const label =
              renderedState === "armed_home"
                ? this._partSetLabel(areaEntity, "a")
                : renderedState === "armed_night"
                  ? this._partSetLabel(areaEntity, "b")
                  : renderedState === "disarmed"
                    ? this._t("state.disarmed_masc")
                    : renderedState
                      ? this._stateLabel(renderedState)
                      : this._modeLabel(mode);

            const expanded = this._areaCardExpanded(area.id);

            return `
              <div class="area-card ${expanded ? "expanded" : "collapsed"}">
                <button
                  type="button"
                  class="area-card-toggle"
                  data-area-id="${this._escapeHtml(area.id)}"
                  aria-expanded="${expanded ? "true" : "false"}"
                >
                  <span class="area-card-title">${this._escapeHtml(area.name)}</span>
                  <span class="area-card-toggle-state">
                    <span class="badge ${stateClass}">${this._escapeHtml(label)}</span>
                    <ha-icon class="area-card-chevron" icon="mdi:chevron-down"></ha-icon>
                  </span>
                </button>

                ${
                  expanded
                    ? `
                      <div class="area-card-body">
                        <div class="area-lock">
                          <ha-icon class="${stateClass}" icon="${this._escapeHtml(icon)}"></ha-icon>
                        </div>

                        <div class="area-meta">
                          <span>${this._tCount("group.detector_count", normalZones.length)}</span>
                          ${isolatedZones ? `<span class="danger">${isolatedZones} ${this._t("state.isolated")}</span>` : ""}
                          ${inhibitedZones ? `<span class="zone-inhibited">${this._tCount("group.inhibited_count", inhibitedZones)}</span>` : ""}
                          ${
                            activeZones
                              ? `<span class="warning">${this._tCount("group.active_count", activeZones)}</span>`
                              : !isolatedZones && !inhibitedZones
                                ? `<span class="ok">${this._t("group.rest")}</span>`
                                : ""
                          }
                          ${
                            activeTampers
                              ? `<span class="danger">${this._t("area.tamper")}</span>`
                              : ""
                          }
                        </div>

                        ${this._lastAreaChange(areaEntity?.stateObj)}
                        ${this._renderAreaControls(area, areaEntity)}
                      </div>
                    `
                    : ""
                }
              </div>
            `;
          })
          .join("")}
      </div>
    </div>
  `;
};

SpcFlexCCard.prototype._styles = function () {
  return `${spcFlexCAreaCardsBaseStyles.call(this)}
    <style>
      .areas-view {
        display: grid;
        gap: 14px;
      }

      .area-toolbar {
        display: flex;
        justify-content: flex-end;
        flex-wrap: wrap;
        gap: 8px;
      }

      .area-toolbar-button,
      .area-card-toggle {
        appearance: none;
        border: 0;
        background: transparent;
        color: var(--primary-text-color);
        cursor: pointer;
        font: inherit;
      }

      .area-toolbar-button {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 7px 10px;
        border: 1px solid var(--divider-color);
        border-radius: 9px;
        color: var(--secondary-text-color);
        font-size: 12px;
        font-weight: 600;
      }

      .area-toolbar-button:hover {
        color: var(--primary-text-color);
        background: var(--secondary-background-color, rgba(127, 127, 127, 0.08));
      }

      .area-toolbar-button ha-icon {
        --mdc-icon-size: 18px;
      }

      .area-list {
        grid-template-columns: repeat(3, minmax(0, 1fr));
        align-items: start;
      }

      .area-card {
        padding: 0;
        overflow: hidden;
      }

      .area-card-toggle {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        width: 100%;
        padding: 18px;
        text-align: left;
      }

      .area-card-toggle:hover {
        background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
      }

      .area-card-toggle-state {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }

      .area-card-toggle .badge {
        text-align: right;
      }

      .area-card-chevron {
        --mdc-icon-size: 22px;
        flex: 0 0 auto;
        color: var(--secondary-text-color);
        transition: transform 0.15s ease;
      }

      .area-card.expanded .area-card-chevron {
        transform: rotate(180deg);
      }

      .area-card-body {
        padding: 0 18px 18px;
        border-top: 1px solid color-mix(in srgb, var(--divider-color) 55%, transparent);
      }

      .door-list,
      .output-list,
      .technical-system-view {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }

      .technical-system-view {
        align-items: start;
      }

      .technical-system-view > .technical-section {
        min-width: 0;
      }

      .output-list {
        gap: 14px;
      }

      .output-row {
        grid-template-columns: 40px minmax(0, 1fr) auto;
        align-content: start;
      }

      .output-controls {
        grid-column: 2 / -1;
      }

      @media (max-width: 700px) {
        .area-list,
        .door-list,
        .output-list,
        .technical-system-view {
          grid-template-columns: 1fr;
        }

        .area-toolbar {
          justify-content: stretch;
        }

        .area-toolbar-button {
          flex: 1 1 auto;
          justify-content: center;
        }
      }
    </style>`;
};

SpcFlexCCard.prototype._render = function () {
  spcFlexCAreaCardsBaseRender.call(this);

  this.querySelectorAll("[data-area-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const areaId = button.dataset.areaId;
      const expanded = button.getAttribute("aria-expanded") === "true";
      this._setAreaCardExpanded(areaId, !expanded);
      this._render();
    });
  });

  this.querySelectorAll("[data-area-action]").forEach((button) => {
    button.addEventListener("click", () => {
      this._setAllAreaCardsExpanded(button.dataset.areaAction === "expand-all");
      this._render();
    });
  });
};
