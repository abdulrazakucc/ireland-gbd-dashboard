/*
 * Overview: the story at a glance. Every card is a door into a detailed view,
 * opened on exactly the series or ranking it summarises.
 */

import { bestRankOption, findSeries, HEADLINES, LIFE_EXPECTANCY, rankParams } from "../catalogue.js";
import { drawArea, paletteFrom, sparkline } from "../charts.js";
import { fmt, signed, span } from "../format.js";
import { h, icon } from "../ui.js";

let state = null;
let charts = [];

function destroyCharts() {
  charts.forEach((chart) => chart.destroy());
  charts = [];
}

async function load(app) {
  const { source, catalogue, rankOptions } = app;
  const le = findSeries(catalogue, LIFE_EXPECTANCY);
  const headlines = HEADLINES.map((spec) => ({ spec, entry: findSeries(catalogue, spec) })).filter((item) => item.entry);
  const causeOption = bestRankOption(rankOptions, "causes");
  const riskOption = bestRankOption(rankOptions, "risks", /DALY/i);

  const [leData, leForecast, causes, risks, ...headlineData] = await Promise.all([
    le ? source.trend({ series: le.series_id }) : null,
    le ? source.trend({ series: le.series_id, forecast_years: 5 }).catch(() => null) : null,
    causeOption ? source.ranked(rankParams(causeOption)) : null,
    riskOption ? source.ranked(rankParams(riskOption)) : null,
    ...headlines.map((item) => source.trend({ series: item.entry.series_id })),
  ]);
  return {
    le,
    leData,
    leForecast,
    causes,
    risks,
    riskOption,
    headlines: headlines.map((item, i) => ({ ...item, data: headlineData[i] })),
  };
}

function change(series, scale) {
  const first = series[0];
  const last = series[series.length - 1];
  const delta = (last.value - first.value) * scale;
  return { first, last, delta, percent: first.value ? ((last.value - first.value) / Math.abs(first.value)) * 100 : 0 };
}

function heroCard(app, data) {
  if (!data.leData) return h("div", { class: "hero-card" }, h("p", {}, "Life expectancy is not in the loaded dataset."));
  const le = data.leData;
  const { first, last, delta } = change(le.series, le.display_scale);
  const projected = data.leForecast?.forecast?.at(-1);
  const canvas = h("canvas", { role: "img", "aria-label": `Life expectancy from ${first.year} to ${last.year}` });
  const card = h(
    "button",
    { type: "button", class: "hero-card", onClick: () => app.navigate("trends", { series: le.series_id }) },
    h(
      "div",
      { class: "hero-text" },
      h("p", { class: "eyebrow" }, "Headline"),
      h("p", { class: "hero-title" }, `Life expectancy ${/birth|<1 year/i.test(le.age) ? "at birth" : `(${le.age})`}, ${le.location}`),
      h("div", { class: "hero-value" }, fmt(last.value * le.display_scale), h("span", { class: "hero-unit" }, `years · ${last.year}`)),
      h(
        "div",
        { class: "hero-delta" },
        h("span", { class: "chip-dark" }, icon(delta >= 0 ? "up" : "down"), `${signed(delta)} years`),
        h("span", {}, `since ${first.year}`),
      ),
      h(
        "p",
        { class: "hero-foot" },
        icon("forecast"),
        projected ? `Exploratory outlook ${projected.year}: ${fmt(projected.value * le.display_scale)} years` : `${span(le.series.map((p) => p.year))} · ${le.release}`,
      ),
    ),
    h("div", { class: "hero-chart" }, canvas),
  );
  return { card, draw: () => charts.push(drawArea(canvas, le.series.map((p) => p.value * le.display_scale), "#ffb500", { palette: { ...paletteFrom(), surface: "#17456b" } })) };
}

function kpiCard(app, item, palette) {
  const { spec, data } = item;
  const { first, last, delta, percent } = change(data.series, data.display_scale);
  const falling = delta < 0;
  const good = spec.goodDown ? falling : !falling;
  const color = palette.series[spec.slot - 1];
  return h(
    "button",
    { type: "button", class: "kpi", style: { "--accent": `var(--series-${spec.slot})` }, onClick: () => app.navigate("trends", { series: data.series_id }) },
    h("span", { class: "kpi-label" }, h("i"), spec.label),
    h("span", { class: "kpi-value" }, fmt(last.value * data.display_scale), h("span", { class: "kpi-unit" }, data.unit)),
    h(
      "span",
      { class: "kpi-foot" },
      h(
        "span",
        {},
        h("span", { class: `delta ${good ? "good" : "bad"}` }, icon(falling ? "down" : "up"), `${fmt(Math.abs(delta))}`, percent ? h("small", {}, `(${Math.abs(percent).toFixed(0)}%)`) : null),
        h("span", { class: "kpi-since", style: { display: "block", "font-size": "11.5px", color: "var(--text-muted)" } }, `since ${first.year}`),
      ),
      h("span", { class: "kpi-spark", html: sparkline(data.series.map((p) => p.value), color, palette.surface) }),
    ),
  );
}

