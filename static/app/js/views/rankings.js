/*
 * Rankings: the leading causes or risk factors for one population and year,
 * with an optional projection of where each would stand.
 */

import { bestRankOption, cascade, DIM_LABEL, HORIZONS, optionText, RANK_DIMS, rankParams } from "../catalogue.js";
import { drawRank } from "../charts.js";
import { describe, esc, fmt } from "../format.js";
import { h, icon, pillSelect, segmented } from "../ui.js";

const LIMIT = 15;
let s = null;

const defaultSelection = (app, type) => {
  const best = bestRankOption(app.rankOptions, type, type === "risks" ? /DALY/i : null);
  return best ? Object.fromEntries(RANK_DIMS.map((dim) => [dim, best[dim]])) : {};
};

function remember() {
  if (s) s.app.memory.rankings = { type: s.type, sel: s.sel, forecast: s.forecast, horizon: s.horizon, table: s.table };
}

function buildLayout() {
  s.filters = h("div", { class: "filters", role: "group", "aria-label": "Choose a ranking" });
  s.actions = h("div", { class: "toolbar-actions" });
  s.title = h("h2", { class: "card-title" }, "Loading…");
  s.sub = h("p", { class: "card-sub" });
  s.canvas = h("canvas", { role: "img", "aria-label": "Ranking chart" });
  s.box = h("div", { class: "chart-box" }, s.canvas);
  s.tableWrap = h("div", { class: "table-wrap", hidden: true });
  s.foot = h("div", { class: "card-foot" });
  s.side = h("aside", { class: "side", "aria-label": "Top of the ranking" });
  s.el.replaceChildren(
    h(
      "div",
      { class: "analysis" },
      h("div", { class: "toolbar" }, s.filters, s.actions),
      h("section", { class: "card chart-card" }, h("div", { class: "card-head" }, h("div", {}, s.title, s.sub)), s.box, s.tableWrap, s.foot),
      s.side,
    ),
  );
}

function renderToolbar(pool) {
  const types = segmented(
    [
      { value: "causes", label: "Causes" },
      { value: "risks", label: "Risk factors" },
    ],
    s.type,
    (type) => {
      if (type === s.type) return;
      s.type = type;
      s.sel = defaultSelection(s.app, type);
      load();
    },
    "Rank causes or risk factors",
  );
  let pills = [];
  if (pool.length) {
    const { selection, options, match } = cascade(pool, RANK_DIMS, s.sel);
    s.sel = selection;
    s.option = match;
    pills = RANK_DIMS.filter((dim) => !((dim === "release" || dim === "location") && options[dim].length <= 1)).map((dim) =>
      pillSelect({
        label: DIM_LABEL[dim],
        values: options[dim],
        value: selection[dim],
        text: (value) => optionText(dim, value),
        wide: dim === "measure",
        onChange: (value) => {
          s.sel = { ...s.sel, [dim]: dim === "year" ? Number(value) : value };
          load();
        },
      }),
    );
  }
  s.filters.replaceChildren(types, ...pills);

  const toggle = h(
    "button",
    { type: "button", class: "btn toggle", "aria-pressed": String(s.forecast), title: "Project each item from its own history", onClick: () => { s.forecast = !s.forecast; load(); } },
    icon("forecast"),
    "Forecast",
  );
  const horizons = s.forecast
    ? segmented(HORIZONS.map((years) => ({ value: years, label: `${years}y` })), s.horizon, (years) => { s.horizon = years; load(); }, "Forecast horizon")
    : null;
  const table = h(
    "button",
    {
      type: "button",
      class: "icon-btn",
      title: s.table ? "Show chart" : "Show table",
      "aria-label": s.table ? "Show chart" : "Show table",
      onClick: () => { s.table = !s.table; renderToolbar(pool); showMode(); remember(); },
    },
    icon(s.table ? "chart" : "table"),
  );
  s.actions.replaceChildren(...[toggle, horizons, table].filter(Boolean));
}

function showMode() {
  s.box.hidden = s.table;
  s.tableWrap.hidden = !s.table;
}

async function load() {
  const mine = ++s.token;
  const pool = s.app.rankOptions.filter((option) => option.type === s.type);
  renderToolbar(pool);
  if (!pool.length) {
    s.chart?.destroy();
    s.chart = null;
    s.data = null;
    s.title.textContent = s.type === "causes" ? "Leading causes" : "Leading risk factors";
    s.sub.textContent = "Nothing in the loaded dataset can be ranked this way.";
    s.side.replaceChildren();
    s.foot.replaceChildren();
    return;
  }
  s.app.replaceParams({ type: s.type, ...s.sel, forecast: s.forecast ? s.horizon : undefined });
  remember();
  s.box.classList.add("loading");
  try {
    const data = await s.app.source.ranked(rankParams(s.option, s.forecast ? { forecast_years: s.horizon } : {}));
    if (!s || mine !== s.token) return;
    s.data = data;
    draw();
  } catch (error) {
    if (s && mine === s.token) s.app.fail(error);
  } finally {
    s?.box.classList.remove("loading");
  }
}

