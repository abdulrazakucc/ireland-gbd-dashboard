/*
 * Presentation mode: the headline story as full-screen slides, for talks and
 * teaching. Every slide is built from the loaded data, so it stays correct
 * when a new GBD release is imported.
 */

import { bestRankOption, cascade, findSeries, HEADLINES, LIFE_EXPECTANCY, rankParams, TREND_DIMS } from "./catalogue.js";
import { drawRank, drawTrend, paletteFrom } from "./charts.js";
import { describe, fmt, signed, span } from "./format.js";
import { h, icon } from "./ui.js";

function currentTrend(app, exclude) {
  const memory = app.memory.trends;
  if (!memory?.sel) return null;
  const { match } = cascade(app.catalogue, TREND_DIMS, memory.sel);
  return match && match.series_id !== exclude ? match : null;
}

function header(eyebrow, title, sub) {
  return h("header", { class: "slide-head" }, h("p", { class: "slide-eyebrow" }, eyebrow), h("h2", { class: "slide-title" }, title), sub ? h("p", { class: "slide-sub" }, sub) : null);
}

function coverSlide(meta, place) {
  return {
    build: () => ({
      node: h(
        "section",
        { class: "slide cover" },
        h("p", { class: "slide-eyebrow" }, "School of Public Health · University College Cork"),
        h("h2", { class: "slide-title" }, "Global Health ", h("span", {}, "Evidence")),
        h(
          "div",
          { class: "cover-meta" },
          h("div", { class: "cover-person" }, h("img", { src: "../assets/zubair-kabir.png", alt: "" }), h("div", {}, h("strong", {}, "Dr. Zubair Kabir"), h("span", {}, "Principal Investigator"))),
          h("span", {}, `${place} · ${meta.release}`),
          meta.prototype ? h("span", { class: "flag" }, "Prototype data · not for citation") : null,
        ),
      ),
    }),
  };
}

function trendSlide(data, eyebrow, title, takeaway) {
  return {
    build: () => {
      const canvas = h("canvas", { role: "img", "aria-label": title });
      return {
        node: h(
          "section",
          { class: "slide" },
          header(eyebrow, title, `${describe(data)} · ${span(data.series.map((p) => p.year))}`),
          h("div", { class: "slide-body" }, canvas),
          h("p", { class: "slide-takeaway" }, icon("trends"), takeaway),
        ),
        draw: (palette) => drawTrend(canvas, data, { palette, fontSize: 15 }),
      };
    },
  };
}

function kpiSlide(items) {
  return {
    build: () => ({
      node: h(
        "section",
        { class: "slide" },
        header("Headline indicators", "How key measures have moved", "Latest estimate and change since the first year available"),
        h(
          "div",
          { class: "slide-body" },
          h(
            "div",
            { class: "slide-kpis" },
            items.map(({ spec, data }) => {
              const k = data.display_scale;
              const first = data.series[0];
              const last = data.series.at(-1);
              const delta = (last.value - first.value) * k;
              const percent = first.value ? Math.abs(((last.value - first.value) / first.value) * 100).toFixed(0) : "0";
              return h(
                "div",
                { class: "slide-kpi", style: { "--accent": `var(--series-${spec.slot})` } },
                h("span", {}, spec.label),
                h("strong", {}, fmt(last.value * k), h("small", {}, `${data.unit} · ${last.year}`)),
                h("em", {}, `${delta < 0 ? "↓" : "↑"} ${fmt(Math.abs(delta))} (${percent}%) since ${first.year}`),
              );
            }),
          ),
        ),
        h("p", { class: "slide-takeaway" }, icon("overview"), "Exposure measures are summary exposure values; lower is better."),
      ),
    }),
  };
}

