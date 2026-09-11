/* The catalogue of series: dimension order, sensible defaults, and cascading choices. */

export const NONE = ""; // a cause or risk that does not apply to a series

export const DIM_LABEL = {
  release: "Release",
  measure: "Measure",
  cause: "Cause",
  risk: "Risk",
  metric: "Metric",
  age: "Age",
  sex: "Sex",
  location: "Location",
  year: "Year",
};

export const TREND_DIMS = ["location", "measure", "cause", "risk", "metric", "age", "sex", "release"];
export const RANK_DIMS = ["location", "measure", "metric", "age", "sex", "year", "release"];
export const RANK_KEYS = ["type", "release", "measure", "metric", "location", "sex", "age", "year"];
export const HORIZONS = [3, 5, 10];

// Defaults a new selection falls back to, in order of preference.
export const PREFER = {
  sex: ["Both"],
  age: ["Age-standardized", "All ages", "At birth", "<1 year"],
  cause: [NONE, "All causes"],
  risk: [NONE],
  location: ["Ireland"],
};

function ageRank(age) {
  if (/standardi[sz]ed/i.test(age)) return -3;
  if (/^all ages$/i.test(age)) return -2;
  if (/birth/i.test(age)) return -1;
  const match = age.match(/\d+(\.\d+)?/);
  return match ? parseFloat(match[0]) - (age.trim().startsWith("<") ? 0.5 : 0) : 999;
}

export function sortValues(dim, values) {
  const copy = [...values];
  if (dim === "year") return copy.sort((a, b) => b - a);
  if (dim === "age") return copy.sort((a, b) => ageRank(a) - ageRank(b) || a.localeCompare(b));
  if (dim === "sex") {
    const order = (v) => ["Both", "Female", "Male"].indexOf(v) + 1 || 9;
    return copy.sort((a, b) => order(a) - order(b) || a.localeCompare(b));
  }
  return copy.sort((a, b) => (b === NONE) - (a === NONE) || String(a).localeCompare(String(b)));
}

export function pick(dim, values, current) {
  if (values.includes(current)) return current;
  for (const preferred of PREFER[dim] || []) if (values.includes(preferred)) return preferred;
  return values[0];
}

/**
 * Walk the dimensions in order, narrowing the pool at each step. Each choice
 * only offers values that still lead to real data, so no combination a reader
 * can pick is a dead end.
 */
export function cascade(pool, dims, current) {
  const selection = {};
  const options = {};
  for (const dim of dims) {
    const values = sortValues(dim, [...new Set(pool.map((entry) => entry[dim] ?? NONE))]);
    options[dim] = values;
    selection[dim] = pick(dim, values, current[dim]);
    pool = pool.filter((entry) => (entry[dim] ?? NONE) === selection[dim]);
  }
  return { selection, options, match: pool[0] };
}

export const optionText = (dim, value) =>
  value === NONE && (dim === "cause" || dim === "risk") ? "Not applicable" : String(value);

// Curated headline indicators, matched by name so they survive a new export.
export const HEADLINES = [
  { key: "hale", label: "Healthy life expectancy", slot: 1, goodDown: false, measure: /^HALE\b/i },
  { key: "tobacco", label: "Tobacco exposure", slot: 2, goodDown: true, measure: /summary exposure value/i, risk: /^tobacco$/i },
  { key: "bmi", label: "High BMI exposure", slot: 3, goodDown: true, measure: /summary exposure value/i, risk: /high body-mass index/i },
  { key: "air", label: "Air pollution exposure", slot: 4, goodDown: true, measure: /summary exposure value/i, risk: /^air pollution$/i },
];
export const LIFE_EXPECTANCY = { measure: /^life expectancy$/i };

/** The best catalogue entry for a spec: preferred sex, age and location, then the most years. */
export function findSeries(catalogue, spec) {
  const matches = catalogue.filter((entry) =>
    ["measure", "cause", "risk"].every((dim) => !spec[dim] || spec[dim].test(entry[dim] || "")),
  );
  const score = (entry) =>
    ["sex", "age", "location"].reduce((sum, dim) => {
      const index = (PREFER[dim] || []).indexOf(entry[dim]);
      return sum + (index < 0 ? 9 : index);
    }, 0);
  return matches.sort((a, b) => score(a) - score(b) || b.years.length - a.years.length)[0] || null;
}

/** The clearest ranking of a type to show first: both sexes, age-standardised, the launch location, latest year. */
export function bestRankOption(options, type, measure = null) {
  let pool = options.filter((option) => option.type === type);
  if (measure) {
    const preferred = pool.filter((option) => measure.test(option.measure));
    if (preferred.length) pool = preferred;
  }
  const score = (option) =>
    ["sex", "age", "location"].reduce((sum, dim) => {
      const index = (PREFER[dim] || []).indexOf(option[dim]);
      return sum + (index < 0 ? 9 : index);
    }, 0);
  return [...pool].sort((a, b) => score(a) - score(b) || b.year - a.year)[0] || null;
}

export const rankParams = (option, extra = {}) => ({
  ...Object.fromEntries(RANK_KEYS.map((key) => [key, option[key]])),
  ...extra,
});
