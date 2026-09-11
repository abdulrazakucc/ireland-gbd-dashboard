/*
 * The application shell: sign-in, the workspace frame, and navigation.
 *
 * Views are registered below. Adding an analysis means writing one module with
 * { id, label, icon, mount, unmount, redraw } and adding it to VIEWS -- the
 * navigation, deep links and presentation mode pick it up from there.
 */

import { createSource } from "./api.js";
import { ApiError, AuthError } from "./errors.js";
import { fmtDate, initials } from "./format.js";
import { renderLogin } from "./login.js";
import { openPresentation } from "./present.js";
import { $, h, icon, toast } from "./ui.js";
import methods from "./views/methods.js";
import overview from "./views/overview.js";
import rankings from "./views/rankings.js";
import trends from "./views/trends.js";

const VIEWS = [overview, trends, rankings, methods];
const root = document.getElementById("root");
const source = createSource(window.GBD_APP);
const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

const app = {
  source,
  session: null,
  meta: null,
  catalogue: [],
  rankOptions: [],
  memory: {}, // selections each view keeps while the reader moves between views
  current: null,

  navigate(id, params = {}) {
    location.hash = routeHash(id, params);
  },
  replaceParams(params) {
    if (app.current) history.replaceState(null, "", routeHash(app.current.id, params));
  },
  setHeader(title, subtitle = "") {
    const heading = $("#viewTitle");
    if (!heading) return;
    heading.textContent = title;
    $("#viewSubtitle").textContent = subtitle;
  },
  present() {
    openPresentation(app).catch(fail);
  },
  fail,
};

function routeHash(id, params) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""),
  ).toString();
  return `#/${id}${query ? `?${query}` : ""}`;
}

