/*
 * Every chart in the application, the presentation and exported figures.
 *
 * Colours are passed in as a palette rather than read globally, so the same
 * chart can be drawn for the current theme, for the always-dark presentation,
 * or on white for a downloaded figure. The series palette is the validated one
 * the dashboard has always used (lightness band, chroma floor, colour-vision
 * separation); UCC navy and gold stay in the chrome.
 */

import { fmt, scaled } from "./format.js";

const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif';

export const css = (name, el = document.documentElement) => getComputedStyle(el).getPropertyValue(name).trim();

export function paletteFrom(el = document.documentElement) {
  return {
    series: [1, 2, 3, 4].map((i) => css(`--series-${i}`, el)),
    text: css("--text-primary", el),
    secondary: css("--text-secondary", el),
    muted: css("--text-muted", el),
    grid: css("--grid", el),
    axis: css("--axis", el),
    surface: css("--surface-1", el),
  };
}

// Figures are downloaded to paste into slides and papers: always on white.
export const LIGHT = {
  series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
  text: "#14181d",
  secondary: "#4d5561",
  muted: "#6b7480",
  grid: "#e7e9ee",
  axis: "#cfd4dc",
  surface: "#ffffff",
};

export function alpha(hex, amount) {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) return hex;
  return `#${clean}${Math.round(amount * 255).toString(16).padStart(2, "0")}`;
}

function tooltip(p, size) {
  return {
    enabled: true,
    backgroundColor: p.surface,
    titleColor: p.text,
    bodyColor: p.secondary,
    borderColor: alpha(p.axis, 0.9),
    borderWidth: 1,
    padding: 12,
    cornerRadius: 10,
    boxPadding: 5,
    usePointStyle: true,
    titleFont: { family: FONT, weight: "600", size: size + 0.5 },
    bodyFont: { family: FONT, size: size + 0.5 },
  };
}

const crosshair = (p) => ({
  id: "crosshair",
  afterDatasetsDraw(chart) {
    const active = chart.tooltip?.getActiveElements?.() || [];
    if (!active.length) return;
    const { ctx, chartArea } = chart;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(active[0].element.x, chartArea.top);
    ctx.lineTo(active[0].element.x, chartArea.bottom);
    ctx.lineWidth = 1;
    ctx.strokeStyle = p.axis;
    ctx.stroke();
    ctx.restore();
  },
});

// The value beside the last observed point -- the one number people look for.
const endLabel = (p, size) => ({
  id: "endLabel",
  afterDatasetsDraw(chart) {
    const values = chart.data.datasets[0].data;
    let index = values.length - 1;
    while (index >= 0 && values[index] === null) index--;
    if (index < 0) return;
    const point = chart.getDatasetMeta(0).data[index];
    const { ctx, chartArea } = chart;
    const text = fmt(values[index]);
    ctx.save();
    ctx.font = `600 ${size + 1}px ${FONT}`;
    const width = ctx.measureText(text).width;
    // A forecast continues to the right of the last observed point, so the
    // label moves to its left rather than sit on the projected line.
    const forecastFollows = chart.data.datasets.some((dataset) => dataset.label === "Forecast");
    let x = point.x + 12;
    ctx.textAlign = "left";
    if (forecastFollows || x + width > chartArea.right) {
      x = point.x - 12;
      ctx.textAlign = "right";
    }
    ctx.textBaseline = "bottom";
    ctx.fillStyle = p.text;
    ctx.fillText(text, x, point.y - 8);
    ctx.restore();
  },
});

const barValues = (p, size) => ({
  id: "barValues",
  afterDatasetsDraw(chart) {
    const meta = chart.getDatasetMeta(0);
    const values = chart.data.datasets[0].data;
    const { ctx, chartArea } = chart;
    ctx.save();
    ctx.font = `600 ${size}px ${FONT}`;
    ctx.textBaseline = "middle";
    meta.data.forEach((bar, i) => {
      if (values[i] === null) return;
      const text = fmt(values[i]);
      const width = ctx.measureText(text).width;
      if (bar.x + 10 + width <= chartArea.right) {
        ctx.textAlign = "left";
        ctx.fillStyle = p.secondary;
        ctx.fillText(text, bar.x + 8, bar.y);
      } else {
        ctx.textAlign = "right";
        ctx.fillStyle = "#ffffff";
        ctx.fillText(text, bar.x - 8, bar.y);
      }
    });
    ctx.restore();
  },
});

