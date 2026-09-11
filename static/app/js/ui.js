/* Small DOM toolkit: element builder, icons, and the reusable controls. */

export const $ = (selector, root = document) => root.querySelector(selector);

/** Build an element. Children may be nodes, strings, arrays, or null. */
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key === "html") el.innerHTML = value; // trusted markup only (icons)
    else if (key === "style") {
      for (const [name, v] of Object.entries(value)) el.style.setProperty(name, v);
    } else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

const PATHS = {
  overview: '<rect x="3" y="3" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2"/>',
  trends: '<path d="M3 17l5.5-5.5 4 4L21 7"/><path d="M15 7h6v6"/>',
  rankings: '<path d="M4 6h11M4 12h16M4 18h7"/>',
  methods: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"/><path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3"/><path d="M9 7.5h6"/>',
  present: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M10.5 8l3.5 2-3.5 2z"/><path d="M8 20h8M12 16v4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2.5M12 19.5V22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M2 12h2.5M19.5 12H22M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>',
  moon: '<path d="M20.5 13.2A8.5 8.5 0 1 1 10.8 3.5a6.8 6.8 0 0 0 9.7 9.7z"/>',
  logout: '<path d="M9 21H5.5A2.5 2.5 0 0 1 3 18.5v-13A2.5 2.5 0 0 1 5.5 3H9"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
  download: '<path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M5 21h14"/>',
  table: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9.5 10v10"/>',
  chart: '<path d="M4 20V11M10 20V4M16 20v-6M3 20h18"/>',
  forecast: '<path d="M12 2.8l1.9 5.3 5.3 1.9-5.3 1.9L12 17.2l-1.9-5.3L4.8 10l5.3-1.9z"/><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  left: '<path d="M15 18l-6-6 6-6"/>',
  right: '<path d="M9 18l6-6-6-6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5h.01"/>',
  up: '<path d="M12 19V5M5.5 11.5L12 5l6.5 6.5"/>',
  down: '<path d="M12 5v14M18.5 12.5L12 19l-6.5-6.5"/>',
  lock: '<rect x="4" y="10.5" width="16" height="10.5" rx="2.5"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M3 3l18 18"/><path d="M10.6 5.1A10.5 10.5 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.3 4.3M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7a10.4 10.4 0 0 0 5.4-1.5"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5.5A2.5 2.5 0 0 1 7.5 3H15"/>',
  arrow: '<path d="M5 12h14M13 5l7 7-7 7"/>',
  home: '<path d="M3 11.5L12 4l9 7.5"/><path d="M5.5 10v10h13V10"/>',
  shield: '<path d="M12 3l8 3v5.5c0 5-3.4 8.4-8 9.5-4.6-1.1-8-4.5-8-9.5V6z"/><path d="M9 12l2 2 4-4"/>',
  database: '<ellipse cx="12" cy="5.5" rx="8" ry="2.5"/><path d="M4 5.5v13c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-13"/><path d="M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5"/>',
  quote: '<path d="M9 7H5.5A1.5 1.5 0 0 0 4 8.5V12a1.5 1.5 0 0 0 1.5 1.5H8V17l-3 0"/><path d="M20 7h-3.5A1.5 1.5 0 0 0 15 8.5V12a1.5 1.5 0 0 0 1.5 1.5H19V17h-3"/>',
  expand: '<path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
};

export function icon(name, className = "icon") {
  return h("span", {
    class: className,
    "aria-hidden": "true",
    html: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${PATHS[name] || ""}</svg>`,
  });
}

let pillCount = 0;

/** A compact labelled choice. Disabled, but still shown, when there is only one value. */
export function pillSelect({ label, values, value, text = String, onChange, wide = false }) {
  const id = `pill-${++pillCount}`;
  const select = h("select", { id, disabled: values.length <= 1 });
  for (const v of values) select.add(new Option(text(v), v));
  select.value = String(value);
  select.title = text(value);
  select.addEventListener("change", () => onChange(select.value));
  return h(
    "label",
    { class: `pill${wide ? " wide" : ""}${values.length <= 1 ? " fixed" : ""}`, for: id },
    h("span", { class: "pill-label" }, label),
    select,
  );
}

export function segmented(options, value, onChange, label) {
  return h(
    "div",
    { class: "segmented", role: "group", "aria-label": label },
    options.map((option) =>
      h(
        "button",
        { type: "button", class: "seg", "aria-pressed": String(option.value === value), onClick: () => onChange(option.value) },
        option.icon ? icon(option.icon) : null,
        option.label,
      ),
    ),
  );
}

/** A button with a small pop-over list of actions. */
export function menu(content, items, { label, align = "end", className = "btn" } = {}) {
  const list = h("div", { class: `menu-list ${align}`, role: "menu", hidden: true });
  const button = h(
    "button",
    { type: "button", class: className, "aria-haspopup": "menu", "aria-expanded": "false", "aria-label": label },
    content,
  );
  const close = () => {
    list.hidden = true;
    button.setAttribute("aria-expanded", "false");
  };
  for (const item of items.filter(Boolean)) {
    list.append(
      h(
        "button",
        { type: "button", role: "menuitem", class: "menu-item", onClick: () => { close(); item.onSelect(); } },
        item.icon ? icon(item.icon) : null,
        h("span", { class: "menu-text" }, h("strong", {}, item.label), item.hint ? h("small", {}, item.hint) : null),
      ),
    );
  }
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    const opening = list.hidden;
    closeMenus();
    list.hidden = !opening;
    button.setAttribute("aria-expanded", String(opening));
  });
  return h("div", { class: "menu" }, button, list);
}

export function closeMenus() {
  for (const list of document.querySelectorAll(".menu-list:not([hidden])")) {
    list.hidden = true;
    list.previousElementSibling?.setAttribute("aria-expanded", "false");
  }
}
document.addEventListener("click", closeMenus);
document.addEventListener("keydown", (event) => event.key === "Escape" && closeMenus());

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  downloadUrl(url, filename);
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export function downloadUrl(href, filename) {
  const link = h("a", { href, download: filename, hidden: true });
  document.body.append(link);
  link.click();
  link.remove();
}

export function toast(message, kind = "info") {
  const host = document.getElementById("toasts");
  if (!host) return;
  const note = h("div", { class: `toast ${kind}`, role: kind === "error" ? "alert" : "status" }, icon(kind === "error" ? "info" : "shield"), h("span", {}, message));
  host.append(note);
  setTimeout(() => note.classList.add("leaving"), 4200);
  setTimeout(() => note.remove(), 4700);
}
