/* Methods & data: where the figures come from, how to cite them, and how to read them. */

import { fmtDate } from "../format.js";
import { h, icon, toast } from "../ui.js";

function card(accent, iconName, title, ...body) {
  return h(
    "section",
    { class: "card method", style: { "--accent": accent } },
    h("div", { class: "method-head" }, h("span", { class: "method-icon" }, icon(iconName)), h("h2", {}, title)),
    ...body,
  );
}

function facts(rows) {
  return h("dl", { class: "facts" }, rows.filter(Boolean).flatMap(([term, detail]) => [h("dt", {}, term), h("dd", {}, detail)]));
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Citation copied.");
  } catch {
    toast("Copy is unavailable here — select the citation instead.", "error");
  }
}

export default {
  id: "methods",
  label: "Methods & data",
  icon: "methods",

  mount(el, app) {
    const { meta } = app;
    app.setHeader("Methods & data", "How the figures are produced, and how to cite them");
    el.replaceChildren(
      h(
        "div",
        { class: "methods" },
        card(
          "var(--series-1)",
          "quote",
          "Source and citation",
          h("p", {}, "Estimates come from the IHME Global Burden of Disease Results Tool, used under IHME’s Free-to-Use Data Terms. Cite the release shown with every figure:"),
          h("blockquote", { class: "citation" }, meta.citation),
          h(
            "div",
            { class: "method-actions" },
            h("button", { type: "button", class: "btn", onClick: () => copy(meta.citation) }, icon("copy"), "Copy citation"),
            h("a", { class: "btn", href: "https://www.healthdata.org/gbd/about/data-terms", target: "_blank", rel: "noopener noreferrer" }, "IHME data terms", icon("arrow")),
          ),
        ),
        card(
          "var(--series-4)",
          "database",
          "This dataset",
          facts([
            ["Release", meta.release],
            ["Estimates", meta.row_count.toLocaleString()],
            ["Series", meta.series_count.toLocaleString()],
            ["Years", `${meta.year_min}–${meta.year_max}`],
            ["Last updated", fmtDate(meta.imported_at)],
            ["Sources", meta.source_files.map((file) => `${file.label} (${file.row_count.toLocaleString()} rows)`).join(", ")],
            ["Status", meta.prototype ? "Prototype data — not for citation" : meta.source],
          ]),
          meta.prototype ? h("p", { style: { "margin-top": "12px" } }, meta.notice) : null,
        ),
        card(
          "var(--series-3)",
          "layers",
          "Uncertainty intervals",
          h("p", {}, "IHME publishes each estimate with a 95% uncertainty interval. It is drawn as the shaded band around a trend, listed in every table, and included in CSV downloads as lower and upper bounds."),
          h("p", {}, "Where the source gives no interval, none is drawn: the application never invents one. Overlapping intervals mean a difference between two values may not be meaningful."),
        ),
        card(
          "var(--series-2)",
          "forecast",
          "Forecasts",
          h("p", {}, "Optional projections are exploratory aids, calculated on request and never stored with the data. They are not clinical or epidemiological predictions."),
          facts([
            ["Model", "Linear trend (ordinary least squares)"],
            ["Fitted to", "The most recent 15 annual observations, or fewer"],
            ["Requires", "At least 3 distinct years"],
            ["Interval", "Approximate 95% prediction interval"],
            ["Horizons", "3, 5 or 10 years"],
            ["Bounds", "Non-negative series stay non-negative; percentages stay at or below 100%"],
          ]),
        ),
      ),
    );
  },

  unmount() {},
  redraw() {},
};
