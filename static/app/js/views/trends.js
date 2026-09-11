/*
 * Trends: one series at a time, chosen through cascading choices, drawn with
 * its uncertainty band and an optional exploratory forecast.
 */

import { cascade, DIM_LABEL, findSeries, HORIZONS, LIFE_EXPECTANCY, NONE, optionText, TREND_DIMS } from "../catalogue.js";
import { drawTrend, figureBlob } from "../charts.js";
import { describe, esc, fmt, fmtDate, signed, slug, span, trendCsv } from "../format.js";
import { downloadBlob, downloadUrl, h, icon, menu, pillSelect, segmented, toast } from "../ui.js";

const WIDE = new Set(["measure", "cause", "risk"]);
let s = null;

const selectionOf = (entry) => Object.fromEntries(TREND_DIMS.map((dim) => [dim, entry[dim] ?? NONE]));

function remember() {
  if (s) s.app.memory.trends = { sel: s.sel, range: s.range, forecast: s.forecast, horizon: s.horizon, table: s.table };
}

function buildLayout() {
  s.filters = h("div", { class: "filters", role: "group", "aria-label": "Choose a series" });
  s.actions = h("div", { class: "toolbar-actions" });
  s.title = h("h2", { class: "card-title" }, "Loading…");
  s.sub = h("p", { class: "card-sub" });
  s.legend = h("div", { class: "legend" });
  s.canvas = h("canvas", { role: "img", "aria-label": "Trend chart" });
  s.box = h("div", { class: "chart-box" }, s.canvas);
  s.tableWrap = h("div", { class: "table-wrap", hidden: true });
  s.foot = h("div", { class: "card-foot" });
  s.side = h("aside", { class: "side", "aria-label": "Key figures" });
  s.el.replaceChildren(
    h(
      "div",
      { class: "analysis" },
      h("div", { class: "toolbar" }, s.filters, s.actions),
      h("section", { class: "card chart-card" }, h("div", { class: "card-head" }, h("div", {}, s.title, s.sub), s.legend), s.box, s.tableWrap, s.foot),
      s.side,
    ),
  );
}

function renderFilters() {
  const { selection, options, match } = cascade(s.app.catalogue, TREND_DIMS, s.sel);
  s.sel = selection;
  s.entry = match;
  const years = match.years;
  let { from, to, custom } = s.range;
  if (!custom || !years.includes(from)) from = years[0];
  if (!custom || !years.includes(to)) to = years.at(-1);
  if (from > to) [from, to] = [to, from];
  s.range = { from, to, custom: Boolean(custom) && !(from === years[0] && to === years.at(-1)) };

  const pills = TREND_DIMS.filter((dim) => !((dim === "release" || dim === "location") && options[dim].length <= 1)).map((dim) =>
    pillSelect({
      label: DIM_LABEL[dim],
      values: options[dim],
      value: selection[dim],
      text: (value) => optionText(dim, value),
      wide: WIDE.has(dim),
      onChange: (value) => {
        s.sel = { ...s.sel, [dim]: value };
        load();
      },
    }),
  );
  if (s.app.source.capabilities.yearRange && years.length > 2) {
    const setRange = (edge, value) => {
      const next = { ...s.range, [edge]: Number(value), custom: true };
      if (next.from > next.to) next[edge === "from" ? "to" : "from"] = next[edge];
      s.range = next;
      load();
    };
    pills.push(
      pillSelect({ label: "From", values: years, value: from, onChange: (value) => setRange("from", value) }),
      pillSelect({ label: "To", values: years, value: to, onChange: (value) => setRange("to", value) }),
    );
  }
  s.filters.replaceChildren(...pills);
}

function renderActions() {
  const toggle = h(
    "button",
    {
      type: "button",
      class: "btn toggle",
      "aria-pressed": String(s.forecast),
      title: "Add an exploratory projection",
      onClick: () => {
        s.forecast = !s.forecast;
        load();
      },
    },
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
      onClick: () => {
        s.table = !s.table;
        renderActions();
        showMode();
        remember();
      },
    },
    icon(s.table ? "chart" : "table"),
  );
  const downloads = menu(
    [icon("download"), h("span", {}, "Download")],
    [
      { label: "CSV data", hint: "Values, intervals and every dimension", icon: "table", onSelect: () => download("csv") },
      { label: "PNG figure", hint: "With the GBD source and citation", icon: "chart", onSelect: () => download("png") },
      s.app.source.capabilities.pdf ? { label: "PDF figure", hint: "Vector figure for print", icon: "download", onSelect: () => download("pdf") } : null,
    ],
    { label: "Download" },
  );
  s.actions.replaceChildren(...[toggle, horizons, table, downloads].filter(Boolean));
}

