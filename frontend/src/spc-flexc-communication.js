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