function rankSlide(data) {
  const k = data.display_scale;
  const [top, second] = data.items;
  const causes = data.type === "causes";
  const title = `${top.label} ${causes ? "carries the largest burden" : "is the leading risk factor"} in ${data.year}`;
  return {
    build: () => {
      const canvas = h("canvas", { role: "img", "aria-label": title });
      return {
        node: h(
          "section",
          { class: "slide" },
          header(causes ? `Leading causes · ${data.year}` : `Leading risk factors · ${data.year}`, title, `Ranked by ${describe({ ...data, title: null })}`),
          h("div", { class: "slide-body" }, canvas),
          h(
            "p",
            { class: "slide-takeaway" },
            icon("rankings"),
            `${top.label}: ${fmt(top.value * k)} ${data.unit}${second ? ` · followed by ${second.label} at ${fmt(second.value * k)}` : ""}`,
          ),
        ),
        draw: (palette) => drawRank(canvas, data, { palette, fontSize: 15, limit: 10, barThickness: 28 }),
      };
    },
  };
}

function sourcesSlide(meta) {
  return {
    build: () => ({
      node: h(
        "section",
        { class: "slide" },
        header("Sources", "Data and citation"),
        h(
          "div",
          { class: "slide-body" },
          h(
            "div",
            { class: "sources" },
            h("blockquote", {}, meta.citation),
            h("p", {}, "Shaded bands are 95% uncertainty intervals where the source provides them. Forecasts are exploratory linear projections, not epidemiological predictions."),
            meta.prototype ? h("span", { class: "flag" }, meta.notice) : null,
          ),
        ),
        h("p", { class: "slide-takeaway" }, icon("shield"), "Global Health Evidence · School of Public Health, University College Cork"),
      ),
    }),
  };
}

async function buildSlides(app) {
  const { source, catalogue, rankOptions, meta } = app;
  const le = findSeries(catalogue, LIFE_EXPECTANCY);
  const headlines = HEADLINES.map((spec) => ({ spec, entry: findSeries(catalogue, spec) })).filter((item) => item.entry);
  const causeOption = bestRankOption(rankOptions, "causes");
  const riskOption = bestRankOption(rankOptions, "risks", /DALY/i);
  const current = currentTrend(app, le?.series_id);
  const trendsMemory = app.memory.trends || {};

  const [leData, causes, risks, currentData, ...headlineData] = await Promise.all([
    le ? source.trend({ series: le.series_id, forecast_years: 5 }).catch(() => source.trend({ series: le.series_id })) : null,
    causeOption ? source.ranked(rankParams(causeOption)) : null,
    riskOption ? source.ranked(rankParams(riskOption)) : null,
    current ? source.trend({ series: current.series_id, ...(trendsMemory.forecast ? { forecast_years: trendsMemory.horizon } : {}) }) : null,
    ...headlines.map((item) => source.trend({ series: item.entry.series_id })),
  ]);

  const locations = [...new Set(catalogue.map((entry) => entry.location))];
  const slides = [coverSlide(meta, locations.length > 1 ? `${locations.length} locations` : locations[0])];
  if (leData) {
    const k = leData.display_scale;
    const first = leData.series[0];
    const last = leData.series.at(-1);
    const end = leData.forecast?.at(-1);
    slides.push(
      trendSlide(
        leData,
        "Life expectancy",
        `Life expectancy reached ${fmt(last.value * k)} years in ${last.year}`,
        `${signed((last.value - first.value) * k)} years since ${first.year}${end ? ` · exploratory outlook for ${end.year}: ${fmt(end.value * k)} years` : ""}`,
      ),
    );
  }
  if (headlineData.length) slides.push(kpiSlide(headlines.map((item, i) => ({ ...item, data: headlineData[i] }))));
  if (causes?.items.length) slides.push(rankSlide(causes));
  if (risks?.items.length) slides.push(rankSlide(risks));
  if (currentData) {
    const k = currentData.display_scale;
    const last = currentData.series.at(-1);
    slides.push(trendSlide(currentData, "Selected trend", currentData.title, `Latest: ${fmt(last.value * k)} ${currentData.unit} in ${last.year}`));
  }
  slides.push(sourcesSlide(meta));
  return slides;
}