function axes(p, size, unit, { compact, horizontal }) {
  const value = {
    grid: { color: p.grid, drawTicks: false },
    border: { display: false },
    ticks: { color: p.muted, padding: 8, font: { family: FONT, size }, callback: (v) => fmt(v) },
    title: { display: !compact && Boolean(unit), text: unit, color: p.muted, font: { family: FONT, size } },
  };
  const category = {
    grid: { display: false },
    border: { color: p.axis },
    ticks: { color: horizontal ? p.secondary : p.muted, padding: 6, autoSkip: !horizontal, font: { family: FONT, size } },
  };
  return horizontal ? { x: { ...value, grace: "14%" }, y: category } : { x: category, y: value };
}

function common(p, options) {
  return {
    responsive: options.responsive !== false,
    maintainAspectRatio: false,
    animation: options.animate === false ? false : { duration: 550, easing: "easeOutQuart" },
    devicePixelRatio: options.devicePixelRatio,
  };
}

/**
 * A series over time: estimate, 95% uncertainty band, and an optional
 * exploratory forecast with its prediction interval.
 */
export function drawTrend(canvas, data, options = {}) {
  const p = options.palette || paletteFrom();
  const size = options.fontSize || 12;
  const color = p.series[0];
  const projectedColor = p.series[2];
  const k = data.display_scale;
  const forecast = data.forecast || [];
  const n = data.series.length;
  const values = data.series.map((pt) => pt.value * k);
  const lower = data.series.map((pt) => scaled(pt.lower, k));
  const upper = data.series.map((pt) => scaled(pt.upper, k));
  const fValues = forecast.map((pt) => pt.value * k);
  const fLower = forecast.map((pt) => scaled(pt.lower, k));
  const fUpper = forecast.map((pt) => scaled(pt.upper, k));
  const gaps = forecast.map(() => null);
  const band = data.has_uncertainty;

  const datasets = [
    {
      label: data.title,
      data: [...values, ...gaps],
      borderColor: color,
      backgroundColor: alpha(color, 0.1),
      borderWidth: options.compact ? 2.5 : 2.5,
      fill: !band && !forecast.length,
      tension: 0.3,
      pointRadius: options.compact ? 0 : 3.5,
      pointHoverRadius: 6,
      pointBackgroundColor: color,
      pointBorderColor: p.surface,
      pointBorderWidth: 2,
      pointHitRadius: 24,
    },
  ];
  const bound = { borderWidth: 0, pointRadius: 0, pointHitRadius: 0, tension: 0.3, spanGaps: false };
  if (band) {
    datasets.push(
      { ...bound, label: "Upper", data: [...upper, ...gaps], fill: "+1", backgroundColor: alpha(color, 0.2) },
      { ...bound, label: "Lower", data: [...lower, ...gaps], fill: false },
    );
  }
  if (forecast.length) {
    const lead = data.series.map((_, i) => (i === n - 1 ? values[i] : null));
    const hidden = data.series.map(() => null);
    datasets.push(
      {
        label: "Forecast",
        data: [...lead, ...fValues],
        borderColor: projectedColor,
        borderDash: [7, 5],
        borderWidth: 2.5,
        tension: 0.2,
        pointRadius: options.compact ? 0 : 3.5,
        pointBackgroundColor: projectedColor,
        pointBorderColor: p.surface,
        pointBorderWidth: 2,
      },
      { ...bound, label: "Forecast upper", data: [...hidden, ...fUpper], fill: "+1", backgroundColor: alpha(projectedColor, 0.16) },
      { ...bound, label: "Forecast lower", data: [...hidden, ...fLower], fill: false },
    );
  }

  return new Chart(canvas, {
    type: "line",
    data: { labels: [...data.series.map((pt) => pt.year), ...forecast.map((pt) => pt.year)], datasets },
    options: {
      ...common(p, options),
      layout: { padding: { top: 22, right: 18 } },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltip(p, size),
          filter: (item) =>
            item.dataset.label === data.title || (item.dataset.label === "Forecast" && item.dataIndex >= n),
          callbacks: {
            title: (items) => `Year ${items[0].label}`,
            label: (ctx) => {
              const projected = ctx.dataset.label === "Forecast";
              const i = projected ? ctx.dataIndex - n : ctx.dataIndex;
              const value = projected ? fValues[i] : values[i];
              const lo = projected ? fLower[i] : lower[i];
              const hi = projected ? fUpper[i] : upper[i];
              const interval = lo !== null && lo !== undefined ? `  (95% ${projected ? "PI" : "UI"} ${fmt(lo)}–${fmt(hi)})` : "";
              return ` ${projected ? "Forecast " : ""}${fmt(value)} ${data.unit}${interval}`;
            },
          },
        },
      },
      scales: axes(p, size, data.unit, { compact: options.compact }),
    },
    plugins: [crosshair(p), endLabel(p, size)],
  });
}