function parseRoute() {
  const [path, query] = location.hash.replace(/^#\/?/, "").split("?");
  return {
    view: VIEWS.find((view) => view.id === path) || VIEWS[0],
    params: Object.fromEntries(new URLSearchParams(query || "")),
  };
}

/* ---- failure handling ------------------------------------------------- */

function stateScreen(title, message, action) {
  return h(
    "div",
    { class: "state-screen" },
    h("div", { class: "state-card" }, icon("info"), h("h2", {}, title), h("p", {}, message), action || null),
  );
}

function fail(error) {
  if (error instanceof AuthError) {
    showLogin(error.message);
    return;
  }
  console.error(error);
  const message = error instanceof ApiError ? error.message : "Something went wrong while loading this view.";
  const container = $("#view");
  if (container) {
    container.replaceChildren(
      stateScreen("This view could not be loaded", message, h("button", { type: "button", class: "btn primary", onClick: route }, "Try again")),
    );
  } else {
    root.replaceChildren(
      stateScreen("Global Health Evidence is unavailable", message, h("button", { type: "button", class: "btn primary", onClick: () => location.reload() }, "Reload")),
    );
  }
}

/* ---- sign-in ---------------------------------------------------------- */

function teardown() {
  if (app.current?.unmount) app.current.unmount();
  app.current = null;
  window.removeEventListener("hashchange", route);
}

function showLogin(notice = "") {
  teardown();
  document.title = "Sign in · Global Health Evidence";
  renderLogin(root, { source, notice, onSignedIn: startWorkspace });
}

async function signOut() {
  await source.logout();
  app.session = null;
  app.memory = {};
  history.replaceState(null, "", location.pathname);
  showLogin();
  toast("You have signed out.");
}

/* ---- workspace -------------------------------------------------------- */

async function startWorkspace(session) {
  app.session = session;
  root.replaceChildren(h("div", { class: "boot" }, h("div", { class: "spinner" }), h("p", {}, "Preparing your workspace…")));
  try {
    [app.meta, app.catalogue, app.rankOptions] = await Promise.all([source.meta(), source.series(), source.rankedOptions()]);
  } catch (error) {
    fail(error);
    return;
  }
  if (!app.catalogue.length) {
    root.replaceChildren(stateScreen("No results yet", "The loaded dataset contains no estimates. Import a GBD export to begin."));
    return;
  }
  renderShell();
  window.addEventListener("hashchange", route);
  route();
}

function renderShell() {
  const { meta, session } = app;
  const signedOutPossible = session.mode === "password" || session.mode === "sealed";
  const who = session.email || (session.mode === "off" ? "Sign-in is switched off" : "Signed in");

  const nav = h(
    "nav",
    { class: "nav", "aria-label": "Sections" },
    h("span", { class: "nav-label" }, "Explore"),
    VIEWS.map((view) => h("a", { class: "nav-item", href: `#/${view.id}`, "data-view": view.id }, icon(view.icon), h("span", {}, view.label))),
  );
  const sidebar = h(
    "aside",
    { class: "sidebar", id: "sidebar" },
    h(
      "a",
      { class: "brand", href: "#/overview" },
      h("img", { class: "brand-logo", src: "../assets/ucc-logo.png", alt: "University College Cork" }),
      h("span", { class: "brand-text" }, h("strong", {}, "Global Health Evidence"), h("span", {}, "School of Public Health")),
    ),
    nav,
    h(
      "div",
      { class: "sidebar-foot" },
      h(
        "div",
        { class: "dataset-card" },
        h("span", { class: "dataset-label" }, "Dataset"),
        h("strong", {}, meta.release),
        h("span", {}, `${meta.year_min}–${meta.year_max} · updated ${fmtDate(meta.imported_at)}`),
        meta.prototype ? h("span", { class: "flag", title: meta.notice }, "Prototype data · not for citation") : null,
      ),
      h(
        "div",
        { class: "user-card" },
        h("span", { class: "avatar", "aria-hidden": "true" }, initials(session.name || session.email || "UCC")),
        h("div", { class: "user-text" }, h("strong", {}, session.name || "Signed in"), h("span", { title: who }, who)),
        signedOutPossible
          ? h("button", { type: "button", class: "icon-btn on-dark", title: "Sign out", "aria-label": "Sign out", onClick: signOut }, icon("logout"))
          : null,
      ),
    ),
  );

  const topbar = h(
    "header",
    { class: "topbar" },
    h("button", { type: "button", class: "icon-btn menu-toggle", "aria-label": "Open navigation", "aria-controls": "sidebar", "aria-expanded": "false", onClick: toggleNav }, icon("layers")),
    h("div", { class: "topbar-title" }, h("h1", { id: "viewTitle", tabindex: "-1" }), h("p", { id: "viewSubtitle" })),
    h(
      "div",
      { class: "topbar-actions" },
      h("button", { type: "button", class: "icon-btn", id: "themeToggle", onClick: toggleTheme }),
      h("button", { type: "button", class: "btn present-btn", title: "Present (P)", onClick: () => app.present() }, icon("present"), h("span", {}, "Present")),
    ),
  );

  root.replaceChildren(h("div", { class: "shell" }, sidebar, h("div", { class: "main" }, topbar, h("main", { class: "view", id: "view" }))));
  syncThemeButton();
}

let generation = 0;

async function route() {
  const container = $("#view");
  if (!container) return;
  const { view, params } = parseRoute();
  if (app.current?.unmount) app.current.unmount();
  app.current = view;
  for (const link of document.querySelectorAll(".nav-item")) {
    if (link.dataset.view === view.id) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  document.title = `${view.label} · Global Health Evidence`;
  closeNav();
  container.replaceChildren();
  const mine = ++generation;
  try {
    await view.mount(container, app, params);
  } catch (error) {
    if (mine === generation) fail(error);
  }
  $("#viewTitle")?.focus({ preventScroll: true });
}

/* ---- appearance and navigation chrome ---------------------------------- */

const currentTheme = () => document.documentElement.dataset.theme || (darkQuery.matches ? "dark" : "light");

function syncThemeButton() {
  const button = $("#themeToggle");
  if (!button) return;
  const dark = currentTheme() === "dark";
  button.replaceChildren(icon(dark ? "sun" : "moon"));
  button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  button.title = dark ? "Light mode" : "Dark mode";
}

function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem("ucc-gbd-theme", next);
  } catch {
    /* storage unavailable */
  }
  syncThemeButton();
  app.current?.redraw?.();
}

darkQuery.addEventListener("change", () => {
  syncThemeButton();
  app.current?.redraw?.();
});

function toggleNav() {
  const sidebar = $("#sidebar");
  const open = !sidebar.classList.contains("open");
  sidebar.classList.toggle("open", open);
  $(".menu-toggle")?.setAttribute("aria-expanded", String(open));
}

function closeNav() {
  $("#sidebar")?.classList.remove("open");
  $(".menu-toggle")?.setAttribute("aria-expanded", "false");
}

document.addEventListener("keydown", (event) => {
  const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(event.target.tagName);
  if (!typing && !event.metaKey && !event.ctrlKey && event.key.toLowerCase() === "p" && app.current && !document.querySelector(".present")) {
    app.present();
  }
});

async function boot() {
  let session;
  try {
    session = await source.session();
  } catch (error) {
    fail(error);
    return;
  }
  if (session.authenticated) await startWorkspace(session);
  else showLogin();
}

boot();
