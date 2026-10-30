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

/* Preserve expanded diagnostic sections across Home Assistant updates. */
const spcSystemDetailsRender = SpcFlexCCard.prototype._render;
SpcFlexCCard.prototype._render = function () {
  const open = new Set(Array.from(this.querySelectorAll("details.system-detail-card[open]"))
    .map((node) => node.dataset.systemDetailKey).filter(Boolean));
  spcSystemDetailsRender.call(this);
  this.querySelectorAll("details.system-detail-card").forEach((node) => {
    if (open.has(node.dataset.systemDetailKey)) node.open = true;
  });
};

const spcSystemDetailsStyles = SpcFlexCCard.prototype._styles;
SpcFlexCCard.prototype._styles = function () {
  return `${spcSystemDetailsStyles.call(this)}
    <style>
      .system-detail-card { border:1px solid var(--divider-color); border-radius:12px; padding:10px 12px; margin-top:8px; overflow:hidden; }
      .system-detail-card > summary { cursor:pointer; list-style:none; display:flex; align-items:center; gap:8px; font-weight:600; }
      .system-detail-card > summary::-webkit-details-marker { display:none; }
      .system-detail-card > summary::before { content:"▸"; color:var(--secondary-text-color); transition:transform 120ms ease; }
      .system-detail-card[open] > summary::before { transform:rotate(90deg); }
      .system-detail-body { padding-top:10px; }
    </style>`;
};
