const CARD_VERSION = "1.0.18";

class SpcFlexCCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("spc-flexc-card-editor");
  }

  static getStubConfig(hass) {
    const alarmEntities = Object.entries(hass.states)
      .filter(([id]) => id.startsWith("alarm_control_panel."));

    const systemEntity = alarmEntities.find(([, stateObj]) =>
      stateObj?.attributes?.areas && typeof stateObj.attributes.areas === "object"
    );

    const entity = systemEntity?.[0] || alarmEntities[0]?.[0];
    return entity ? { entity } : {};
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("SPC FlexC Card requires an alarm_control_panel entity.");
    }

    const entityChanged = this._config?.entity !== config.entity;

    this._config = {
      name: "SPC FlexC",
      show_controls: true,
      confirm_actions: true,
      ...config,
    };

    const validTabs = [
      "system",
      "areas",
      "zones",
      "doors",
      "outputs",
      "technical",
    ];

    if (entityChanged || !validTabs.includes(this._activeTab)) {
      this._activeTab = this._loadActiveTab(config.entity) || "system";
    }

    if (entityChanged) {
      // Invalidate any registry request started for the previous panel.
      this._scopeGeneration = (this._scopeGeneration || 0) + 1;
      this._diagnosticScope = null;
      this._diagnosticScopeForEntity = null;
      this._diagnosticScopeLoading = false;
    }

    this._render();
    this._ensureDiagnosticScope();
  }

  set hass(hass) {
    this._hass = hass;
    this._reconcileLiveZoneStates();
    this._render();
    this._ensureDiagnosticScope();
    this._ensureStateSubscription();
  }

  connectedCallback() {
    this._ensureStateSubscription();
  }

  disconnectedCallback() {
    if (this._spcStateUnsubscribe) {
      this._spcStateUnsubscribe();
      this._spcStateUnsubscribe = null;
    }
  }

  _t(key, variables = {}, fallback = key) {
    if (typeof spcFlexCTranslate === "function") {
      return spcFlexCTranslate(this._hass, key, variables, fallback);
    }
    return fallback;
  }

  _tCount(key, count, variables = {}) {
    const suffix = Number(count) === 1 ? "one" : "other";
    return this._t(`${key}.${suffix}`, { count, ...variables }, String(count));
  }

  _reconcileLiveZoneStates() {
    if (!this._spcLiveStates?.size || !this._hass?.states) {
      return;
    }

    for (const [entityId, liveState] of this._spcLiveStates) {
      const currentState = this._hass.states[entityId];

      if (!currentState) {
        continue;
      }

      const currentUpdated = Date.parse(currentState.last_updated || "");
      const liveUpdated = Date.parse(liveState.last_updated || "");

      if (
        currentState === liveState ||
        (
          Number.isFinite(currentUpdated) &&
          Number.isFinite(liveUpdated) &&
          currentUpdated >= liveUpdated
        )
      ) {
        this._spcLiveStates.delete(entityId);
      }
    }
  }

  async _ensureStateSubscription() {
    if (
      this._spcStateUnsubscribe ||
      this._spcStateSubscriptionPending ||
      !this.isConnected ||
      !this._hass?.connection?.subscribeEvents
    ) {
      return;
    }

    this._spcStateSubscriptionPending = true;

    try {
      const unsubscribe = await this._hass.connection.subscribeEvents(
        (event) => {
          const entityId = event?.data?.entity_id;
          const newState = event?.data?.new_state || null;
          const oldState = event?.data?.old_state || null;
          const attrs = newState?.attributes || oldState?.attributes || {};
          const isSpcZone =
            entityId?.startsWith("binary_sensor.") &&
            attrs.zone_id != null &&
            attrs.area_id != null &&
            attrs.spc_zone_type != null;

          if (!isSpcZone) {
            return;
          }

          this._spcLiveStates ||= new Map();

          if (newState) {
            this._spcLiveStates.set(entityId, newState);
          } else {
            this._spcLiveStates.delete(entityId);
          }

          if (this.isConnected) {
            this._render();
          }
        },
        "state_changed"
      );

      if (!this.isConnected) {
        unsubscribe();
        return;
      }

      this._spcStateUnsubscribe = unsubscribe;
    } catch (error) {
      console.warn(
        "SPC FlexC Card: unable to subscribe to live zone state changes",
        error
      );
    } finally {
      this._spcStateSubscriptionPending = false;
    }
  }

  _activeTabStorageKey(entityId = this._config?.entity) {
    if (!entityId) {
      return null;
    }

    return `spc-flexc-card:${entityId}:active-tab`;
  }

  _loadActiveTab(entityId) {
    const key = this._activeTabStorageKey(entityId);

    if (!key) {
      return null;
    }

    try {
      const value = window.localStorage.getItem(key);
      return [
        "system",
        "areas",
        "zones",
        "doors",
        "outputs",
        "technical",
      ].includes(value)
        ? value
        : null;
    } catch {
      return null;
    }
  }

  _saveActiveTab(tabId) {
    const key = this._activeTabStorageKey();

    if (!key) {
      return;
    }

    try {
      window.localStorage.setItem(key, tabId);
    } catch {
      // Home Assistant can still keep the tab during normal rerenders even
      // when persistent browser storage is unavailable.
    }
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return {
      columns: 12,
      min_columns: 6,
    };
  }

  _escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _locale() {
    return this._hass?.locale?.language || navigator.language || undefined;
  }

  _formatDateTime(value) {
    if (!value) return null;

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;

    try {
      return new Intl.DateTimeFormat(this._locale(), {
        dateStyle: "short",
        timeStyle: "short",
      }).format(date);
    } catch {
      return date.toLocaleString(this._locale());
    }
  }

  _stateLabel(state) {
    const key = {
      disarmed: "state.disarmed",
      armed_away: "state.armed",
      armed_home: "state.part_a",
      armed_night: "state.part_b",
      armed_vacation: "state.armed",
      armed_custom_bypass: "state.armed",
      arming: "state.arming",
      disarming: "state.disarming",
      triggered: "state.alarm",
      pending: "state.pending",
      unavailable: "state.unavailable",
      unknown: "state.unknown",
      mixed: "state.mixed",
    }[state];

    return key ? this._t(key) : state || this._t("state.unknown_short");
  }

  _stateClass(state) {
    switch (state) {
      case "disarmed":
        return "ok";

      case "armed_away":
      case "armed_home":
      case "armed_night":
      case "armed_vacation":
      case "armed_custom_bypass":
      case "arming":
      case "pending":
      case "mixed":
        return "warning";

      case "triggered":
        return "danger";

      default:
        return "muted";
    }
  }

  _stateIcon(state) {
    switch (state) {
      case "disarmed":
        return "mdi:lock-open-variant";

      case "armed_away":
      case "armed_home":
      case "armed_night":
      case "armed_vacation":
      case "armed_custom_bypass":
        return "mdi:lock";

      case "arming":
      case "pending":
        return "mdi:lock-clock";

      case "mixed":
        return "mdi:lock-alert";

      case "triggered":
        return "mdi:alarm-light";

      case "unavailable":
        return "mdi:alert-circle";

      default:
        return "mdi:shield-outline";
    }
  }

  _modeLabel(mode) {
    const normalized = String(mode ?? "").toLowerCase();
    const key = {
      unset: "state.disarmed_masc",
      disarmed: "state.disarmed_masc",
      full_set: "state.armed_masc",
      fullset: "state.armed_masc",
      set: "state.armed_masc",
      armed: "state.armed_masc",
      part_set_a: "state.part_a",
      partset_a: "state.part_a",
      part_set_b: "state.part_b",
      partset_b: "state.part_b",
      part_set: "state.partial",
      partset: "state.partial",
      unknown: "state.unknown_short",
    }[normalized];

    return key ? this._t(key) : String(mode ?? this._t("state.unknown_short"));
  }

  _modeClass(mode) {
    const normalized = String(mode ?? "").toLowerCase();

    if (normalized === "unset" || normalized === "disarmed") {
      return "ok";
    }

    if (normalized.includes("set") || normalized.includes("armed")) {
      return "warning";
    }

    return "muted";
  }

  _getAlarmEntity() {
    if (!this._hass || !this._config) {
      return undefined;
    }

    return this._hass.states[this._config.entity];
  }

  _getAreas() {
    const alarm = this._getAlarmEntity();
    const rawAreas = alarm?.attributes?.areas;

    if (!rawAreas || typeof rawAreas !== "object") {
      return [];
    }

    return Object.entries(rawAreas)
      .map(([id, area]) => ({
        id: String(id),
        numericId: Number(id),
        name: area?.name || this._t("area.name", { id }),
        mode: area?.mode,
        modeName: area?.mode_name,
        raw: area,
      }))
      .sort((a, b) => {
        if (
          Number.isFinite(a.numericId) &&
          Number.isFinite(b.numericId)
        ) {
          return a.numericId - b.numericId;
        }

        return a.name.localeCompare(b.name);
      });
  }

  _getAreaAlarmEntity(areaId) {
    const ids = this._panelEntityIds();
    if (!ids || !this._hass) {
      return null;
    }

    const id = String(areaId);
    return Array.from(ids)
      .filter((entityId) => entityId.startsWith("alarm_control_panel."))
      .map((entityId) => ({ entityId, stateObj: this._hass.states[entityId] }))
      .find(({ stateObj }) =>
        stateObj && String(stateObj.attributes?.area_id ?? "") === id
      ) || null;
  }

  // Never fall back to a global entity lookup: identical area/zone IDs
  // are normal when multiple SPC panels are configured.
  _panelEntityIds() {
    if (
      this._diagnosticScopeForEntity !== this._config?.entity ||
      !this._diagnosticScope?.integrationEntityIds ||
      !this._diagnosticScope?.selected?.config_entry_id
    ) {
      return null;
    }
    return this._diagnosticScope.integrationEntityIds;
  }

  _getZones() {
    const panelIds = this._panelEntityIds();
    if (!this._hass || !panelIds) {
      return [];
    }

    const states = { ...this._hass.states };

    if (this._spcLiveStates?.size) {
      for (const [entityId, stateObj] of this._spcLiveStates) {
        states[entityId] = stateObj;
      }
    }

    return Object.entries(states)
      .filter(([entityId, stateObj]) => {
        if (!panelIds.has(entityId) || !entityId.startsWith("binary_sensor.")) {
          return false;
        }

        const attrs = stateObj?.attributes || {};

        return (
          attrs.zone_id !== undefined &&
          attrs.zone_id !== null &&
          attrs.area_id !== undefined &&
          attrs.area_id !== null &&
          attrs.spc_zone_type !== undefined &&
          attrs.spc_zone_type !== null &&
          String(attrs.spc_zone_type).trim() !== ""
        );
      })
      .map(([entityId, stateObj]) => {
        const attrs = stateObj.attributes || {};

        return {
          entityId,
          state: stateObj.state,
          zoneId: attrs.zone_id,
          areaId: attrs.area_id,
          zoneType: String(
            attrs.spc_zone_type || ""
          ).toLowerCase(),
          deviceClass: String(
            attrs.device_class || ""
          ).toLowerCase(),
          name:
            attrs.friendly_name ||
            entityId.split(".").pop() ||
            this._t("zone.name", { id: attrs.zone_id }),
          logicInput: attrs.logic_input,
          status: attrs.status,
          procState: attrs.proc_state,
          alarmState: attrs.alarm_state,
          eventTamper: attrs.event_tamper,
          lastEvent: attrs.last_event,
          actuationsSinceLastRead:
            attrs.actuations_since_last_read,
          raw: stateObj,
        };
      })
      .sort((a, b) => {
        const areaA = Number(a.areaId);
        const areaB = Number(b.areaId);

        if (
          Number.isFinite(areaA) &&
          Number.isFinite(areaB) &&
          areaA !== areaB
        ) {
          return areaA - areaB;
        }

        const zoneA = Number(a.zoneId);
        const zoneB = Number(b.zoneId);

        if (
          Number.isFinite(zoneA) &&
          Number.isFinite(zoneB)
        ) {
          return zoneA - zoneB;
        }

        return a.name.localeCompare(b.name);
      });
  }

  _getNormalZones() {
    return this._getZones().filter(
      (zone) =>
        zone.zoneType !== "tamper" &&
        zone.deviceClass !== "tamper"
    );
  }

  _getTamperZones() {
    return this._getZones().filter(
      (zone) =>
        zone.zoneType === "tamper" ||
        zone.deviceClass === "tamper"
    );
  }

  _areaName(areaId) {
    const id = String(areaId);

    const area = this._getAreas().find(
      (candidate) => String(candidate.id) === id
    );

    return area?.name || this._t("area.name", { id });
  }

  _zoneIcon(zone) {
    if (
      zone.zoneType === "tamper" ||
      zone.deviceClass === "tamper"
    ) {
      return "mdi:shield-alert-outline";
    }

    switch (zone.deviceClass) {
      case "motion":
      case "occupancy":
        return "mdi:motion-sensor";

      case "door":
        return "mdi:door";

      case "window":
        return "mdi:window-closed-variant";

      case "opening":
        return "mdi:door-open";

      case "smoke":
        return "mdi:smoke-detector";

      case "heat":
        return "mdi:fire";

      case "moisture":
        return "mdi:water-alert";

      case "gas":
        return "mdi:gas-cylinder";

      default:
        break;
    }

    switch (zone.zoneType) {
      case "entry_exit":
      case "entry-exit":
        return "mdi:door-open";

      case "fire":
        return "mdi:fire";

      case "panic":
        return "mdi:alarm-light";

      default:
        return "mdi:shield-home-outline";
    }
  }

  _zoneStateInfo(zone) {
    const active = zone.state === "on";
    const isTamper =
      zone.zoneType === "tamper" ||
      zone.deviceClass === "tamper";
    const tamperActive =
      zone.eventTamper === true ||
      (isTamper && active);

    if (isTamper) {
      return {
        label: tamperActive
          ? this._t("zone.tamper")
          : this._t("state.normal"),
        className: tamperActive ? "danger" : "ok",
      };
    }

    if (zone.state === "unavailable") {
      return {
        label: this._t("state.unavailable"),
        className: "muted",
      };
    }

    if (zone.state === "unknown") {
      return {
        label: this._t("state.unknown_short"),
        className: "muted",
      };
    }

    switch (zone.deviceClass) {
      case "motion":
      case "occupancy":
        return {
          label: active
            ? this._t("zone.motion")
            : this._t("zone.rest"),
          className: active ? "warning" : "ok",
        };

      case "door":
      case "window":
      case "opening":
        return {
          label: active
            ? this._t("zone.open")
            : this._t("zone.closed"),
          className: active ? "warning" : "ok",
        };

      case "smoke":
        return {
          label: active
            ? this._t("zone.smoke")
            : this._t("state.normal"),
          className: active ? "danger" : "ok",
        };

      case "heat":
        return {
          label: active
            ? this._t("zone.heat")
            : this._t("state.normal"),
          className: active ? "danger" : "ok",
        };

      default:
        return {
          label: active
            ? this._t("zone.active")
            : this._t("zone.rest"),
          className: active ? "warning" : "ok",
        };
    }
  }

  _lastAreaChange(stateObj) {
    if (!stateObj) {
      return "";
    }

    const attrs = stateObj.attributes || {};
    const rows = [
      ["last_arm", "last_set", "area.last_set"],
      ["last_disarm", "last_unset", "area.last_unset"],
    ].map(([prefix, legacyPrefix, labelKey]) => {
      const selectedPrefix = attrs[`${prefix}_time`] ? prefix : legacyPrefix;
      const formattedTime = this._formatDateTime(
        attrs[`${selectedPrefix}_time`]
      );
      if (!formattedTime) {
        return "";
      }

      const user = [
        attrs[`${selectedPrefix}_user_display_name`],
        attrs[`${selectedPrefix}_user_name`],
        attrs[`${selectedPrefix}_user_id`],
      ]
        .map((value) => String(value ?? "").trim())
        .find(Boolean);

      return `
        <div class="last-change">
          <div class="last-change-label">
            ${this._escapeHtml(this._t(labelKey))}
          </div>
          <div class="last-change-value">
            ${this._escapeHtml(formattedTime)}
            ${
              user
                ? `<span class="last-change-user"> · ${this._escapeHtml(user)}</span>`
                : ""
            }
          </div>
        </div>
      `;
    });

    return rows.filter(Boolean).join("");
  }

  async _ensureDiagnosticScope() {
    if (
      !this._hass?.callWS ||
      !this._config?.entity
    ) {
      return;
    }

    if (this._diagnosticScopeLoading) {
      return;
    }

    if (
      this._diagnosticScopeForEntity ===
        this._config.entity &&
      this._diagnosticScope
    ) {
      return;
    }

    this._diagnosticScopeLoading = true;
    const generation = this._scopeGeneration || 0;
    const requestedEntity = this._config.entity;

    try {
      const [entries, devices] = await Promise.all([
        this._hass.callWS({
          type: "config/entity_registry/list",
        }),
        this._hass.callWS({
          type: "config/device_registry/list",
        }).catch(() => []),
      ]);

      // Ignore stale results if the editor switched panels while loading.
      if (generation !== (this._scopeGeneration || 0) ||
          requestedEntity !== this._config?.entity) {
        return;
      }

      const selected = entries.find(
        (entry) => entry.entity_id === requestedEntity
      );

      if (!selected) {
        this._diagnosticScope = {
          method: "none",
          entityIds: null,
          integrationEntityIds: null,
          selected: null,
          device: null,
          integrationEntries: [],
          entryMap: new Map(),
        };
      } else {
        const integrationEntityIds = new Set(
          entries
            .filter((entry) => {
              if (selected.config_entry_id) {
                if (
                  entry.config_entry_id !==
                  selected.config_entry_id
                ) {
                  return false;
                }
              } else if (selected.device_id) {
                if (entry.device_id !== selected.device_id) {
                  return false;
                }
              } else if (
                entry.entity_id !== selected.entity_id
              ) {
                return false;
              }

              if (
                selected.platform &&
                entry.platform &&
                entry.platform !== selected.platform
              ) {
                return false;
              }

              return true;
            })
            .map((entry) => entry.entity_id)
        );

        let entityIds = integrationEntityIds;
        let method = "config_entry";

        if (selected.device_id) {
          entityIds = new Set(
            entries
              .filter(
                (entry) =>
                  entry.device_id &&
                  entry.device_id === selected.device_id
              )
              .map((entry) => entry.entity_id)
          );
          method = "device";
        }

        const device = Array.isArray(devices)
          ? devices.find(
              (candidate) =>
                candidate.id === selected.device_id
            ) || null
          : null;

        const integrationEntries = entries.filter((entry) =>
          integrationEntityIds.has(entry.entity_id)
        );

        this._diagnosticScope = {
          method,
          entityIds,
          integrationEntityIds,
          selected,
          device,
          integrationEntries,
          entryMap: new Map(
            integrationEntries.map((entry) => [entry.entity_id, entry])
          ),
        };
      }
    } catch (error) {
      if (generation !== (this._scopeGeneration || 0) ||
          requestedEntity !== this._config?.entity) {
        return;
      }
      console.warn(
        "SPC FlexC Card: unable to read Home Assistant registries for diagnostics",
        error
      );

      this._diagnosticScope = {
        method: "unavailable",
        entityIds: null,
        integrationEntityIds: null,
        selected: null,
        device: null,
        integrationEntries: [],
        entryMap: new Map(),
      };
    } finally {
      if (generation === (this._scopeGeneration || 0) &&
          requestedEntity === this._config?.entity) {
        this._diagnosticScopeForEntity = requestedEntity;
        this._diagnosticScopeLoading = false;
        this._render();
      }
    }
  }

  _scopeEntityIds(includeIntegration = false) {
    const scope = this._diagnosticScope;

    if (!scope) {
      return null;
    }

    if (
      includeIntegration &&
      scope.integrationEntityIds
    ) {
      return scope.integrationEntityIds;
    }

    return scope.entityIds || null;
  }

  _scopedStates(includeIntegration = false) {
    const ids = this._scopeEntityIds(
      includeIntegration
    );

    if (!ids || !this._hass) {
      return [];
    }

    const entryMap = this._diagnosticScope?.entryMap || new Map();

    return Array.from(ids)
      .map((entityId) => ({
        entityId,
        stateObj: this._hass.states[entityId],
        registryEntry: entryMap.get(entityId) || null,
      }))
      .filter((item) => Boolean(item.stateObj));
  }

  _getSystemDiagnostics() {
    const scope = this._diagnosticScope;

    if (!scope?.entityIds) {
      return {
        scopeAvailable: false,
        connection: null,
        engineerMode: null,
        faults: [],
      };
    }

    const diagnostics = [];

    for (const { entityId, stateObj } of this._scopedStates()) {
      if (!entityId.startsWith("binary_sensor.")) {
        continue;
      }

      const attrs = stateObj.attributes || {};

      if (
        attrs.zone_id !== undefined ||
        attrs.area_id !== undefined ||
        attrs.spc_zone_type !== undefined
      ) {
        continue;
      }

      diagnostics.push({
        entityId,
        stateObj,
        deviceClass: String(
          attrs.device_class || ""
        ).toLowerCase(),
        friendlyName: String(
          attrs.friendly_name || entityId
        ),
      });
    }

    const connection =
      diagnostics.find((item) => {
        if (item.deviceClass !== "connectivity") {
          return false;
        }

        return /flex\s*c|flexc/i.test(
          `${item.entityId} ${item.friendlyName}`
        );
      }) || null;

    const engineerMode =
      diagnostics.find((item) =>
        /engineer[_\s-]*mode|installer|installateur/i.test(
          `${item.entityId} ${item.friendlyName}`
        )
      ) || null;

    const faults = diagnostics
      .filter(
        (item) =>
          item.deviceClass === "problem" &&
          item.stateObj.state === "on"
      )
      .sort((a, b) =>
        a.friendlyName.localeCompare(
          b.friendlyName,
          this._locale()
        )
      );

    return {
      scopeAvailable: true,
      connection,
      engineerMode,
      faults,
    };
  }

  _renderSystemDiagnostics() {
    const diagnostics = this._getSystemDiagnostics();

    let connectionHtml;

    if (!diagnostics.scopeAvailable) {
      connectionHtml = `
        <div class="diagnostic-row">
          <ha-icon class="muted" icon="mdi:lan-disconnect"></ha-icon>
          <div class="diagnostic-main">
            <div class="diagnostic-name">${this._t("system.connection")}</div>
            <div class="diagnostic-detail muted">${this._t("system.state_unknown")}</div>
          </div>
        </div>
      `;
    } else if (!diagnostics.connection) {
      connectionHtml = `
        <div class="diagnostic-row">
          <ha-icon class="muted" icon="mdi:lan"></ha-icon>
          <div class="diagnostic-main">
            <div class="diagnostic-name">${this._t("system.connection")}</div>
            <div class="diagnostic-detail muted">${this._t("system.entity_missing")}</div>
          </div>
        </div>
      `;
    } else {
      const connected =
        diagnostics.connection.stateObj.state === "on";

      connectionHtml = `
        <div class="diagnostic-row">
          <ha-icon
            class="${connected ? "ok" : "danger"}"
            icon="${connected ? "mdi:lan-connect" : "mdi:lan-disconnect"}"
          ></ha-icon>
          <div class="diagnostic-main">
            <div class="diagnostic-name">${this._t("system.connection")}</div>
            <div class="diagnostic-detail ${connected ? "ok" : "danger"}">
              ${this._t(connected ? "state.connected" : "state.disconnected")}
            </div>
          </div>
        </div>
      `;
    }

    const engineerHtml =
      diagnostics.engineerMode?.stateObj?.state === "on"
        ? `
          <div class="diagnostic-row engineer-warning">
            <ha-icon class="warning" icon="mdi:account-hard-hat"></ha-icon>
            <div class="diagnostic-main">
              <div class="diagnostic-name warning">${this._t("system.engineer_active")}</div>
              <div class="diagnostic-detail muted">
                ${this._t("system.engineer_detail")}
              </div>
            </div>
          </div>
        `
        : "";

    const faultsHtml =
      !diagnostics.scopeAvailable
        ? `
          <div class="fault-ok muted">
            <ha-icon icon="mdi:information-outline"></ha-icon>
            <span>${this._t("system.faults_unknown")}</span>
          </div>
        `
        : diagnostics.faults.length
          ? `
            <div class="fault-header danger">
              <ha-icon icon="mdi:alert-circle"></ha-icon>
              <span>${this._t("system.active_faults")}</span>
              <span class="fault-count">${diagnostics.faults.length}</span>
            </div>
            <div class="fault-list">
              ${diagnostics.faults
                .map(
                  (fault) => `
                    <div class="fault-row danger">
                      <ha-icon icon="mdi:alert"></ha-icon>
                      <span>${this._escapeHtml(fault.friendlyName)}</span>
                    </div>
                  `
                )
                .join("")}
            </div>
          `
          : `
            <div class="fault-ok ok">
              <ha-icon icon="mdi:check-circle"></ha-icon>
              <span>${this._t("system.no_fault")}</span>
            </div>
          `;

    return `
      <div class="diagnostics-block">
        <div class="group-title">${this._t("system.health")}</div>
        ${connectionHtml}
        ${engineerHtml}
        ${faultsHtml}
      </div>
    `;
  }

  _valueWithUnit(stateObj) {
    if (!stateObj) return null;

    const state = String(stateObj.state ?? "").trim();
    if (!state || ["unknown", "unavailable"].includes(state)) {
      return null;
    }

    const unit = String(
      stateObj.attributes?.unit_of_measurement || ""
    ).trim();

    return unit ? `${state} ${unit}` : state;
  }

  _findIntegrationState(patterns) {
    return (
      this._scopedStates(true).find(({ entityId, stateObj }) => {
        const friendlyName =
          stateObj?.attributes?.friendly_name || "";
        const haystack = `${entityId} ${friendlyName}`;
        return patterns.some((pattern) => pattern.test(haystack));
      }) || null
    );
  }

  _technicalLine(label, value, className = "") {
    if (
      value === undefined ||
      value === null ||
      String(value).trim() === ""
    ) {
      return "";
    }

    return `
      <div class="technical-row">
        <div class="technical-label">${this._escapeHtml(label)}</div>
        <div class="technical-value ${className}">${this._escapeHtml(value)}</div>
      </div>
    `;
  }

  _entityTechnicalLine(label, match, className = "") {
    return this._technicalLine(
      label,
      this._valueWithUnit(match?.stateObj),
      className
    );
  }

  _getFlexcCommunication() {
    const states = this._scopedStates(true);
    const atsMap = new Map();

    const ensureAts = (atsId) => {
      if (!atsMap.has(atsId)) {
        atsMap.set(atsId, {
          id: atsId,
          name: null,
          entities: [],
          atps: new Map(),
          activePath: null,
        });
      }
      return atsMap.get(atsId);
    };

    const ensureAtp = (ats, atpId) => {
      if (!ats.atps.has(atpId)) {
        ats.atps.set(atpId, {
          id: atpId,
          name: null,
          entities: [],
          lastTxOkTimestamp: null,
          active: null,
          fault: null,
        });
      }
      return ats.atps.get(atpId);
    };

    const friendlyName = (item) =>
      String(
        item.stateObj?.attributes?.friendly_name ||
          item.registryEntry?.original_name ||
          item.entityId ||
          ""
      ).trim();

    const atpNameFromFriendly = (friendly, atpId) => {
      const suffix = new RegExp(
        `\\s+ATP\\s+${atpId}\\s+(?:last\\s+TX\\s+successful|fault)$`,
        "i"
      );
      const match = String(friendly || "").match(suffix);
      if (!match) return null;
      const name = String(friendly).slice(0, match.index).trim();
      return name || null;
    };

    /*
     * SPC FlexC exposes stable registry unique IDs for communication entities:
     *   <entry_id>_ats_<ats_id>_active_path
     *   <entry_id>_ats_<ats_id>_atp_<atp_id>_last_tx_ok
     *   <entry_id>_ats_<ats_id>_atp_<atp_id>_fault
     *
     * Parse only those IDs. Do not infer ATS/ATP numbers from entity names or
     * unrelated states: doing so can incorrectly turn the alarm entity into
     * an ATS 0 / ATP 0.
     */
    for (const item of states) {
      const uniqueId = String(item.registryEntry?.unique_id || "");
      const stateObj = item.stateObj;
      if (!uniqueId || !stateObj) continue;

      let match = uniqueId.match(/_ats_(\d+)_active_path$/);
      if (match) {
        const atsId = Number(match[1]);
        if (atsId < 1) continue;

        const ats = ensureAts(atsId);
        ats.entities.push(item);

        const friendly = friendlyName(item);
        const nameMatch = friendly.match(/^(.*?)\s+active\s+path$/i);
        ats.name = nameMatch?.[1]?.trim() || ats.name;

        const activePath = String(stateObj.state || "").trim();
        if (activePath && !["unknown", "unavailable"].includes(activePath)) {
          ats.activePath = activePath;
        }
        continue;
      }

      match = uniqueId.match(/_ats_(\d+)_atp_(\d+)_(last_tx_ok|fault)$/);
      if (!match) continue;

      const atsId = Number(match[1]);
      const atpId = Number(match[2]);
      const kind = match[3];
      if (atsId < 1 || atpId < 1) continue;

      const ats = ensureAts(atsId);
      const atp = ensureAtp(ats, atpId);
      atp.entities.push(item);

      const parsedName = atpNameFromFriendly(friendlyName(item), atpId);
      if (parsedName && !atp.name) atp.name = parsedName;

      if (kind === "last_tx_ok") {
        const value = String(stateObj.state || "").trim();
        if (value && !["unknown", "unavailable"].includes(value)) {
          atp.lastTxOkTimestamp = value;
        }
      } else if (kind === "fault") {
        if (stateObj.state === "on") atp.fault = true;
        else if (stateObj.state === "off") atp.fault = false;
      }
    }

    const atsList = Array.from(atsMap.values())
      .map((ats) => {
        const rawAtps = Array.from(ats.atps.values()).sort(
          (a, b) => Number(a.id) - Number(b.id)
        );

        const normalizePath = (value) =>
          String(value || "")
            .toLocaleLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\batp\s*\d+\b/g, " ")
            .replace(/[^a-z0-9]+/g, " ")
            .trim();

        const activePath = normalizePath(ats.activePath);

        rawAtps.forEach((atp, index) => {
          atp.displayId = index + 1;

          if (!activePath) return;

          const atpName = normalizePath(atp.name);
          const significantWords = atpName
            .split(/\s+/)
            .filter((word) => word.length >= 3);

          if (
            atpName &&
            (atpName.endsWith(activePath) ||
              activePath.endsWith(atpName) ||
              significantWords.some(
                (word) =>
                  activePath === word ||
                  activePath.startsWith(`${word} `) ||
                  activePath.endsWith(` ${word}`)
              ))
          ) {
            atp.active = true;
          } else {
            atp.active = false;
          }
        });

        if (activePath && rawAtps.length === 1) {
          rawAtps[0].active = true;
          if (!rawAtps[0].name && ats.activePath) {
            rawAtps[0].name = ats.activePath;
          }
        }

        ats.atps = rawAtps;
        return ats;
      })
      .sort((a, b) => Number(a.id) - Number(b.id));

    return atsList;
  }

  _atpStateLabel(atp) {
    if (atp.fault === true || String(atp.fault).toLowerCase() === "true") {
      return { label: this._t("state.fault"), className: "danger" };
    }

    if (atp.active === true || String(atp.active).toLowerCase() === "true") {
      return { label: this._t("state.ok"), className: "ok" };
    }

    if (atp.active === false || String(atp.active).toLowerCase() === "false") {
      return { label: this._t("state.inactive"), className: "muted" };
    }

    if (atp.fault === false || String(atp.fault).toLowerCase() === "false") {
      return { label: this._t("state.ok"), className: "ok" };
    }

    return null;
  }

  _renderFlexcCommunication() {
    const atsList = this._getFlexcCommunication();
    if (!atsList.length) return "";

    return `
      <div class="technical-section">
        <div class="technical-section-title">${this._t("system.communication")}</div>
        <div class="ats-list">
          ${atsList
            .map((ats) => {
              const atsLabel = ats.ungrouped
                ? ats.name
                : `ATS ${ats.id ?? "?"}${
                    ats.name ? ` — ${ats.name}` : ""
                  }`;

              return `
                <div class="ats-card">
                  <div class="ats-title">${this._escapeHtml(atsLabel)}</div>
                  ${ats.atps.length
                    ? `<div class="atp-list">
                        ${ats.atps
                          .map((atp) => {
                            const atpLabel = `ATP ${atp.displayId ?? "?"}${
                              atp.name ? ` — ${atp.name}` : ""
                            }`;
                            const stateInfo = this._atpStateLabel(atp);
                            const formattedTx = this._formatDateTime(
                              atp.lastTxOkTimestamp
                            );

                            return `
                              <div class="atp-card">
                                <div class="atp-title">${this._escapeHtml(atpLabel)}</div>
                                ${stateInfo
                                  ? this._technicalLine(
                                      this._t("system.state"),
                                      stateInfo.label,
                                      stateInfo.className
                                    )
                                  : ""}
                                ${ats.ungrouped
                                  ? ""
                                  : this._technicalLine(
                                      this._t("system.ats_used"),
                                      atsLabel
                                    )}
                                ${this._technicalLine(
                                  this._t("system.last_tx"),
                                  formattedTx
                                )}
                              </div>
                            `;
                          })
                          .join("")}
                      </div>`
                    : ""}
                </div>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
  }

  _getXBusDevices() {
    const devices = new Map();

    for (const { entityId, stateObj } of this._scopedStates(true)) {
      const attrs = stateObj.attributes || {};
      const id = attrs.xbus_device_id;

      if (id === undefined || id === null) {
        continue;
      }

      const key = String(id);
      if (!devices.has(key)) {
        devices.set(key, {
          id,
          name: attrs.xbus_device_name || null,
          siaAddress: attrs.sia_address ?? null,
          tamperFault: attrs.tamper_fault ?? null,
          tamperIsolated: attrs.tamper_isolated ?? null,
          entities: [],
        });
      }

      const device = devices.get(key);
      device.entities.push({ entityId, stateObj });
      if (attrs.xbus_device_name) device.name = attrs.xbus_device_name;
      if (attrs.sia_address !== undefined) device.siaAddress = attrs.sia_address;
      if (attrs.tamper_fault !== undefined) device.tamperFault = attrs.tamper_fault;
      if (attrs.tamper_isolated !== undefined) device.tamperIsolated = attrs.tamper_isolated;
    }

    return Array.from(devices.values()).sort(
      (a, b) => Number(a.id) - Number(b.id)
    );
  }

  _renderXBusDevices() {
    const devices = this._getXBusDevices();
    if (!devices.length) return "";

    return `
      <div class="technical-section">
        <div class="technical-section-title">${this._t("system.xbus")}</div>
        <div class="xbus-list">
          ${devices
            .map((device) => {
              const title = device.name || `X-BUS ${device.id}`;
              const fault = device.tamperFault === true;
              const isolated = device.tamperIsolated === true;

              return `
                <div class="xbus-card">
                  <div class="xbus-title">
                    <span>${this._escapeHtml(title)}</span>
                    <span class="${fault ? "danger" : "ok"}">
                      ${this._t(fault ? "state.fault" : "state.ok")}
                    </span>
                  </div>
                  ${this._technicalLine(this._t("system.xbus_id"), device.id)}
                  ${this._technicalLine(this._t("system.sia_address"), device.siaAddress)}
                  ${device.tamperFault !== null
                    ? this._technicalLine(
                        this._t("system.tamper"),
                        this._t(fault ? "state.fault" : "state.ok"),
                        fault ? "danger" : "ok"
                      )
                    : ""}
                  ${device.tamperIsolated !== null
                    ? this._technicalLine(
                        this._t("system.tamper_isolation"),
                        this._t(isolated ? "state.isolated" : "state.not_isolated"),
                        isolated ? "warning" : "ok"
                      )
                    : ""}
                </div>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
  }

  _renderTechnicalSystem() {
    const scope = this._diagnosticScope;
    const device = scope?.device || {};

    const identityLines = [
      this._technicalLine(this._t("system.manufacturer"), device.manufacturer),
      this._technicalLine(this._t("system.model"), device.model || device.model_id),
      this._technicalLine(this._t("system.firmware"), device.sw_version),
      this._technicalLine(this._t("system.hardware"), device.hw_version),
      this._technicalLine(this._t("system.serial"), device.serial_number),
    ].join("");

    const acFrequency = this._findIntegrationState([
      /ac[_\s-]*frequency/i,
      /fr[ée]quence.*secteur/i,
    ]);
    const batteryVoltage = this._findIntegrationState([
      /battery[_\s-]*voltage/i,
      /tension.*batterie/i,
    ]);
    const auxVoltage = this._findIntegrationState([
      /aux[_\s-]*voltage/i,
      /tension.*aux/i,
    ]);
    const auxCurrent = this._findIntegrationState([
      /aux[_\s-]*current/i,
      /courant.*aux/i,
    ]);

    const powerLines = [
      this._entityTechnicalLine(this._t("system.ac_frequency"), acFrequency),
      this._entityTechnicalLine(this._t("system.battery_voltage"), batteryVoltage),
      this._entityTechnicalLine(this._t("system.aux_voltage"), auxVoltage),
      this._entityTechnicalLine(this._t("system.aux_current"), auxCurrent),
    ].join("");

    const rfEntities = this._scopedStates(true).filter(({ entityId, stateObj }) =>
      /\brf\b|radio/i.test(
        `${entityId} ${stateObj.attributes?.friendly_name || ""}`
      )
    );
    const modemEntities = this._scopedStates(true).filter(({ entityId, stateObj }) =>
      /modem/i.test(
        `${entityId} ${stateObj.attributes?.friendly_name || ""}`
      )
    );

    const renderEntityList = (title, entities) => {
      const rows = entities
        .filter(({ stateObj }) => this._valueWithUnit(stateObj) !== null)
        .map(({ stateObj }) =>
          this._technicalLine(
            stateObj.attributes?.friendly_name || this._t("system.state"),
            this._valueWithUnit(stateObj)
          )
        )
        .join("");

      return rows
        ? `<div class="technical-section">
            <div class="technical-section-title">${this._escapeHtml(title)}</div>
            ${rows}
          </div>`
        : "";
    };

    const identitySection = identityLines
      ? `<div class="technical-section" data-technical-section="panel">
          <div class="technical-section-title">${this._t("system.panel")}</div>
          ${identityLines}
        </div>`
      : "";

    const powerSection = powerLines
      ? `<div class="technical-section">
          <div class="technical-section-title">${this._t("system.power")}</div>
          ${powerLines}
        </div>`
      : "";

    const content = [
      identitySection,
      powerSection,
      this._renderFlexcCommunication(),
      this._renderXBusDevices(),
      renderEntityList(this._t("system.rf"), rfEntities),
      renderEntityList(this._t("system.modem"), modemEntities),
    ].join("");

    if (!content) {
      return "";
    }

    return `
      <div class="technical-system-view">
        ${content}
      </div>
    `;
  }

  async _callAlarmService(
    service,
    entityId = this._config?.entity,
    displayName = null,
    actionLabel = null
  ) {
    if (!this._hass || !entityId) {
      return;
    }

    // Fail closed if the selected panel cannot be established or the target
    // belongs to another config entry. The panel-level entity is allowed.
    const panelIds = this._panelEntityIds();
    if (!panelIds?.has(entityId)) {
      console.warn("SPC FlexC Card: blocked alarm command outside selected panel", entityId);
      return;
    }

    const stateObj = this._hass.states[entityId];
    const name =
      displayName ||
      stateObj?.attributes?.friendly_name ||
      this._config?.name ||
      entityId;

    let prompt = this._t("confirm.generic", { name });

    switch (service) {
      case "alarm_disarm":
        prompt = this._t("confirm.disarm", { name });
        break;

      case "alarm_arm_away":
        prompt = this._t("confirm.full_arm", { name });
        break;

      case "alarm_arm_home":
        prompt = this._t("confirm.part_set", {
          action: actionLabel || this._t("state.part_a"),
          name,
        });
        break;

      case "alarm_arm_night":
        prompt = this._t("confirm.part_set", {
          action: actionLabel || this._t("state.part_b"),
          name,
        });
        break;

      default:
        break;
    }

    if (
      this._config.confirm_actions &&
      !window.confirm(prompt)
    ) {
      return;
    }

    if (!this._panelEntityIds()?.has(entityId)) return;

    await this._hass.callService(
      "alarm_control_panel",
      service,
      {
        entity_id: entityId,
      }
    );
  }

  _getDoors() {
    const doors = new Map();

    const ensureDoor = (doorId) => {
      const key = String(doorId);

      if (!doors.has(key)) {
        doors.set(key, {
          id: doorId,
          name: null,
          areaId: null,
          areaName: null,
          areaSide1: null,
          areaSide1Name: null,
          zoneId: null,
          zoneName: null,
          status: null,
          mode: null,
          buttons: {},
        });
      }

      return doors.get(key);
    };

    for (const item of this._scopedStates(true)) {
      const {
        entityId,
        stateObj,
        registryEntry,
      } = item;

      const attrs = stateObj?.attributes || {};
      const uniqueId = String(registryEntry?.unique_id || "");
      let doorId = attrs.door_id;
      let match = uniqueId.match(/_door_(\d+)_(status|mode)$/);

      if (match) {
        doorId = match[1];
      }

      if (doorId !== undefined && doorId !== null) {
        const door = ensureDoor(doorId);

        door.zoneId = attrs.zone_id ?? door.zoneId;
        door.zoneName = attrs.zone_name || door.zoneName;
        door.areaId = attrs.area_id ?? door.areaId;
        door.areaName = attrs.area_name || door.areaName;
        door.areaSide1 = attrs.area_side_1 ?? door.areaSide1;
        door.areaSide1Name = attrs.area_side_1_name || door.areaSide1Name;
        door.name = attrs.zone_name || door.name;

        const rawStatus = attrs.raw_status;
        const rawMode = attrs.raw_mode;

        if (match?.[2] === "status" || rawStatus !== undefined) {
          door.status = rawStatus ?? stateObj.state;
        }

        if (match?.[2] === "mode" || rawMode !== undefined) {
          door.mode = rawMode ?? stateObj.state;
        }

        if (!door.name) {
          const friendly = String(attrs.friendly_name || "").trim();
          door.name =
            friendly
              .replace(/\s+(Status|Mode|Statut)$/i, "")
              .trim() || null;
        }
      }

      match = uniqueId.match(
        /_door_(\d+)_(open_momentarily|open_permanently|set_normal|lock)$/
      );

      if (match && entityId.startsWith("button.")) {
        const door = ensureDoor(match[1]);
        door.buttons[match[2]] = entityId;
      }
    }

    return Array.from(doors.values())
      .filter(
        (door) =>
          door.status !== null ||
          door.mode !== null ||
          Object.keys(door.buttons).length
      )
      .map((door) => ({
        ...door,
        name:
          door.name ||
          door.zoneName ||
          this._t("door.name", { id: door.id }),
      }))
      .sort((a, b) => Number(a.id) - Number(b.id));
  }

  _doorAreasLabel(door) {
    const first =
      door.areaName ||
      (
        door.areaId !== null &&
        door.areaId !== undefined
          ? this._areaName(door.areaId)
          : null
      );

    const second =
      door.areaSide1Name ||
      (
        door.areaSide1 !== null &&
        door.areaSide1 !== undefined
          ? this._areaName(door.areaSide1)
          : null
      );

    if (first && second && first !== second) {
      return `${first} ↔ ${second}`;
    }

    return first || second || this._t("door.unknown_area");
  }

  _renderDoorButton(
    door,
    action,
    label,
    icon,
    primary = false
  ) {
    const entityId = door.buttons[action];

    if (!entityId || this._config.show_controls === false) {
      return "";
    }

    return `
      <button
        type="button"
        class="control-button door-control${primary ? " primary" : ""}"
        data-door-entity="${this._escapeHtml(entityId)}"
        data-door-name="${this._escapeHtml(door.name)}"
        data-door-action="${this._escapeHtml(label)}"
      >
        <ha-icon icon="${this._escapeHtml(icon)}"></ha-icon>
        <span>${this._escapeHtml(label)}</span>
      </button>
    `;
  }

  _renderDoors() {
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
        ${doors
          .map(
            (door) => `
              <div class="door-card">
                <div class="door-header">
                  <div>
                    <div class="door-title">${this._escapeHtml(door.name)}</div>
                    <div class="door-areas">${this._escapeHtml(this._doorAreasLabel(door))}</div>
                  </div>
                  <ha-icon class="door-icon" icon="mdi:door"></ha-icon>
                </div>

                <div class="door-state-grid">
                  <div class="door-state-card">
                    <div class="door-state-label">${this._t("door.status")}</div>
                    <div class="door-state-value">${this._escapeHtml(door.status ?? "—")}</div>
                  </div>
                  <div class="door-state-card">
                    <div class="door-state-label">${this._t("door.mode")}</div>
                    <div class="door-state-value">${this._escapeHtml(door.mode ?? "—")}</div>
                  </div>
                </div>

                ${
                  door.zoneName
                    ? `
                      <div class="door-zone">
                        <ha-icon icon="mdi:shield-home-outline"></ha-icon>
                        <span>
                          ${this._t("zone.name", { id: door.zoneId ?? "" })}${
                            door.zoneId != null ? " · " : ""
                          }${this._escapeHtml(door.zoneName)}
                        </span>
                      </div>
                    `
                    : ""
                }

                <div class="door-controls">
                  ${this._renderDoorButton(
                    door,
                    "open_momentarily",
                    this._t("action.door_momentary"),
                    "mdi:door-open",
                    true
                  )}
                  ${this._renderDoorButton(
                    door,
                    "open_permanently",
                    this._t("action.door_permanent"),
                    "mdi:lock-open-variant"
                  )}
                  ${this._renderDoorButton(
                    door,
                    "set_normal",
                    this._t("action.door_normal"),
                    "mdi:door-closed"
                  )}
                  ${this._renderDoorButton(
                    door,
                    "lock",
                    this._t("action.door_lock"),
                    "mdi:lock"
                  )}
                </div>

                <div class="door-raw-note">
                  ${this._t("door.raw_note")}
                </div>
              </div>
            `
          )
          .join("")}
      </div>
    `;
  }

  async _callDoorButton(entityId, doorName, actionLabel) {
    if (!this._hass || !entityId) {
      return;
    }

    if (!this._panelEntityIds()?.has(entityId)) {
      console.warn("SPC FlexC Card: blocked cross-panel door command", entityId);
      return;
    }

    if (
      this._config.confirm_actions &&
      !window.confirm(
        this._t("confirm.door", {
          action: actionLabel,
          name: doorName,
        })
      )
    ) {
      return;
    }

    if (!this._panelEntityIds()?.has(entityId)) return;

    await this._hass.callService(
      "button",
      "press",
      {
        entity_id: entityId,
      }
    );
  }

  _renderTabs() {
    const hasDoors = this._getDoors().length > 0;

    if (!hasDoors && this._activeTab === "doors") {
      this._activeTab = "system";
    }

    const tabs = [
      ["system", this._t("tab.general")],
      ["areas", this._t("tab.areas")],
      ["zones", this._t("tab.detectors")],
      ...(hasDoors ? [["doors", this._t("tab.doors")]] : []),
      ["technical", this._t("tab.system")],
    ];

    return `<div class="tabs">${tabs.map(([id, label]) => `
      <button type="button" class="tab ${this._activeTab === id ? "active" : ""}" data-tab="${id}">
        ${this._escapeHtml(label)}
      </button>
    `).join("")}</div>`;
  }

  _renderSystem() {
    const alarm = this._getAlarmEntity();
    const rawState = alarm?.state || "unknown";
    const state = rawState === "unknown" && alarm?.attributes?.arming_summary === "mixed"
      ? "mixed"
      : rawState;
    const areas = this._getAreas();
    const zones = this._getNormalZones();
    const tampers = this._getTamperZones();

    const activeZones = zones.filter(
      (zone) => zone.state === "on"
    ).length;

    const activeTampers = tampers.filter(
      (zone) =>
        zone.state === "on" ||
        zone.eventTamper === true
    ).length;

    const controls =
      this._config.show_controls
        ? `
          <div class="alarm-controls system-controls">
            <button
              type="button"
              class="control-button"
              data-service="alarm_disarm"
              data-entity="${this._escapeHtml(this._config.entity)}"
            >
              <ha-icon icon="mdi:lock-open-variant"></ha-icon>
              <span>${this._t("action.disarm")}</span>
            </button>

            <button
              type="button"
              class="control-button primary"
              data-service="alarm_arm_away"
              data-entity="${this._escapeHtml(this._config.entity)}"
            >
              <ha-icon icon="mdi:lock"></ha-icon>
              <span>${this._t("action.full_arm")}</span>
            </button>
          </div>
        `
        : "";

    const areaSummary = areas.length
      ? this._tCount("group.area_count", areas.length)
      : this._t("group.no_area");
    const detectorSummary = zones.length
      ? this._tCount("group.detector_count", zones.length)
      : this._t("group.no_detector");

    return `
      <div class="system-view">
        <div class="system-panel">
          <div class="system-state ${this._stateClass(state)}">
            ${this._escapeHtml(this._stateLabel(state))}
          </div>

          <ha-icon
            class="system-icon ${this._stateClass(state)}"
            icon="${this._escapeHtml(this._stateIcon(state))}"
          ></ha-icon>

          <div class="system-summary">
            ${areaSummary} · ${detectorSummary}
          </div>
        </div>

        <div class="summary-grid">
          <div class="summary-card">
            <ha-icon icon="mdi:shield-home-outline"></ha-icon>
            <div>
              <div class="summary-value">${areas.length}</div>
              <div class="summary-label">${this._t("tab.areas")}</div>
            </div>
          </div>

          <div class="summary-card">
            <ha-icon icon="mdi:motion-sensor"></ha-icon>
            <div>
              <div class="summary-value">${zones.length}</div>
              <div class="summary-label">
                ${this._t("tab.detectors")}
                ${
                  activeZones
                    ? `<span class="warning"> · ${this._tCount("group.active_count", activeZones)}</span>`
                    : ""
                }
              </div>
            </div>
          </div>

          <div class="summary-card">
            <ha-icon icon="mdi:shield-alert-outline"></ha-icon>
            <div>
              <div class="summary-value">${tampers.length}</div>
              <div class="summary-label">
                ${this._t("group.tampers")}
                ${
                  activeTampers
                    ? `<span class="danger"> · ${this._t("group.in_fault", { count: activeTampers })}</span>`
                    : ""
                }
              </div>
            </div>
          </div>
        </div>

        ${this._renderSystemDiagnostics()}
        ${controls}
      </div>
    `;
  }

  _partSetLabel(areaEntity, part) {
    const attrs = areaEntity?.stateObj?.attributes || {};
    const attributeName = part === "a" ? "partset_a_name" : "partset_b_name";
    const value = attrs[attributeName];

    return value != null && String(value).trim()
      ? String(value).trim()
      : this._t(part === "a" ? "state.part_a" : "state.part_b");
  }

  _renderAreaControls(area, areaEntity) {
    if (!this._config.show_controls || !areaEntity) {
      return "";
    }

    const { entityId, stateObj } = areaEntity;
    const attrs = stateObj?.attributes || {};
    const state = stateObj?.state || "unknown";

    const stableArmedStates = new Set([
      "armed_away",
      "armed_home",
      "armed_night",
      "armed_vacation",
      "armed_custom_bypass",
    ]);

    const buttons = [];

    if (state === "disarmed") {
      buttons.push(`
        <button
          type="button"
          class="control-button primary"
          data-service="alarm_arm_away"
          data-entity="${this._escapeHtml(entityId)}"
          data-name="${this._escapeHtml(area.name)}"
        >
          <ha-icon icon="mdi:lock"></ha-icon>
          <span>${this._t("action.arm")}</span>
        </button>
      `);

      if (attrs.partset_a_enabled === true) {
        const label = this._partSetLabel(areaEntity, "a");
        buttons.push(`
          <button
            type="button"
            class="control-button"
            data-service="alarm_arm_home"
            data-entity="${this._escapeHtml(entityId)}"
            data-name="${this._escapeHtml(area.name)}"
            data-action-label="${this._escapeHtml(label)}"
          >
            <ha-icon icon="mdi:shield-home"></ha-icon>
            <span>${this._escapeHtml(label)}</span>
          </button>
        `);
      }

      if (attrs.partset_b_enabled === true) {
        const label = this._partSetLabel(areaEntity, "b");
        buttons.push(`
          <button
            type="button"
            class="control-button"
            data-service="alarm_arm_night"
            data-entity="${this._escapeHtml(entityId)}"
            data-name="${this._escapeHtml(area.name)}"
            data-action-label="${this._escapeHtml(label)}"
          >
            <ha-icon icon="mdi:weather-night"></ha-icon>
            <span>${this._escapeHtml(label)}</span>
          </button>
        `);
      }
    } else if (stableArmedStates.has(state) || state === "triggered") {
      buttons.push(`
        <button
          type="button"
          class="control-button"
          data-service="alarm_disarm"
          data-entity="${this._escapeHtml(entityId)}"
          data-name="${this._escapeHtml(area.name)}"
        >
          <ha-icon icon="mdi:lock-open-variant"></ha-icon>
          <span>${this._t("action.disarm")}</span>
        </button>
      `);
    }

    if (!buttons.length) {
      return "";
    }

    return `
      <div class="area-controls">
        ${buttons.join("")}
      </div>
    `;
  }

  _renderAreas() {
    const areas = this._getAreas();
    const zones = this._getZones();

    if (!areas.length) {
      return `
        <div class="empty-state">
          <ha-icon icon="mdi:shield-home-outline"></ha-icon>
          <div>${this._t("area.none")}</div>
        </div>
      `;
    }

    return `
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

            const activeZones = normalZones.filter(
              (zone) => zone.state === "on"
            ).length;

            const activeTampers = tampers.filter(
              (zone) =>
                zone.state === "on" ||
                zone.eventTamper === true
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

            return `
              <div class="area-card">
                <div class="area-card-header">
                  <div class="area-card-title">${this._escapeHtml(area.name)}</div>
                  <div class="badge ${stateClass}">${this._escapeHtml(label)}</div>
                </div>

                <div class="area-lock">
                  <ha-icon class="${stateClass}" icon="${this._escapeHtml(icon)}"></ha-icon>
                </div>

                <div class="area-meta">
                  <span>${this._tCount("group.detector_count", normalZones.length)}</span>
                  ${
                    activeZones
                      ? `<span class="warning">${this._tCount("group.active_count", activeZones)}</span>`
                      : `<span class="ok">${this._t("group.rest")}</span>`
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
            `;
          })
          .join("")}
      </div>
    `;
  }

  _renderZoneRow(zone) {
    const stateInfo = this._zoneStateInfo(zone);

    return `
      <div class="zone-row">
        <div class="zone-icon ${stateInfo.className}">
          <ha-icon icon="${this._escapeHtml(this._zoneIcon(zone))}"></ha-icon>
        </div>

        <div class="zone-main">
          <div class="zone-name">${this._escapeHtml(zone.name)}</div>
          <div class="zone-area">${this._escapeHtml(this._areaName(zone.areaId))}</div>
        </div>

        <div class="zone-state ${stateInfo.className}">
          ${this._escapeHtml(stateInfo.label)}
        </div>
      </div>
    `;
  }

  _renderZones() {
    const zones = this._getNormalZones();
    const tampers = this._getTamperZones();

    if (!zones.length && !tampers.length) {
      return `
        <div class="empty-state">
          <ha-icon icon="mdi:motion-sensor-off"></ha-icon>
          <div>${this._t("zone.none")}</div>
        </div>
      `;
    }

    return `
      <div class="zones-view">
        ${
          zones.length
            ? `
              <div class="group-title">
                ${this._t("group.detectors")}
                <span>${zones.length}</span>
              </div>
              <div class="zone-list">
                ${zones.map((zone) => this._renderZoneRow(zone)).join("")}
              </div>
            `
            : ""
        }

        ${
          tampers.length
            ? `
              <div class="group-title tamper-title">
                ${this._t("group.tampers")}
                <span>${tampers.length}</span>
              </div>
              <div class="zone-list tamper-list">
                ${tampers.map((zone) => this._renderZoneRow(zone)).join("")}
              </div>
            `
            : ""
        }
      </div>
    `;
  }

  _renderIntrusionBanner() {
    const alarm = this._getAlarmEntity();
    const areas = this._getAreas();
    const active = areas.filter((area) => area.raw?.alarm_event_active === true);
    if (!active.length && alarm?.state !== "triggered") return "";

    const details = active.map((area) => {
      const zones = Array.isArray(area.raw?.alarm_zones)
        ? area.raw.alarm_zones.map((zone) => zone?.name || `Zone ${zone?.zone_id ?? "?"}`)
        : [];
      return this._escapeHtml(
        zones.length ? `${area.name} : ${zones.join(", ")}` : area.name
      );
    });

    return `
      <div class="spc-intrusion-banner" role="alert" aria-live="assertive">
        <ha-icon icon="mdi:alarm-light"></ha-icon>
        <div>
          <strong>${this._escapeHtml(this._t("state.alarm"))}</strong>
          ${details.length ? `<div>${details.join("<br>")}</div>` : ""}
        </div>
      </div>
    `;
  }

  _renderActiveView() {
    switch (this._activeTab) {
      case "areas":
        return this._renderAreas();

      case "zones":
        return this._renderZones();

      case "doors":
        return this._getDoors().length
          ? this._renderDoors()
          : this._renderSystem();

      case "technical":
        return this._renderTechnicalSystem();

      case "system":
      default:
        return this._renderSystem();
    }
  }

  _styles() {
    return `
      <style>
        :host {
          display: block;
          width: 100%;
        }

        ha-card {
          overflow: hidden;
          padding: 0;
          width: 100%;
        }

        .card {
          padding: 22px;
        }

        .spc-intrusion-banner {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 14px;
          margin-bottom: 16px;
          border-radius: 10px;
          background: var(--error-color, #b3261e);
          color: #fff;
          animation: spc-intrusion-pulse 1.3s ease-in-out infinite;
        }

        .spc-intrusion-banner ha-icon {
          flex-shrink: 0;
        }

        @keyframes spc-intrusion-pulse {
          50% { opacity: 0.65; }
        }

        @media (prefers-reduced-motion: reduce) {
          .spc-intrusion-banner { animation: none; }
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 10px;
        }

        .title {
          font-size: 24px;
          line-height: 1.2;
          font-weight: 600;
        }

        .entity {
          margin-top: 4px;
          color: var(--secondary-text-color);
          font-size: 12px;
        }

        .tabs {
          display: flex;
          gap: 28px;
          overflow-x: auto;
          border-bottom: 1px solid var(--divider-color);
          margin: 0 -22px 20px;
          padding: 0 22px;
        }

        .tab {
          appearance: none;
          border: 0;
          border-bottom: 3px solid transparent;
          background: transparent;
          color: var(--secondary-text-color);
          cursor: pointer;
          font: inherit;
          font-weight: 600;
          padding: 12px 0 10px;
          white-space: nowrap;
        }

        .tab:hover {
          color: var(--primary-text-color);
        }

        .tab.active {
          color: var(--primary-color);
          border-bottom-color: var(--primary-color);
        }

        .system-panel {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 260px;
          padding: 28px;
          border-radius: 14px;
          background: var(
            --secondary-background-color,
            rgba(127, 127, 127, 0.08)
          );
        }

        .system-state {
          font-size: 22px;
          font-weight: 700;
          text-align: center;
        }

        .system-icon {
          --mdc-icon-size: 140px;
          margin: 22px 0;
        }

        .system-summary {
          color: var(--secondary-text-color);
          text-align: center;
        }

        .summary-grid {
          display: grid;
          grid-template-columns: repeat(
            3,
            minmax(0, 1fr)
          );
          gap: 12px;
          margin-top: 16px;
        }

        .summary-card {
          display: flex;
          align-items: center;
          gap: 8px;
          min-width: 0;
          padding: 12px;
          border: 1px solid var(--divider-color);
          border-radius: 12px;
        }

        .summary-card ha-icon {
          --mdc-icon-size: 28px;
          flex: 0 0 auto;
        }

        .summary-card > div {
          min-width: 0;
        }

        .summary-value {
          font-size: 20px;
          font-weight: 700;
          line-height: 1.1;
        }

        .summary-label {
          max-width: 100%;
          color: var(--secondary-text-color);
          font-size: 11px;
          line-height: 1.25;
          white-space: normal;
          overflow-wrap: anywhere;
          word-break: normal;
          hyphens: auto;
        }

        .alarm-controls {
          display: grid;
          gap: 10px;
          margin-top: 18px;
        }

        .system-controls {
          grid-template-columns: repeat(
            2,
            minmax(0, 1fr)
          );
        }

        .area-controls {
          display: grid;
          grid-template-columns: repeat(
            auto-fit,
            minmax(120px, 1fr)
          );
          gap: 10px;
          margin-top: 16px;
        }

        .control-button {
          appearance: none;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 7px;
          min-height: 70px;
          padding: 10px;
          border: 1px solid var(--divider-color);
          border-radius: 12px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          cursor: pointer;
          font: inherit;
        }

        .control-button:hover {
          background: var(
            --secondary-background-color,
            rgba(127, 127, 127, 0.08)
          );
        }

        .control-button.primary {
          border-color: var(--primary-color);
          color: var(--primary-color);
        }

        .control-button ha-icon {
          --mdc-icon-size: 27px;
        }

        .diagnostics-block {
          margin-top: 18px;
          padding: 16px;
          border: 1px solid var(--divider-color);
          border-radius: 14px;
        }

        .diagnostic-row {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 4px 0 12px;
        }

        .diagnostic-row > ha-icon {
          --mdc-icon-size: 28px;
        }

        .diagnostic-main {
          min-width: 0;
        }

        .diagnostic-name {
          font-weight: 600;
        }

        .diagnostic-detail {
          margin-top: 2px;
          font-size: 12px;
        }

        .fault-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 8px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color);
          font-weight: 700;
        }

        .fault-count {
          margin-left: auto;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 22px;
          height: 22px;
          padding: 0 6px;
          border-radius: 11px;
          background: color-mix(
            in srgb,
            currentColor 14%,
            transparent
          );
        }

        .fault-list {
          display: grid;
          gap: 7px;
          margin-top: 10px;
        }

        .fault-row {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 10px;
          border-radius: 9px;
          background: var(
            --secondary-background-color,
            rgba(127, 127, 127, 0.08)
          );
        }

        .fault-row ha-icon {
          --mdc-icon-size: 20px;
        }

        .fault-ok {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 8px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color);
          font-weight: 600;
        }

        .engineer-warning {
          margin-top: 8px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color);
        }

        .technical-system-view {
          display: grid;
          gap: 18px;
        }

        .technical-section {
          padding-top: 15px;
        }

        .technical-section-title {
          margin-bottom: 8px;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }

        .technical-row {
          display: grid;
          grid-template-columns: minmax(130px, 0.7fr) minmax(0, 1.3fr);
          gap: 14px;
          padding: 6px 0;
          border-bottom: 1px solid color-mix(
            in srgb,
            var(--divider-color) 55%,
            transparent
          );
        }

        .technical-row:last-child {
          border-bottom: 0;
        }

        .technical-label {
          color: var(--secondary-text-color);
          font-size: 12px;
        }

        .technical-value {
          min-width: 0;
          overflow-wrap: anywhere;
          text-align: right;
          font-size: 13px;
          font-weight: 600;
        }

        .ats-list,
        .atp-list,
        .xbus-list {
          display: grid;
          gap: 10px;
        }

        .ats-card,
        .atp-card,
        .xbus-card {
          padding: 12px;
          border-radius: 11px;
          background: var(
            --secondary-background-color,
            rgba(127, 127, 127, 0.08)
          );
        }

        .atp-list {
          margin-top: 10px;
          padding-left: 10px;
          border-left: 2px solid var(--divider-color);
        }

        .atp-card {
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
        }

        .ats-title,
        .atp-title,
        .xbus-title {
          font-weight: 700;
        }

        .xbus-title {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 4px;
        }

        .list {
          display: grid;
          gap: 14px;
        }

        .area-list {
          grid-template-columns: repeat(
            auto-fit,
            minmax(280px, 1fr)
          );
        }

        .area-card {
          padding: 18px;
          border-radius: 14px;
          background: var(
            --secondary-background-color,
            rgba(127, 127, 127, 0.08)
          );
        }

        .area-card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        .area-card-title {
          font-size: 18px;
          font-weight: 700;
        }

        .badge {
          font-weight: 700;
        }

        .area-lock {
          display: flex;
          justify-content: center;
          padding: 18px 0 10px;
        }

        .area-lock ha-icon {
          --mdc-icon-size: 78px;
        }

        .area-meta {
          display: flex;
          justify-content: center;
          flex-wrap: wrap;
          gap: 8px 18px;
          color: var(--secondary-text-color);
          font-size: 12px;
        }

        .last-change {
          margin-top: 15px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color);
          text-align: center;
        }

        .last-change-label {
          color: var(--secondary-text-color);
          font-size: 12px;
        }

        .last-change-value {
          margin-top: 4px;
          font-size: 13px;
          color: var(--primary-text-color);
        }

        .last-change-user {
          color: var(--secondary-text-color);
        }

        .zones-view {
          display: grid;
          gap: 12px;
        }

        .group-title {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 2px;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }

        .group-title span {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 18px;
          height: 18px;
          padding: 0 5px;
          border-radius: 9px;
          background: var(
            --secondary-background-color,
            rgba(127, 127, 127, 0.12)
          );
          font-size: 10px;
        }

        .tamper-title {
          margin-top: 16px;
        }

        .zone-list {
          display: grid;
          gap: 7px;
        }

        .zone-row {
          display: grid;
          grid-template-columns:
            46px minmax(0, 1fr) auto;
          align-items: center;
          gap: 12px;
          min-height: 52px;
          padding: 8px 12px;
          border-radius: 10px;
          background: var(
            --secondary-background-color,
            rgba(127, 127, 127, 0.08)
          );
        }

        .zone-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border: 2px solid currentColor;
          border-radius: 50%;
        }

        .zone-icon ha-icon {
          --mdc-icon-size: 22px;
        }

        .zone-main {
          min-width: 0;
        }

        .zone-name {
          overflow: hidden;
          font-weight: 600;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .zone-area {
          overflow: hidden;
          margin-top: 2px;
          color: var(--secondary-text-color);
          font-size: 12px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .zone-state {
          font-weight: 700;
          text-align: right;
          white-space: nowrap;
        }

        .door-list {
          display: grid;
          grid-template-columns: repeat(
            auto-fit,
            minmax(300px, 1fr)
          );
          gap: 14px;
        }

        .door-card {
          padding: 18px;
          border-radius: 14px;
          background: var(
            --secondary-background-color,
            rgba(127, 127, 127, 0.08)
          );
        }

        .door-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 14px;
        }

        .door-title {
          font-size: 18px;
          font-weight: 700;
        }

        .door-areas,
        .door-zone,
        .door-raw-note {
          color: var(--secondary-text-color);
          font-size: 12px;
        }

        .door-areas {
          margin-top: 3px;
        }

        .door-icon {
          --mdc-icon-size: 38px;
        }

        .door-state-grid {
          display: grid;
          grid-template-columns:
            1fr 1fr;
          gap: 10px;
          margin-top: 16px;
        }

        .door-state-card {
          padding: 11px 12px;
          border: 1px solid var(--divider-color);
          border-radius: 10px;
        }

        .door-state-label {
          color: var(--secondary-text-color);
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .door-state-value {
          margin-top: 3px;
          font-size: 18px;
          font-weight: 700;
        }

        .door-zone {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-top: 12px;
        }

        .door-zone ha-icon {
          --mdc-icon-size: 18px;
        }

        .door-controls {
          display: grid;
          grid-template-columns:
            repeat(2, minmax(0, 1fr));
          gap: 10px;
          margin-top: 16px;
        }

        .door-raw-note {
          margin-top: 14px;
          line-height: 1.4;
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 12px;
          min-height: 180px;
          color: var(--secondary-text-color);
          text-align: center;
        }

        .empty-state ha-icon {
          --mdc-icon-size: 54px;
        }

        .ok {
          color: var(
            --success-color,
            #4caf50
          );
        }

        .warning {
          color: var(
            --warning-color,
            #ff9800
          );
        }

        .danger {
          color: var(
            --error-color,
            #f44336
          );
        }

        .muted {
          color: var(--secondary-text-color);
        }

        @media (max-width: 520px) {
          .door-list,
          .door-controls,
          .door-state-grid {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 700px) {
          .card {
            padding: 16px;
          }

          .tabs {
            margin-left: -16px;
            margin-right: -16px;
            padding-left: 16px;
            padding-right: 16px;
          }

          .summary-grid {
            grid-template-columns: 1fr;
          }

          .technical-row {
            grid-template-columns: 1fr;
            gap: 2px;
          }

          .technical-value {
            text-align: left;
          }

          .system-controls {
            grid-template-columns: repeat(
              2,
              minmax(0, 1fr)
            );
          }

          .area-list {
            grid-template-columns: 1fr;
          }

          .system-panel {
            min-height: 220px;
          }

          .system-icon {
            --mdc-icon-size: 110px;
          }
        }

        @media (max-width: 420px) {
          .zone-row {
            grid-template-columns:
              40px minmax(0, 1fr);
          }

          .zone-state {
            grid-column: 2;
            text-align: left;
            font-size: 12px;
          }

          .system-controls {
            grid-template-columns:
              1fr 1fr;
          }
        }
      </style>
    `;
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }

    const stateObj = this._getAlarmEntity();

    if (!stateObj) {
      this.innerHTML = `
        <ha-card>
          <div style="padding:16px">
            ${this._escapeHtml(
              this._t("card.entity_not_found", {
                entity: this._config.entity,
              })
            )}
          </div>
        </ha-card>
      `;
      return;
    }

    const title =
      this._config.name ||
      stateObj.attributes.friendly_name ||
      "SPC FlexC";

    const previousCard = this.querySelector(":scope > ha-card");
    const previousTabIds = previousCard
      ? Array.from(previousCard.querySelectorAll("[data-tab]"), (tab) => tab.dataset.tab).join("|")
      : null;
    const previousActiveTab = previousCard?.querySelector("[data-tab].active")?.dataset.tab;

    const markup = `
      <ha-card>
        ${this._styles()}

        <div class="card">
          <div class="header">
            <div>
              <div class="title">
                ${this._escapeHtml(title)}
              </div>
            </div>
          </div>

          ${this._renderTabs()}

          ${this._renderIntrusionBanner()}

          <div class="content">
            ${this._renderActiveView()}
          </div>
        </div>
      </ha-card>
    `;
    const template = document.createElement("template");
    template.innerHTML = markup;
    const nextCard = template.content.querySelector("ha-card");
    const nextTabIds = Array.from(nextCard.querySelectorAll("[data-tab]"), (tab) => tab.dataset.tab).join("|");
    const nextActiveTab = nextCard.querySelector("[data-tab].active")?.dataset.tab;
    const preserveTabs = previousCard &&
      previousTabIds === nextTabIds &&
      previousActiveTab === nextActiveTab;

    if (preserveTabs) {
      // Keep the existing tab strip connected during routine state updates.
      // Firefox otherwise reactivates its overlay scrollbar on each DOM detach.
      const oldContent = previousCard.querySelector(".content");
      const nextContent = nextCard.querySelector(".content");
      if (oldContent && nextContent) oldContent.replaceWith(nextContent);

      const oldBanner = previousCard.querySelector(".spc-intrusion-banner");
      const nextBanner = nextCard.querySelector(".spc-intrusion-banner");
      if (oldBanner && nextBanner) oldBanner.replaceWith(nextBanner);
      else if (oldBanner) oldBanner.remove();
      else if (nextBanner) previousCard.querySelector(".content")?.before(nextBanner);

      const oldTitle = previousCard.querySelector(".title");
      const nextTitle = nextCard.querySelector(".title");
      if (oldTitle && nextTitle) oldTitle.textContent = nextTitle.textContent;
    } else {
      this.replaceChildren(nextCard);
    }

    if (!preserveTabs) this.querySelectorAll("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        this._activeTab = button.dataset.tab;
        this._saveActiveTab(this._activeTab);
        this._render();
      });
    });

    this.querySelectorAll("[data-service]").forEach((button) => {
      button.addEventListener("click", () => {
        this._callAlarmService(
          button.dataset.service,
          button.dataset.entity || this._config.entity,
          button.dataset.name || null,
          button.dataset.actionLabel || null
        );
      });
    });

    this.querySelectorAll("[data-door-entity]").forEach((button) => {
      button.addEventListener("click", () => {
        this._callDoorButton(
          button.dataset.doorEntity,
          button.dataset.doorName || this._t("door.fallback_name"),
          button.dataset.doorAction || this._t("action.execute")
        );
      });
    });
  }
}

class SpcFlexCCardEditor extends HTMLElement {
  setConfig(config) {
    const nextConfig = {
      show_controls: true,
      confirm_actions: true,
      ...config,
    };
    const previousConfig = this._config;
    this._config = nextConfig;

    // Home Assistant may echo config-changed back through setConfig.
    // Do not replace focused inputs when the visible settings are unchanged.
    if (
      !previousConfig ||
      previousConfig.entity !== nextConfig.entity ||
      previousConfig.name !== nextConfig.name ||
      previousConfig.show_controls !== nextConfig.show_controls ||
      previousConfig.confirm_actions !== nextConfig.confirm_actions
    ) {
      this._render();
    }
  }

  set hass(hass) {
    const wasReady = Boolean(this._hass);
    this._hass = hass;
    // State updates are frequent: rebuilding the editor would close an open
    // dropdown and reset a field while the user is typing.
    if (!wasReady) {
      this._render();
    }
  }

  _escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _t(key, variables = {}, fallback = key) {
    if (typeof spcFlexCTranslate === "function") {
      return spcFlexCTranslate(this._hass, key, variables, fallback);
    }
    return fallback;
  }

  _changed() {
    const config = {
      ...this._config,

      entity:
        this.querySelector("#entity")?.value || "",

      name:
        this.querySelector("#name")?.value || undefined,

      show_controls: Boolean(
        this.querySelector("#show_controls")?.checked
      ),

      confirm_actions: Boolean(
        this.querySelector("#confirm_actions")?.checked
      ),
    };

    this._config = config;

    this.dispatchEvent(
      new CustomEvent(
        "config-changed",
        {
          detail: { config },
          bubbles: true,
          composed: true,
        }
      )
    );
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }

    const options = Object.keys(this._hass.states)
      .filter((id) => id.startsWith("alarm_control_panel."))
      .map((id) => {
        const stateObj = this._hass.states[id];
        const name = stateObj?.attributes?.friendly_name || id;

        return `
          <option
            value="${this._escapeHtml(id)}"
            ${id === this._config.entity ? "selected" : ""}
          >
            ${this._escapeHtml(name)}
            (${this._escapeHtml(id)})
          </option>
        `;
      })
      .join("");

    this.innerHTML = `
      <style>
        .editor {
          display: grid;
          gap: 16px;
        }

        label {
          display: grid;
          gap: 6px;
        }

        input,
        select {
          box-sizing: border-box;
          width: 100%;
          padding: 9px;
        }

        .toggle {
          display: flex;
          align-items: center;
          gap: 9px;
        }

        .toggle input {
          width: auto;
        }

        .help {
          color: var(--secondary-text-color);
          font-size: 12px;
          line-height: 1.4;
        }
      </style>

      <div class="editor">
        <label>
          ${this._t("editor.entity")}
          <select id="entity">
            <option value="">${this._t("editor.select_entity")}</option>
            ${options}
          </select>
        </label>

        <label>
          ${this._t("editor.name")}
          <input
            id="name"
            type="text"
            value="${this._escapeHtml(this._config.name || "")}"
            placeholder="SPC FlexC"
          >
        </label>

        <label class="toggle">
          <input
            id="show_controls"
            type="checkbox"
            ${this._config.show_controls !== false ? "checked" : ""}
          >
          ${this._t("editor.show_controls")}
        </label>

        <label class="toggle">
          <input
            id="confirm_actions"
            type="checkbox"
            ${this._config.confirm_actions !== false ? "checked" : ""}
          >
          ${this._t("editor.confirm_actions")}
        </label>

        <div class="help">
          ${this._t("editor.help")}
        </div>
      </div>
    `;

    this.querySelectorAll("input, select").forEach((element) => {
      element.addEventListener("change", () => this._changed());
      element.addEventListener("input", () => this._changed());
    });
  }
}

if (!customElements.get("spc-flexc-card")) {
  customElements.define("spc-flexc-card", SpcFlexCCard);
}

if (!customElements.get("spc-flexc-card-editor")) {
  customElements.define("spc-flexc-card-editor", SpcFlexCCardEditor);
}

window.customCards = window.customCards || [];

if (!window.customCards.some((card) => card.type === "spc-flexc-card")) {
  window.customCards.push({
    type: "spc-flexc-card",
    name: "SPC FlexC Card",
    description: "",
    preview: true,
    documentationURL:
      "https://github.com/minimicro34/ha-spc-flexc-card",
  });
}

console.info(
  `%c SPC FLEXC CARD %c ${CARD_VERSION} `,
  "color:white;background:#1565c0;font-weight:700;",
  "color:#1565c0;background:white;font-weight:700;"
);

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

/* SPC FlexC Card v1.0.5 translations. */

const SPC_FLEXC_CARD_TRANSLATIONS = {
  fr: {
    "card.description": "Carte de contrôle visuelle pour l’intégration Home Assistant SPC FlexC.",
    "card.entity_not_found": "Entité introuvable : {entity}",
    "tab.general": "Général",
    "tab.areas": "Secteurs",
    "tab.detectors": "Détecteurs",
    "tab.doors": "Portes",
    "tab.outputs": "Sorties",
    "tab.system": "Système",
    "state.disarmed": "Désarmée",
    "state.disarmed_masc": "Désarmé",
    "state.armed": "Armée",
    "state.armed_masc": "Armé",
    "state.part_a": "Partiel A",
    "state.part_b": "Partiel B",
    "state.partial": "Partiel",
    "state.alarm": "ALARME",
    "state.arming": "Armement…",
    "state.disarming": "Désarmement…",
    "state.pending": "Temporisation",
    "state.unavailable": "Indisponible",
    "state.unknown": "État inconnu",
    "state.mixed": "Armement mixte",
    "state.unknown_short": "Inconnu",
    "state.normal": "Normal",
    "state.on": "Activé",
    "state.off": "Désactivé",
    "state.connected": "Connectée",
    "state.disconnected": "Déconnectée",
    "state.ok": "OK",
    "state.inactive": "Inactif",
    "state.fault": "Défaut",
    "state.inhibited": "Inhibé",
    "state.not_inhibited": "Non inhibé",
    "state.isolated": "Isolé",
    "state.not_isolated": "Non isolé",
    "zone.motion": "Mouvement",
    "zone.rest": "Repos",
    "zone.open": "Ouvert",
    "zone.closed": "Fermé",
    "zone.smoke": "Fumée détectée",
    "zone.heat": "Chaleur détectée",
    "zone.active": "Actif",
    "zone.tamper": "AUTOPROTECTION",
    "zone.inhibited": "Inhibé",
    "zone.none": "Aucune zone SPC découverte.",
    "zone.name": "Zone {id}",
    "area.none": "Aucun secteur SPC disponible.",
    "area.name": "Secteur {id}",
    "area.last_set": "Dernier armement",
    "area.last_unset": "Dernier désarmement",
    "area.tamper": "Autoprotection",
    "door.none": "Aucune porte SPC découverte.",
    "door.name": "Porte {id}",
    "door.fallback_name": "Porte SPC",
    "door.status": "État",
    "door.mode": "Mode",
    "door.dps": "DPS",
    "door.drs": "DRS",
    "door.access_forbidden": "Accès interdit",
    "door.free_access": "Accès libre",
    "door.unknown_area": "Association secteur inconnue",
    "door.supervision_note": "Supervision FlexC uniquement. Les commandes de mode de porte ne sont pas présentées comme une commande physique de serrure.",
    "door.raw_note": "État et Mode sont affichés tels que fournis par SPC tant que leur signification n’est pas validée sur matériel réel.",
    "output.none": "Aucune sortie SPC (Mapping Gate) découverte.",
    "output.name": "Sortie {id}",
    "output.fallback_name": "Sortie SPC",
    "output.mapping_gate": "Mapping Gate",
    "group.detectors": "Détecteurs",
    "group.tampers": "Autoprotections",
    "group.expand_all": "Tout développer",
    "group.collapse_all": "Tout réduire",
    "group.rest": "Au repos",
    "group.detector_count.one": "{count} détecteur",
    "group.detector_count.other": "{count} détecteurs",
    "group.area_count.one": "{count} secteur",
    "group.area_count.other": "{count} secteurs",
    "group.tamper_count.one": "{count} autoprotection",
    "group.tamper_count.other": "{count} autoprotections",
    "group.active_count.one": "{count} Actif",
    "group.active_count.other": "{count} Actifs",
    "group.inhibited_count.one": "{count} Inhibé",
    "group.inhibited_count.other": "{count} Inhibés",
    "group.fault_count.one": "{count} défaut",
    "group.fault_count.other": "{count} défauts",
    "group.unavailable_count.one": "{count} indisponible",
    "group.unavailable_count.other": "{count} indisponibles",
    "group.in_fault": "{count} en défaut",
    "group.no_area": "Aucun secteur",
    "group.no_detector": "Aucun détecteur",
    "system.health": "État et défauts",
    "system.connection": "Connexion FlexC",
    "system.state_unknown": "État non déterminé",
    "system.entity_missing": "Entité non exposée",
    "system.engineer_active": "Mode ingénieur actif",
    "system.engineer_detail": "L’état est remonté en temps réel par la centrale.",
    "system.active_faults": "Défauts actifs",
    "system.no_fault": "Aucun défaut actif",
    "system.faults_unknown": "Défauts système non déterminés : métadonnées indisponibles.",
    "system.card": "Carte SPC FlexC",
    "system.panel": "Centrale",
    "system.manufacturer": "Fabricant",
    "system.model": "Modèle",
    "system.firmware": "Firmware",
    "system.hardware": "Matériel",
    "system.serial": "N° de série",
    "system.power": "Alimentation",
    "system.ac_frequency": "Fréquence secteur",
    "system.battery_voltage": "Tension batterie",
    "system.aux_voltage": "Tension auxiliaire",
    "system.aux_current": "Courant auxiliaire",
    "system.communication": "Communication FlexC",
    "system.state": "État",
    "system.ats_used": "ATS utilisé",
    "system.last_tx": "Dernière transmission réussie",
    "system.xbus": "X-BUS",
    "system.xbus_id": "ID X-BUS",
    "system.sia_address": "Adresse SIA",
    "system.tamper": "Autoprotection",
    "system.tamper_isolation": "Isolement autoprotection",
    "system.rf": "RF",
    "system.modem": "Modem",
    "action.disarm": "Désarmer",
    "action.full_arm": "Armement total",
    "action.arm": "Armer",
    "action.activate": "Activer",
    "action.deactivate": "Désactiver",
    "action.execute": "Exécuter la commande",
    "action.door_momentary": "Ouverture momentanée",
    "action.door_permanent": "Ouverture permanente",
    "action.door_normal": "Retour au mode normal",
    "action.door_lock": "Verrouiller",
    "action.restore": "Restaurer",
    "confirm.restore_zone": "Restaurer la zone {name} ?",
    "confirm.generic": "Exécuter l'action sur {name} ?",
    "confirm.disarm": "Désarmer {name} ?",
    "confirm.full_arm": "Armer complètement {name} ?",
    "confirm.part_set": "Activer {action} sur {name} ?",
    "confirm.mapping_gate": "{action} — {name} ?",
    "confirm.door": "{action} — {name} ?",
    "editor.entity": "Entité d'alarme",
    "editor.select_entity": "Sélectionner une entité",
    "editor.name": "Nom de la carte",
    "editor.show_controls": "Afficher les commandes d'alarme",
    "editor.confirm_actions": "Confirmer les actions d'armement/désarmement",
    "editor.help": "Les secteurs sont récupérés depuis l'entité d'alarme. Les détecteurs SPC sont découverts automatiquement parmi les binary_sensor possédant les attributs zone_id, area_id et spc_zone_type. Les diagnostics et informations techniques sont rattachés à la même intégration via les registres Home Assistant quand ceux-ci sont disponibles.",
  },
  en: {
    "card.description": "Visual alarm control card for the SPC FlexC Home Assistant integration.",
    "card.entity_not_found": "Entity not found: {entity}",
    "tab.general": "General",
    "tab.areas": "Areas",
    "tab.detectors": "Detectors",
    "tab.doors": "Doors",
    "tab.outputs": "Outputs",
    "tab.system": "System",
    "state.disarmed": "Disarmed",
    "state.disarmed_masc": "Disarmed",
    "state.armed": "Armed",
    "state.armed_masc": "Armed",
    "state.part_a": "Part Set A",
    "state.part_b": "Part Set B",
    "state.partial": "Part set",
    "state.alarm": "ALARM",
    "state.arming": "Arming…",
    "state.disarming": "Disarming…",
    "state.pending": "Pending",
    "state.unavailable": "Unavailable",
    "state.unknown": "Unknown state",
    "state.mixed": "Mixed arming",
    "state.unknown_short": "Unknown",
    "state.normal": "Normal",
    "state.on": "On",
    "state.off": "Off",
    "state.connected": "Connected",
    "state.disconnected": "Disconnected",
    "state.ok": "OK",
    "state.inactive": "Inactive",
    "state.fault": "Fault",
    "state.inhibited": "Inhibited",
    "state.not_inhibited": "Not inhibited",
    "state.isolated": "Isolated",
    "state.not_isolated": "Not isolated",
    "zone.motion": "Motion",
    "zone.rest": "Idle",
    "zone.open": "Open",
    "zone.closed": "Closed",
    "zone.smoke": "Smoke detected",
    "zone.heat": "Heat detected",
    "zone.active": "Active",
    "zone.tamper": "TAMPER",
    "zone.inhibited": "Inhibited",
    "zone.none": "No SPC zone discovered.",
    "zone.name": "Zone {id}",
    "area.none": "No SPC area available.",
    "area.name": "Area {id}",
    "area.last_set": "Last arm",
    "area.last_unset": "Last disarm",
    "area.tamper": "Tamper",
    "door.none": "No SPC door discovered.",
    "door.name": "Door {id}",
    "door.fallback_name": "SPC door",
    "door.status": "Status",
    "door.mode": "Mode",
    "door.dps": "DPS",
    "door.drs": "DRS",
    "door.access_forbidden": "Access forbidden",
    "door.free_access": "Free access",
    "door.unknown_area": "Unknown area association",
    "door.supervision_note": "FlexC supervision only. Door mode commands are not presented as physical lock commands.",
    "door.raw_note": "Status and Mode are displayed as provided by SPC until their meaning is validated on real hardware.",
    "output.none": "No SPC output (Mapping Gate) discovered.",
    "output.name": "Output {id}",
    "output.fallback_name": "SPC output",
    "output.mapping_gate": "Mapping Gate",
    "group.detectors": "Detectors",
    "group.tampers": "Tampers",
    "group.expand_all": "Expand all",
    "group.collapse_all": "Collapse all",
    "group.rest": "Idle",
    "group.detector_count.one": "{count} detector",
    "group.detector_count.other": "{count} detectors",
    "group.area_count.one": "{count} area",
    "group.area_count.other": "{count} areas",
    "group.tamper_count.one": "{count} tamper",
    "group.tamper_count.other": "{count} tampers",
    "group.active_count.one": "{count} Active",
    "group.active_count.other": "{count} Active",
    "group.inhibited_count.one": "{count} Inhibited",
    "group.inhibited_count.other": "{count} Inhibited",
    "group.fault_count.one": "{count} fault",
    "group.fault_count.other": "{count} faults",
    "group.unavailable_count.one": "{count} unavailable",
    "group.unavailable_count.other": "{count} unavailable",
    "group.in_fault": "{count} in fault",
    "group.no_area": "No area",
    "group.no_detector": "No detector",
    "system.health": "State and faults",
    "system.connection": "FlexC connection",
    "system.state_unknown": "State unavailable",
    "system.entity_missing": "Entity not exposed",
    "system.engineer_active": "Engineer mode active",
    "system.engineer_detail": "The state is reported in real time by the panel.",
    "system.active_faults": "Active faults",
    "system.no_fault": "No active fault",
    "system.faults_unknown": "System faults unavailable: metadata is not available.",
    "system.card": "SPC FlexC Card",
    "system.panel": "Panel",
    "system.manufacturer": "Manufacturer",
    "system.model": "Model",
    "system.firmware": "Firmware",
    "system.hardware": "Hardware",
    "system.serial": "Serial number",
    "system.power": "Power",
    "system.ac_frequency": "AC frequency",
    "system.battery_voltage": "Battery voltage",
    "system.aux_voltage": "Auxiliary voltage",
    "system.aux_current": "Auxiliary current",
    "system.communication": "FlexC communication",
    "system.state": "State",
    "system.ats_used": "ATS used",
    "system.last_tx": "Last successful transmission",
    "system.xbus": "X-BUS",
    "system.xbus_id": "X-BUS ID",
    "system.sia_address": "SIA address",
    "system.tamper": "Tamper",
    "system.tamper_isolation": "Tamper isolation",
    "system.rf": "RF",
    "system.modem": "Modem",
    "action.disarm": "Disarm",
    "action.full_arm": "Full set",
    "action.arm": "Arm",
    "action.activate": "Activate",
    "action.deactivate": "Deactivate",
    "action.execute": "Run command",
    "action.door_momentary": "Open momentarily",
    "action.door_permanent": "Open permanently",
    "action.door_normal": "Return to normal mode",
    "action.door_lock": "Lock",
    "action.restore": "Restore",
    "confirm.restore_zone": "Restore zone {name}?",
    "confirm.generic": "Run the action on {name}?",
    "confirm.disarm": "Disarm {name}?",
    "confirm.full_arm": "Full set {name}?",
    "confirm.part_set": "Activate {action} on {name}?",
    "confirm.mapping_gate": "{action} — {name}?",
    "confirm.door": "{action} — {name}?",
    "editor.entity": "Alarm entity",
    "editor.select_entity": "Select an entity",
    "editor.name": "Card name",
    "editor.show_controls": "Show alarm controls",
    "editor.confirm_actions": "Confirm arm/disarm actions",
    "editor.help": "Areas are read from the alarm entity. SPC detectors are discovered automatically from binary_sensor entities exposing zone_id, area_id and spc_zone_type. Diagnostics and technical information are associated with the same integration through the Home Assistant registries when available.",
  },
};

function spcFlexCFormatTranslation(template, variables = {}) {
  let result = String(template ?? "");

  for (const [name, value] of Object.entries(variables)) {
    result = result.split(`{${name}}`).join(String(value));
  }

  return result;
}

function spcFlexCLanguage(hass) {
  const language = String(
    hass?.locale?.language || navigator.language || "en"
  ).toLowerCase();

  return language.startsWith("fr") ? "fr" : "en";
}

function spcFlexCTranslate(hass, key, variables = {}, fallback = key) {
  const language = spcFlexCLanguage(hass);
  const template =
    SPC_FLEXC_CARD_TRANSLATIONS[language]?.[key] ??
    SPC_FLEXC_CARD_TRANSLATIONS.en[key] ??
    fallback;

  return spcFlexCFormatTranslation(template, variables);
}

const spcFlexCCardRegistration = window.customCards?.find(
  (card) => card.type === "spc-flexc-card"
);

if (spcFlexCCardRegistration) {
  spcFlexCCardRegistration.description = spcFlexCTranslate(
    null,
    "card.description"
  );
}

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

/* SPC FlexC Card communication diagnostics. */

const spcFlexCCommunicationBaseStyles = SpcFlexCCard.prototype._styles;
const spcFlexCCommunicationBaseRender = SpcFlexCCard.prototype._render;

SpcFlexCCard.prototype._styles = function () {
  return `${spcFlexCCommunicationBaseStyles.call(this)}
    <style>
      .atp-card {
        overflow: hidden;
      }

      .atp-card > summary {
        list-style: none;
      }

      .atp-card > summary::-webkit-details-marker {
        display: none;
      }

      .atp-title {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        cursor: pointer;
        user-select: none;
      }

      .atp-title-main {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }

      .atp-title-main::before {
        content: "▸";
        color: var(--secondary-text-color);
        font-size: 12px;
        line-height: 1;
        transition: transform 120ms ease;
      }

      .atp-card[open] .atp-title-main::before {
        transform: rotate(90deg);
      }

      .atp-card-body {
        padding-top: 4px;
      }
    </style>`;
};

SpcFlexCCard.prototype._renderFlexcCommunication = function () {
  const atsList = this._getFlexcCommunication();
  if (!atsList.length) return "";

  return `
    <div class="technical-section">
      <div class="technical-section-title">${this._t("system.communication")}</div>
      <div class="ats-list">
        ${atsList
          .map((ats) => {
            const atsLabel = ats.ungrouped
              ? ats.name
              : `ATS ${ats.id ?? "?"}${
                  ats.name ? ` — ${ats.name}` : ""
                }`;

            return `
              <div class="ats-card">
                <div class="ats-title">${this._escapeHtml(atsLabel)}</div>
                ${ats.atps.length
                  ? `<div class="atp-list">
                      ${ats.atps
                        .map((atp) => {
                          const atpLabel = `ATP ${atp.displayId ?? "?"}${
                            atp.name ? ` — ${atp.name}` : ""
                          }`;
                          const stateInfo = this._atpStateLabel(atp);
                          const formattedTx = this._formatDateTime(
                            atp.lastTxOkTimestamp
                          );
                          const atpKey = `${ats.id ?? "ungrouped"}:${atp.id ?? atp.displayId ?? "unknown"}`;

                          return `
                            <details class="atp-card" data-atp-key="${this._escapeHtml(atpKey)}">
                              <summary class="atp-title">
                                <span class="atp-title-main">${this._escapeHtml(atpLabel)}</span>
                                ${stateInfo
                                  ? `<span class="${stateInfo.className}">${this._escapeHtml(stateInfo.label)}</span>`
                                  : ""}
                              </summary>
                              <div class="atp-card-body">
                                ${stateInfo
                                  ? this._technicalLine(
                                      this._t("system.state"),
                                      stateInfo.label,
                                      stateInfo.className
                                    )
                                  : ""}
                                ${ats.ungrouped
                                  ? ""
                                  : this._technicalLine(
                                      this._t("system.ats_used"),
                                      atsLabel
                                    )}
                                ${this._technicalLine(
                                  this._t("system.last_tx"),
                                  formattedTx
                                )}
                              </div>
                            </details>
                          `;
                        })
                        .join("")}
                    </div>`
                  : ""}
              </div>
            `;
          })
          .join("")}
      </div>
    </div>
  `;
};

SpcFlexCCard.prototype._render = function () {
  const openAtps = new Set(
    Array.from(this.querySelectorAll("details.atp-card[open][data-atp-key]"))
      .map((details) => details.dataset.atpKey)
      .filter(Boolean)
  );

  spcFlexCCommunicationBaseRender.call(this);

  if (!openAtps.size) {
    return;
  }

  for (const details of this.querySelectorAll("details.atp-card[data-atp-key]")) {
    if (openAtps.has(details.dataset.atpKey)) {
      details.open = true;
    }
  }
};

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

/* SPC FlexC Card container-responsive layout. */

const spcFlexCResponsiveBaseStyles = SpcFlexCCard.prototype._styles;
const spcFlexCResponsiveBaseGridOptions = SpcFlexCCard.prototype.getGridOptions;
const spcFlexCResponsiveBaseTechnicalSystem = SpcFlexCCard.prototype._renderTechnicalSystem;

SpcFlexCCard.prototype.getGridOptions = function () {
  const baseOptions = spcFlexCResponsiveBaseGridOptions
    ? spcFlexCResponsiveBaseGridOptions.call(this)
    : {};

  return {
    ...baseOptions,
    columns: "full",
  };
};

SpcFlexCCard.prototype._renderTechnicalSystem = function () {
  const html = spcFlexCResponsiveBaseTechnicalSystem.call(this);

  if (!html || typeof DOMParser === "undefined") {
    return html;
  }

  const documentNode = new DOMParser().parseFromString(
    `<body>${html}</body>`,
    "text/html"
  );
  const root = documentNode.querySelector(".technical-system-view");

  if (!root) {
    return html;
  }

  const columns = [[], [], []];
  const communicationTitle = this._t("system.communication");
  const xbusTitle = this._t("system.xbus");
  const rfTitle = this._t("system.rf");
  const modemTitle = this._t("system.modem");

  for (const section of Array.from(root.children)) {
    const title = section
      .querySelector(".technical-section-title")
      ?.textContent?.trim();

    if (title === xbusTitle) {
      columns[1].push(section.outerHTML);
    } else if (title === communicationTitle) {
      columns[2].push(section.outerHTML);
    } else if (title === rfTitle || title === modemTitle) {
      columns[0].push(section.outerHTML);
    } else {
      columns[0].push(section.outerHTML);
    }
  }

  return `
    <div class="technical-system-view technical-system-columns">
      <div class="technical-system-column technical-system-column-main">
        ${columns[0].join("")}
      </div>
      <div class="technical-system-column technical-system-column-xbus">
        ${columns[1].join("")}
      </div>
      <div class="technical-system-column technical-system-column-communication">
        ${columns[2].join("")}
      </div>
    </div>
  `;
};

SpcFlexCCard.prototype._styles = function () {
  return `${spcFlexCResponsiveBaseStyles.call(this)}
    <style>
      .card {
        container-type: inline-size;
        container-name: spc-flexc-card;
      }

      .area-list,
      .door-list,
      .output-list,
      .technical-system-view {
        grid-template-columns: 1fr;
      }

      .technical-system-column {
        display: grid;
        gap: 18px;
        align-content: start;
        min-width: 0;
      }

      .technical-row {
        grid-template-columns: 1fr;
        gap: 2px;
      }

      .technical-value {
        text-align: left;
      }

      .xbus-card,
      .ats-card,
      .atp-card,
      .door-card,
      .output-row,
      .area-card {
        min-width: 0;
      }

      @container spc-flexc-card (min-width: 840px) {
        .area-list,
        .door-list,
        .output-list,
        .technical-system-view {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .technical-row {
          grid-template-columns: minmax(130px, 0.7fr) minmax(0, 1.3fr);
          gap: 14px;
        }

        .technical-value {
          text-align: right;
        }
      }
    </style>`;
};

/* SPC FlexC Card render scheduler. */

const spcFlexCImmediateRender = SpcFlexCCard.prototype._render;
const spcFlexCBaseDisconnectedCallback =
  SpcFlexCCard.prototype.disconnectedCallback;

SpcFlexCCard.prototype._showCardVersion = function () {
  if (this.querySelector(".spc-card-version")) {
    return;
  }

  const panelSection =
    this.querySelector('[data-technical-section="panel"]') ||
    Array.from(this.querySelectorAll(".technical-section")).find(
      (section) =>
        section.querySelector(".technical-section-title")?.textContent.trim() ===
        this._t("system.panel")
    );

  if (!panelSection) {
    return;
  }

  const versionRow = document.createElement("div");
  versionRow.className = "technical-row spc-card-version";
  versionRow.innerHTML = `
    <div class="technical-label">${this._escapeHtml(this._t("system.card"))}</div>
    <div class="technical-value">${this._escapeHtml(CARD_VERSION)}</div>
  `;

  panelSection
    .querySelector(".technical-section-title")
    ?.insertAdjacentElement("afterend", versionRow);
};

SpcFlexCCard.prototype._captureScrollPositions = function () {
  const positions = [];
  const seen = new Set();
  let node = this;

  while (node) {
    const parent = node.parentElement || node.getRootNode?.()?.host || null;
    if (!parent || seen.has(parent)) {
      break;
    }

    seen.add(parent);

    if (
      parent.scrollHeight > parent.clientHeight ||
      parent.scrollWidth > parent.clientWidth
    ) {
      positions.push({
        element: parent,
        top: parent.scrollTop,
        left: parent.scrollLeft,
      });
    }

    node = parent;
  }

  const scrollingElement = document.scrollingElement;
  if (scrollingElement && !seen.has(scrollingElement)) {
    positions.push({
      element: scrollingElement,
      top: scrollingElement.scrollTop,
      left: scrollingElement.scrollLeft,
    });
  }

  return positions;
};

SpcFlexCCard.prototype._restoreScrollPositions = function (positions) {
  for (const position of positions || []) {
    const { element, top, left } = position;
    if (!element?.isConnected) {
      continue;
    }

    if (element.scrollTop !== top) {
      element.scrollTop = top;
    }
    if (element.scrollLeft !== left) {
      element.scrollLeft = left;
    }
  }
};

SpcFlexCCard.prototype._render = function () {
  if (this._spcRenderFrame != null) {
    return;
  }

  const render = () => {
    this._spcRenderFrame = null;
    this._spcRenderUsesAnimationFrame = false;

    const scrollPositions = this._captureScrollPositions();

    // The base renderer now preserves the connected tab strip on routine updates.
    const previousHaCard = this.querySelector(":scope > ha-card");
    // Preserve scroll position when the tab strip must actually be replaced.
    const previousTabsScrollLeft = previousHaCard?.querySelector(".tabs")?.scrollLeft ?? 0;
    // The legacy renderer replaces the complete card DOM with innerHTML on
    // every HA update. Keep the host at its current rendered height while the
    // replacement custom elements are attached/upgraded. Without this guard,
    // the dashboard briefly reflows and produces a visible vertical jump on
    // every tab, even when the user's scrollTop is restored afterwards.
    const previousMinHeight = this.style.minHeight;
    const renderedHeight = this.getBoundingClientRect().height;
    if (renderedHeight > 0) {
      this.style.minHeight = `${renderedHeight}px`;
    }

    spcFlexCImmediateRender.call(this);

    // Restore the horizontal tab position after the old shell is reattached
    // (or after the new shell replaces it on a tab change).
    const restoreTabsScroll = () => {
      const tabs = this.querySelector(":scope > ha-card .tabs");
      if (tabs && tabs.scrollLeft !== previousTabsScrollLeft) {
        tabs.scrollLeft = previousTabsScrollLeft;
      }
    };
    restoreTabsScroll();
    this._showCardVersion();
    this._restoreScrollPositions(scrollPositions);

    if (this._spcScrollRestoreFrame != null &&
        typeof window.cancelAnimationFrame === "function") {
      window.cancelAnimationFrame(this._spcScrollRestoreFrame);
    }

    this._spcScrollRestoreFrame = window.requestAnimationFrame?.(() => {
      this._spcScrollRestoreFrame = null;
      restoreTabsScroll();
      this._restoreScrollPositions(scrollPositions);

      // Release the temporary layout lock only after the replacement DOM has
      // had a frame to settle. Restore scroll once more after releasing it in
      // case the new content legitimately has a different height.
      this.style.minHeight = previousMinHeight;
      this._spcLayoutReleaseFrame = window.requestAnimationFrame?.(() => {
        this._spcLayoutReleaseFrame = null;
        this._restoreScrollPositions(scrollPositions);
      }) ?? null;
    }) ?? null;
  };

  if (typeof window.requestAnimationFrame === "function") {
    this._spcRenderUsesAnimationFrame = true;
    this._spcRenderFrame = window.requestAnimationFrame(render);
  } else {
    this._spcRenderUsesAnimationFrame = false;
    this._spcRenderFrame = window.setTimeout(render, 0);
  }
};

SpcFlexCCard.prototype.disconnectedCallback = function () {
  if (this._spcRenderFrame != null) {
    if (
      this._spcRenderUsesAnimationFrame &&
      typeof window.cancelAnimationFrame === "function"
    ) {
      window.cancelAnimationFrame(this._spcRenderFrame);
    } else {
      window.clearTimeout(this._spcRenderFrame);
    }

    this._spcRenderFrame = null;
    this._spcRenderUsesAnimationFrame = false;
  }

  if (
    this._spcScrollRestoreFrame != null &&
    typeof window.cancelAnimationFrame === "function"
  ) {
    window.cancelAnimationFrame(this._spcScrollRestoreFrame);
    this._spcScrollRestoreFrame = null;
  }

  if (
    this._spcLayoutReleaseFrame != null &&
    typeof window.cancelAnimationFrame === "function"
  ) {
    window.cancelAnimationFrame(this._spcLayoutReleaseFrame);
    this._spcLayoutReleaseFrame = null;
  }

  this.style.minHeight = "";
  spcFlexCBaseDisconnectedCallback.call(this);
};