function showMode() {
  s.box.hidden = s.table;
  s.tableWrap.hidden = !s.table;
}

async function load() {
  const mine = ++s.token;
  renderFilters();
  renderActions();
  const whole = s.range.from === s.entry.years[0] && s.range.to === s.entry.years.at(-1);
  const params = { series: s.entry.series_id };
  if (s.app.source.capabilities.yearRange && !whole) Object.assign(params, { year_from: s.range.from, year_to: s.range.to });
  if (s.forecast) params.forecast_years = s.horizon;
  s.params = params;
  s.app.replaceParams({ series: s.entry.series_id, forecast: s.forecast ? s.horizon : undefined });
  remember();
  s.box.classList.add("loading");
  try {
    const data = await s.app.source.trend(params);
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
  const cell = (value) => (value === null || value === undefined ? "–" : fmt(value * k));
  const rows = [
    ...d.series.map((p) => `<tr><td>${p.year}</td><td>Observed</td><td class="num">${cell(p.value)}</td><td class="num">${cell(p.lower)}</td><td class="num">${cell(p.upper)}</td></tr>`),
    ...(d.forecast || []).map((p) => `<tr class="projected"><td>${p.year}</td><td>Forecast</td><td class="num">${cell(p.value)}</td><td class="num">${cell(p.lower)}</td><td class="num">${cell(p.upper)}</td></tr>`),
  ];
  s.tableWrap.innerHTML =
    `<table><caption hidden>${esc(d.title)} — ${esc(describe(d))}</caption>` +
    `<thead><tr><th>Year</th><th>Type</th><th class="num">Value (${esc(d.unit)})</th><th class="num">Lower</th><th class="num">Upper</th></tr></thead>` +
    `<tbody>${rows.join("")}</tbody></table>`;
}

function renderSide(d) {
  const k = d.display_scale;
  const first = d.series[0];
  const last = d.series.at(-1);
  const delta = (last.value - first.value) * k;
  const percent = first.value ? ((last.value - first.value) / Math.abs(first.value)) * 100 : 0;
  const values = d.series.map((p) => p.value);
  const peak = d.series[values.indexOf(Math.max(...values))];

  const latest = h(
    "section",
    { class: "card stat-card" },
    h("div", { class: "stat-label" }, `Latest · ${last.year}`),
    h("div", { class: "stat-value" }, fmt(last.value * k), h("small", {}, d.unit)),
    h("div", { class: "stat-sub" }, last.lower !== null ? `95% UI ${fmt(last.lower * k)}–${fmt(last.upper * k)}` : "No uncertainty interval in the source"),
    h(
      "div",
      { class: "stat-grid" },
      h(
        "div",
        {},
        h("div", { class: "stat-label" }, `Since ${first.year}`),
        h("div", { class: "stat-value" }, signed(delta)),
        h("div", { class: "stat-sub" }, percent ? `${percent >= 0 ? "+" : "−"}${Math.abs(percent).toFixed(1)}%` : "no change"),
      ),
      h(
        "div",
        {},
        h("div", { class: "stat-label" }, "Peak"),
        h("div", { class: "stat-value" }, fmt(peak.value * k)),
        h("div", { class: "stat-sub" }, String(peak.year)),
      ),
    ),
  );

  const info = d.forecast_info;
  const end = d.forecast?.at(-1);
  let outlook;
  if (end) {
    outlook = h(
      "section",
      { class: "forecast-card" },
      h("div", { class: "stat-label" }, icon("forecast"), `Outlook · ${end.year}`),
      h("div", { class: "stat-value" }, fmt(end.value * k), h("small", {}, d.unit)),
      h("div", { class: "stat-sub" }, `95% prediction interval ${fmt(end.lower * k)}–${fmt(end.upper * k)}`),
      h("p", {}, `${info.model}, fitted to ${info.training_points} observations (${info.training_year_min}–${info.training_year_max}). Exploratory only.`),
    );
  } else if (info) {
    outlook = h("section", { class: "forecast-card" }, h("div", { class: "stat-label" }, icon("forecast"), "Outlook"), h("p", {}, `Not available for this series: ${info.note}`));
  } else {
    outlook = h(
      "section",
      { class: "forecast-card" },
      h("div", { class: "stat-label" }, icon("forecast"), "Outlook"),
      h("p", {}, "Project this series 3, 5 or 10 years ahead with a transparent linear model and its prediction interval."),
      h("button", { type: "button", class: "btn", onClick: () => { s.forecast = true; load(); } }, icon("forecast"), "Add a forecast"),
    );
  }
  s.side.replaceChildren(latest, outlook, h("p", { class: "side-note" }, "Choices only offer combinations that exist in the data."));
}

function draw() {
  const d = s.data;
  const years = d.series.map((p) => p.year);
  s.app.setHeader("Trends", `${d.title} · ${d.location} · ${d.release}`);
  s.title.textContent = d.title;
  s.sub.textContent = `${describe(d)} · ${span(years)}`;
  s.legend.replaceChildren(
    ...[
      h("span", { class: "key" }, h("i"), "Estimate"),
      d.has_uncertainty ? h("span", { class: "key band" }, h("i"), "95% uncertainty interval") : h("span", { class: "key" }, "No interval in the source"),
      d.forecast?.length ? h("span", { class: "key forecast" }, h("i"), "Exploratory forecast") : null,
    ].filter(Boolean),
  );
  s.chart?.destroy();
  s.chart = drawTrend(s.canvas, d);
  renderTable(d);
  showMode();
  const info = d.forecast_info;
  s.foot.replaceChildren(
    h("span", {}, `Unit: ${d.unit}. Source: IHME, ${d.release}.`),
    h("span", {}, info?.status === "available" ? `${info.model} · approximate 95% prediction interval` : "Hover the chart for exact values."),
  );
  renderSide(d);
}

async function download(kind) {
  const d = s?.data;
  if (!d) return;
  const { source, meta } = s.app;
  const stem = `${slug(d.title)}_${slug(d.release)}${d.forecast?.length ? `_forecast-${s.horizon}y` : ""}`;
  const href = source.href(kind, s.params);
  if (href) {
    downloadUrl(href, `${stem}.${kind}`);
    return;
  }
  if (kind === "csv") {
    downloadBlob(new Blob([trendCsv(d)], { type: "text/csv" }), `${stem}.csv`);
    return;
  }
  toast("Preparing your figure…");
  const blob = await figureBlob((canvas, options) => drawTrend(canvas, d, options), {
    title: d.title,
    subtitle: `${describe(d)} · ${span(d.series.map((p) => p.year))}`,
    notice: meta.prototype ? meta.notice : "",
    footer: [
      `Source: ${meta.citation}`,
      d.forecast_info?.status === "available" ? `Forecast: ${d.forecast_info.model}, approximate 95% prediction interval. ${d.forecast_info.note}` : "",
      `Figure: Global Health Evidence, School of Public Health, University College Cork. Generated ${fmtDate(new Date().toISOString())}.`,
    ].filter(Boolean),
  });
  downloadBlob(blob, `${stem}.png`);
}

export default {
  id: "trends",
  label: "Trends",
  icon: "trends",

  async mount(el, app, params) {
    const memory = app.memory.trends || {};
    s = {
      app,
      el,
      token: 0,
      chart: null,
      data: null,
      sel: memory.sel || {},
      range: memory.range || {},
      forecast: Boolean(memory.forecast),
      horizon: memory.horizon || 5,
      table: Boolean(memory.table),
    };
    const requested = params.series && app.catalogue.find((entry) => entry.series_id === params.series);
    if (requested) {
      s.sel = selectionOf(requested);
      s.range = {};
    } else if (!memory.sel) {
      s.sel = selectionOf(findSeries(app.catalogue, LIFE_EXPECTANCY) || app.catalogue[0]);
    }
    if (params.forecast !== undefined) {
      const years = Number(params.forecast);
      s.forecast = HORIZONS.includes(years);
      if (s.forecast) s.horizon = years;
    }
    app.setHeader("Trends", "");
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