function insights(app, data) {
  const items = [];
  const risk = data.risks?.items?.[0];
  if (risk) {
    items.push({
      accent: "var(--series-2)",
      icon: "rankings",
      eyebrow: `Leading risk factor · ${data.risks.year}`,
      title: risk.label,
      detail: `${fmt(risk.value * data.risks.display_scale)} ${data.risks.unit} of ${data.risks.measure.replace(/\s*\(.*\)/, "")}`,
      go: () => app.navigate("rankings", { ...rankParams(data.riskOption) }),
    });
  }
  const improvements = data.headlines
    .map((item) => ({ item, ...change(item.data.series, item.data.display_scale) }))
    .filter(({ item, delta }) => (item.spec.goodDown ? delta < 0 : delta > 0))
    .sort((a, b) => Math.abs(b.percent) - Math.abs(a.percent));
  if (improvements.length) {
    const best = improvements[0];
    items.push({
      accent: "var(--series-3)",
      icon: "trends",
      eyebrow: "Biggest improvement",
      title: best.item.spec.label,
      detail: `${best.delta < 0 ? "Down" : "Up"} ${Math.abs(best.percent).toFixed(0)}% since ${best.first.year}`,
      go: () => app.navigate("trends", { series: best.item.data.series_id }),
    });
  }
  const outlook = data.leForecast;
  if (outlook?.forecast?.length) {
    const end = outlook.forecast.at(-1);
    items.push({
      accent: "var(--series-1)",
      icon: "forecast",
      eyebrow: "Exploratory outlook",
      title: `Life expectancy ${end.year}: ${fmt(end.value * outlook.display_scale)} years`,
      detail: `95% prediction interval ${fmt(end.lower * outlook.display_scale)}–${fmt(end.upper * outlook.display_scale)}`,
      go: () => app.navigate("trends", { series: outlook.series_id, forecast: 5 }),
    });
  }
  return h(
    "section",
    { class: "card insights", "aria-label": "Highlights" },
    h("h2", {}, "Highlights"),
    items.map((item) =>
      h(
        "button",
        { type: "button", class: "insight", style: { "--accent": item.accent }, onClick: item.go },
        h("span", { class: "insight-icon" }, icon(item.icon)),
        h("span", { class: "insight-text" }, h("span", {}, item.eyebrow), h("strong", {}, item.title), h("em", {}, item.detail)),
        icon("right"),
      ),
    ),
  );
}

function leaders(app, ranking) {
  if (!ranking) return h("section", { class: "card leaders" }, h("h2", {}, "Leading causes"), h("p", {}, "No causes can be ranked in this dataset."));
  const top = ranking.items.slice(0, 5);
  const max = Math.max(...top.map((item) => item.value)) || 1;
  return h(
    "section",
    { class: "card leaders", "aria-label": "Leading causes" },
    h(
      "div",
      { class: "leaders-head" },
      h("h2", {}, `Leading causes · ${ranking.year}`),
      h("button", { type: "button", class: "link-btn", onClick: () => app.navigate("rankings", { type: "causes" }) }, "All", icon("right")),
    ),
    h("p", { class: "card-sub", style: { margin: "0 4px 4px" } }, `${ranking.measure.replace(/\s*\(.*\)/, "")} · ${ranking.metric} (${ranking.unit}) · ${ranking.age}`),
    h(
      "div",
      { class: "leader-list" },
      top.map((item, i) =>
        h(
          "div",
          { class: "leader" },
          h("span", { class: "leader-rank" }, String(i + 1)),
          h("span", { class: "leader-label", title: item.label }, item.label),
          h("span", { class: "leader-value" }, fmt(item.value * ranking.display_scale)),
          h("span", { class: "leader-bar" }, h("i", { style: { width: `${(item.value / max) * 100}%`, "animation-delay": `${i * 70}ms` } })),
        ),
      ),
    ),
  );
}

function render() {
  if (!state) return;
  destroyCharts();
  const { app, data, el } = state;
  const palette = paletteFrom();
  const hero = heroCard(app, data);
  el.replaceChildren(
    h(
      "div",
      { class: "overview" },
      hero.card || hero,
      h("section", { class: "kpis", "aria-label": "Headline indicators" }, data.headlines.map((item) => kpiCard(app, item, palette))),
      h("div", { class: "side-stack" }, insights(app, data), leaders(app, data.causes)),
    ),
  );
  hero.draw?.();
}

export default {
  id: "overview",
  label: "Overview",
  icon: "overview",

  async mount(el, app) {
    const locations = [...new Set(app.catalogue.map((entry) => entry.location))];
    app.setHeader("Overview", `${locations.length > 1 ? `${locations.length} locations` : locations[0]} · ${app.meta.release} · ${app.meta.series_count.toLocaleString()} series`);
    el.append(
      h(
        "div",
        { class: "overview" },
        h("div", { class: "skeleton", style: { "grid-column": "1" } }),
        h("div", { class: "skeleton", style: { "grid-column": "2", "grid-row": "1 / span 2" } }),
      ),
    );
    const mine = Symbol("overview");
    state = { app, el, token: mine };
    const data = await load(app);
    if (!state || state.token !== mine) return;
    state.data = data;
    render();
  },

  unmount() {
    destroyCharts();
    state = null;
  },

  redraw: render,
};