export async function openPresentation(app) {
  if (document.querySelector(".present")) return;
  const opener = document.activeElement;
  const overlay = h(
    "div",
    { class: "present", role: "dialog", "aria-modal": "true", "aria-label": "Presentation", tabindex: "-1" },
    h("div", { class: "boot", style: { "min-height": "100vh" } }, h("div", { class: "spinner" }), h("p", {}, "Preparing slides…")),
  );
  document.body.append(overlay);
  document.body.classList.add("presenting");
  overlay.focus();
  // Requested first, while the click or key press still counts as a user gesture.
  const fullscreen = overlay.requestFullscreen?.().catch(() => {});

  let slides;
  let index = 0;
  let chart = null;

  function close() {
    document.removeEventListener("keydown", onKey, true);
    chart?.destroy();
    if (document.fullscreenElement === overlay) document.exitFullscreen().catch(() => {});
    overlay.remove();
    document.body.classList.remove("presenting");
    opener?.focus?.();
  }

  try {
    await fullscreen;
    slides = await buildSlides(app);
  } catch (error) {
    close();
    throw error;
  }

  const holder = h("div", { style: { height: "100%" } });
  const count = h("span", { class: "present-count", "aria-live": "polite" });
  const prev = h("button", { type: "button", class: "present-nav prev", "aria-label": "Previous slide", onClick: () => go(index - 1) }, icon("left"));
  const next = h("button", { type: "button", class: "present-nav next", "aria-label": "Next slide", onClick: () => go(index + 1) }, icon("right"));
  const dots = h(
    "div",
    { class: "present-dots" },
    slides.map((_, i) => h("button", { type: "button", "aria-label": `Slide ${i + 1}`, onClick: () => go(i) })),
  );
  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else overlay.requestFullscreen?.().catch(() => {});
  };

  overlay.replaceChildren(
    h(
      "div",
      { class: "present-top" },
      h("img", { src: "../assets/ucc-logo.png", alt: "" }),
      h("span", { class: "brand-text" }, h("strong", {}, "Global Health Evidence"), h("span", {}, app.meta.release)),
      count,
      h("button", { type: "button", class: "icon-btn", title: "Full screen (F)", "aria-label": "Toggle full screen", onClick: toggleFullscreen }, icon("expand")),
      h("button", { type: "button", class: "icon-btn", title: "Close (Esc)", "aria-label": "Close presentation", onClick: close }, icon("close")),
    ),
    h("div", { class: "present-stage" }, holder, prev, next),
    h("div", { class: "present-foot" }, h("span", {}, "← → to move · F for full screen · Esc to close"), dots),
  );

  function go(target) {
    index = Math.max(0, Math.min(slides.length - 1, target));
    chart?.destroy();
    chart = null;
    const { node, draw } = slides[index].build();
    holder.replaceChildren(node);
    count.textContent = `${index + 1} / ${slides.length}`;
    prev.disabled = index === 0;
    next.disabled = index === slides.length - 1;
    [...dots.children].forEach((dot, i) => dot.setAttribute("aria-current", String(i === index)));
    if (draw) requestAnimationFrame(() => { chart = draw(paletteFrom(overlay)); });
  }

  function onKey(event) {
    const onButton = event.target instanceof HTMLElement && event.target.closest("button");
    if (["ArrowRight", "PageDown"].includes(event.key) || (event.key === " " && !onButton)) {
      event.preventDefault();
      go(index + 1);
    } else if (["ArrowLeft", "PageUp"].includes(event.key)) {
      event.preventDefault();
      go(index - 1);
    } else if (event.key === "Home") go(0);
    else if (event.key === "End") go(slides.length - 1);
    else if (event.key === "Escape") close();
    else if (event.key.toLowerCase() === "f" && !event.metaKey && !event.ctrlKey) toggleFullscreen();
  }

  document.addEventListener("keydown", onKey, true);
  go(0);
}
