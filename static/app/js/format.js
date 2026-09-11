/* Formatting shared by every view: numbers, dates, text, and CSV. */

export function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const magnitude = Math.abs(value);
  const digits = magnitude >= 1000 ? 0 : magnitude >= 100 ? 1 : 2;
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export const signed = (value) => (value > 0 ? "+" : value < 0 ? "−" : "") + fmt(Math.abs(value));

// Stored values are exactly as imported -- IHME exports Percent as a proportion --
// and the API says how to scale each series for display.
export const scaled = (value, scale) => (value === null || value === undefined ? null : value * scale);

export function fmtDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? String(iso || "")
    : date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export const slug = (text) =>
  String(text).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "gbd";

// Dimension values come from imported files: escape before they touch innerHTML.
export const esc = (text) =>
  String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// Every dimension of a series that is not already its title. "Rate (per 100,000)"
// adds information; "Years (years)" only repeats it.
export function describe(d, { withTitle = false } = {}) {
  return [
    withTitle ? d.title : null,
    d.measure !== d.title ? d.measure : null,
    String(d.unit).toLowerCase() !== String(d.metric).toLowerCase() ? `${d.metric} (${d.unit})` : d.metric,
    d.age,
    d.sex,
    d.location,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function span(years) {
  if (!years.length) return "";
  const first = years[0];
  const last = years[years.length - 1];
  return first === last ? String(first) : `${first}–${last}`;
}

export const initials = (text) =>
  String(text || "?")
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");

const EXPORT_COLUMNS = ["release", "measure", "metric", "location", "sex", "age", "cause", "risk", "year", "value", "lower", "upper"];

function csvCell(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** A trend response as CSV, in the same columns as the server's export. */
export function trendCsv(data) {
  const withForecast = Boolean(data.forecast && data.forecast.length);
  const columns = withForecast ? [...EXPORT_COLUMNS, "record_type", "forecast_method"] : EXPORT_COLUMNS;
  const base = Object.fromEntries(EXPORT_COLUMNS.slice(0, 8).map((key) => [key, data[key] ?? ""]));
  const rows = data.series.map((p) => ({ ...base, ...p, record_type: "observed", forecast_method: "" }));
  if (withForecast) {
    rows.push(...data.forecast.map((p) => ({ ...base, ...p, record_type: "forecast", forecast_method: data.forecast_info.model })));
  }
  return [columns.join(","), ...rows.map((row) => columns.map((key) => csvCell(row[key])).join(","))].join("\n") + "\n";
}