/** Leading causes or risks: observed bars, with projected bars when a forecast is on. */
export function drawRank(canvas, data, options = {}) {
  const p = options.palette || paletteFrom();
  const size = options.fontSize || 12;
  const color = data.type === "causes" ? p.series[0] : p.series[1];
  const k = data.display_scale;
  const toItem = (it) => ({ label: it.label, v: it.value * k, lo: scaled(it.lower, k), hi: scaled(it.upper, k) });
  const observed = data.items.map(toItem);
  const projected = (data.forecast_items || []).map(toItem);
  const byLabel = Object.fromEntries(observed.map((it) => [it.label, it]));
  const projectedByLabel = Object.fromEntries(projected.map((it) => [it.label, it]));
  let items = projected.length ? projected.map((it) => byLabel[it.label]).filter(Boolean) : observed;
  if (options.limit) items = items.slice(0, options.limit);

  const datasets = [
    {
      label: `Observed ${data.year}`,
      data: items.map((it) => it.v),
      backgroundColor: color,
      borderRadius: 6,
      borderSkipped: "start",
      maxBarThickness: options.barThickness || 22,
      categoryPercentage: 0.78,
      barPercentage: projected.length ? 0.92 : 0.86,
    },
  ];
  if (projected.length) {
    datasets.push({
      label: `Forecast ${data.forecast_year}`,
      data: items.map((it) => projectedByLabel[it.label]?.v ?? null),
      backgroundColor: alpha(p.series[2], 0.72),
      borderColor: p.series[2],
      borderWidth: 1,
      borderRadius: 6,
      borderSkipped: "start",
      maxBarThickness: Math.round((options.barThickness || 22) * 0.7),
      categoryPercentage: 0.78,
      barPercentage: 0.92,
    });
  }

  const chart = new Chart(canvas, {
    type: "bar",
    data: { labels: items.map((it) => it.label), datasets },
    options: {
      ...common(p, options),
      indexAxis: "y",
      layout: { padding: { right: 12 } },
      plugins: {
        legend: {
          display: projected.length > 0,
          position: "top",
          align: "end",
          labels: { color: p.secondary, usePointStyle: true, boxWidth: 8, font: { family: FONT, size } },
        },
        tooltip: {
          ...tooltip(p, size),
          callbacks: {
            label: (ctx) => {
              const it = ctx.datasetIndex ? projectedByLabel[items[ctx.dataIndex].label] : items[ctx.dataIndex];
              const interval = it.lo !== null ? `  (95% ${ctx.datasetIndex ? "PI" : "UI"} ${fmt(it.lo)}–${fmt(it.hi)})` : "";
              return ` ${fmt(it.v)} ${data.unit}${interval}`;
            },
          },
        },
      },
      scales: axes(p, size, data.unit, { compact: options.compact, horizontal: true }),
    },
    plugins: [barValues(p, size)],
  });
  chart.$items = { items, projectedByLabel };
  return chart;
}

