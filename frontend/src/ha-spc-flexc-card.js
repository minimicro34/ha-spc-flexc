const CARD_VERSION = "1.0.5";

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