function renderTable(d) {
  const k = d.display_scale;
  const projected = Object.fromEntries((d.forecast_items || []).map((item) => [item.label, item]));
  const hasForecast = Boolean(d.forecast_items?.length);
  const rows = d.items.map(
    (item, i) =>
      `<tr><td>${i + 1}</td><td>${esc(item.label)}</td><td class="num">${fmt(item.value * k)}</td>` +
      `<td class="num">${item.lower === null ? "–" : `${fmt(item.lower * k)}–${fmt(item.upper * k)}`}</td>` +
      (hasForecast ? `<td class="num">${projected[item.label] ? fmt(projected[item.label].value * k) : "–"}</td>` : "") +
      "</tr>",
  );
  s.tableWrap.innerHTML =
    `<table><thead><tr><th>#</th><th>${d.type === "causes" ? "Cause" : "Risk factor"}</th>` +
    `<th class="num">${d.year} (${esc(d.unit)})</th><th class="num">95% UI</th>` +
    (hasForecast ? `<th class="num">Forecast ${d.forecast_year}</th>` : "") +
    `</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function renderSide(d) {
  const k = d.display_scale;
  const causes = d.type === "causes";
  const podium = h(
    "section",
    { class: "card podium", style: { "--accent": causes ? "var(--series-1)" : "var(--series-2)" } },
    h("h3", {}, `Top three · ${d.year}`),
    d.items.slice(0, 3).map((item, i) =>
      h(
        "div",
        { class: "podium-item" },
        h("span", { class: "podium-rank" }, String(i + 1)),
        h("span", { class: "podium-label", title: item.label }, item.label),
        h(
          "span",
          { class: "podium-value" },
          `${fmt(item.value * k)} ${d.unit}${item.lower !== null ? ` · UI ${fmt(item.lower * k)}–${fmt(item.upper * k)}` : ""}`,
        ),
      ),
    ),
  );
  const cards = [podium];
  const leader = d.forecast_items?.[0];
  if (leader) {
    cards.push(
      h(
        "section",
        { class: "forecast-card" },
        h("div", { class: "stat-label" }, icon("forecast"), `Projected leader · ${d.forecast_year}`),
        h("div", { class: "stat-value", style: { "font-size": "20px" } }, leader.label),
        h("div", { class: "stat-sub" }, `${fmt(leader.value * k)} ${d.unit} · 95% PI ${fmt(leader.lower * k)}–${fmt(leader.upper * k)}`),
        h("p", {}, d.forecast_info.note),
      ),
    );
  } else if (d.forecast_info) {
    cards.push(h("section", { class: "forecast-card" }, h("div", { class: "stat-label" }, icon("forecast"), "Projection"), h("p", {}, d.forecast_info.note)));
  }
  if (causes) {
    cards.push(
      h(
        "details",
        { class: "card caveat" },
        h("summary", {}, icon("info"), "About cause levels"),
        h(
          "p",
          {},
          "Every cause in the loaded dataset is ranked together. GBD causes are hierarchical, so a parent (for example “Mental disorders”) can appear alongside its own sub-causes (“Anxiety disorders”). Import a single cause level to compare like with like.",
        ),
      ),
    );
  }
  s.side.replaceChildren(...cards);
}

function draw() {
  const d = s.data;
  const causes = d.type === "causes";
  const heading = causes ? "Leading causes" : "Leading risk factors";
  s.app.setHeader("Rankings", `${heading} · ${d.location} · ${d.year}`);
  s.title.textContent = `${heading}, ${d.year}${d.forecast_items?.length ? ` → ${d.forecast_year}` : ""}`;
  s.sub.textContent = `Ranked by ${describe({ ...d, title: null })}`;
  s.chart?.destroy();
  s.chart = drawRank(s.canvas, d, { limit: LIMIT });
  renderTable(d);
  showMode();
  s.foot.replaceChildren(
    h("span", {}, `Unit: ${d.unit}. Source: IHME, ${d.release}.`),
    h("span", {}, d.items.length > LIMIT ? `Chart shows the top ${LIMIT} of ${d.items.length}; the table lists all.` : "Hover a bar for its uncertainty interval."),
  );
  renderSide(d);
}

export default {
  id: "rankings",
  label: "Rankings",
  icon: "rankings",

  async mount(el, app, params) {
    const memory = app.memory.rankings || {};
    const type = params.type === "causes" || params.type === "risks" ? params.type : memory.type || "causes";
    s = { app, el, token: 0, chart: null, data: null, type, forecast: Boolean(memory.forecast), horizon: memory.horizon || 5, table: Boolean(memory.table) };
    const pinned = Object.fromEntries(
      RANK_DIMS.filter((dim) => params[dim] !== undefined).map((dim) => [dim, dim === "year" ? Number(params[dim]) : params[dim]]),
    );
    const remembered = memory.type === type ? memory.sel : null;
    s.sel = Object.keys(pinned).length ? { ...defaultSelection(app, type), ...pinned } : remembered || defaultSelection(app, type);
    if (params.forecast !== undefined) {
      const years = Number(params.forecast);
      s.forecast = HORIZONS.includes(years);
      if (s.forecast) s.horizon = years;
    }
    app.setHeader("Rankings", "");
    buildLayout();
    await load();
  },

  unmount() {
    if (!s) return;
    remember();
    s.chart?.destroy();
    s = null;
  },

  redraw() {
    if (s?.data) draw();
  },
};