/** A soft area line without axes, for headline cards. */
export function drawArea(canvas, values, color, options = {}) {
  const p = options.palette || paletteFrom();
  return new Chart(canvas, {
    type: "line",
    data: {
      labels: values.map((_, i) => i),
      datasets: [
        {
          data: values,
          borderColor: color,
          borderWidth: 2.5,
          tension: 0.35,
          pointRadius: values.map((_, i) => (i === values.length - 1 ? 4 : 0)),
          pointBackgroundColor: color,
          pointBorderColor: p.surface,
          pointBorderWidth: 2,
          fill: true,
          backgroundColor: (context) => {
            const { ctx, chartArea } = context.chart;
            if (!chartArea) return alpha(color, 0.15);
            const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
            gradient.addColorStop(0, alpha(color, 0.32));
            gradient.addColorStop(1, alpha(color, 0));
            return gradient;
          },
        },
      ],
    },
    options: {
      ...common(p, options),
      layout: { padding: { top: 6, bottom: 2, left: 2, right: 6 } },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false, grace: "8%" } },
    },
  });
}

export function sparkline(values, color, surface) {
  const w = 112;
  const hgt = 36;
  const pad = 4;
  const min = Math.min(...values);
  const range = Math.max(...values) - min || 1;
  const points = values.map((v, i) => [
    pad + (i / (values.length - 1 || 1)) * (w - 2 * pad),
    hgt - pad - ((v - min) / range) * (hgt - 2 * pad),
  ]);
  const line = points.map((pt, i) => `${i ? "L" : "M"}${pt[0].toFixed(1)} ${pt[1].toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  const area = `${line} L ${last[0].toFixed(1)} ${hgt - pad} L ${points[0][0].toFixed(1)} ${hgt - pad} Z`;
  return (
    `<svg class="spark" width="${w}" height="${hgt}" viewBox="0 0 ${w} ${hgt}" aria-hidden="true">` +
    `<path d="${area}" fill="${color}" opacity="0.12"/>` +
    `<path d="${line}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>` +
    `<circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3.8" fill="${color}" stroke="${surface}" stroke-width="2"/></svg>`
  );
}

function wrapText(ctx, text, width) {
  const lines = [];
  let line = "";
  for (const word of String(text).split(/\s+/)) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > width && line) {
      lines.push(line);
      line = word;
    } else line = next;
  }
  if (line) lines.push(line);
  return lines;
}

/**
 * A downloadable PNG drawn entirely in the browser: title, selection, the
 * chart on white, and the citation and provenance beneath it.
 */
export async function figureBlob(draw, { title, subtitle, footer = [], notice = "" }) {
  const width = 1600;
  const pad = 64;
  const chartHeight = 620;
  const plot = document.createElement("canvas");
  plot.width = width - 2 * pad;
  plot.height = chartHeight;
  const chart = draw(plot, { palette: LIGHT, responsive: false, animate: false, fontSize: 19, devicePixelRatio: 1 });
  chart.draw();

  const measure = document.createElement("canvas").getContext("2d");
  measure.font = `400 19px ${FONT}`;
  const lines = footer.flatMap((text) => wrapText(measure, text, width - 2 * pad));
  const height = 176 + chartHeight + 40 + (notice ? 36 : 0) + lines.length * 28 + pad;

  const out = document.createElement("canvas");
  out.width = width;
  out.height = height;
  const ctx = out.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#0f2942";
  ctx.fillRect(0, 0, width, 10);
  ctx.fillStyle = "#ffb500";
  ctx.fillRect(0, 10, width, 4);
  ctx.fillStyle = "#0f2942";
  ctx.font = `700 44px ${FONT}`;
  ctx.fillText(title, pad, 96);
  ctx.fillStyle = "#4d5561";
  ctx.font = `400 23px ${FONT}`;
  ctx.fillText(subtitle, pad, 136);
  ctx.drawImage(plot, pad, 176);
  let y = 176 + chartHeight + 40;
  if (notice) {
    ctx.fillStyle = "#b3261e";
    ctx.font = `700 19px ${FONT}`;
    ctx.fillText(notice, pad, y);
    y += 36;
  }
  ctx.fillStyle = "#4d5561";
  ctx.font = `400 19px ${FONT}`;
  for (const line of lines) {
    ctx.fillText(line, pad, y);
    y += 28;
  }
  chart.destroy();
  return new Promise((resolve) => out.toBlob(resolve, "image/png"));
}
