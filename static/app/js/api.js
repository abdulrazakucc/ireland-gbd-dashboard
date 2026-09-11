/*
 * Where results come from. Every view talks to one of these through the same
 * methods, so the application is identical whether it is served by the API
 * (a laptop or a server) or opened from the sealed copy on GitHub Pages.
 */

import { ApiError, AuthError } from "./errors.js";
import { fromB64, openBundle, requestKey, toB64, unlock } from "./sealed.js";

const present = (params = {}) =>
  Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));

class ServerSource {
  constructor() {
    this.kind = "server";
    this.capabilities = { pdf: true, yearRange: true, serverFigures: true };
  }

  url(route, params) {
    const query = new URLSearchParams(present(params)).toString();
    return `../api/${route}${query ? `?${query}` : ""}`;
  }

  async request(route, params) {
    let response;
    try {
      response = await fetch(this.url(route, params), { credentials: "same-origin", headers: { Accept: "application/json" } });
    } catch {
      throw new ApiError("The server could not be reached.");
    }
    if (response.status === 401) throw new AuthError("Your session has ended. Please sign in again.");
    if (!response.ok) {
      let detail = "";
      try {
        const body = await response.json();
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        /* not JSON */
      }
      throw new ApiError(detail || `The request failed (${response.status}).`, response.status);
    }
    return response.json();
  }

  session() {
    return this.request("auth/session");
  }

  async login(email, password) {
    let response;
    try {
      response = await fetch(this.url("auth/login"), {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email, password }),
      });
    } catch {
      throw new ApiError("The server could not be reached.");
    }
    let body = {};
    try {
      body = await response.json();
    } catch {
      /* no body */
    }
    if (response.ok) return body;
    const detail = typeof body.detail === "string" ? body.detail : "";
    if (response.status === 401 || response.status === 429) throw new AuthError(detail || "Email or password is incorrect.");
    throw new ApiError(detail || "Sign-in is unavailable right now.", response.status);
  }

  async logout() {
    await fetch(this.url("auth/logout"), { method: "POST", credentials: "same-origin" }).catch(() => {});
  }

  meta() { return this.request("meta"); }
  series() { return this.request("series"); }
  rankedOptions() { return this.request("ranked/options"); }
  trend(params) { return this.request("trend", params); }
  ranked(params) { return this.request("ranked", params); }

  /** A download address for the server-rendered file, or null. */
  href(kind, params) {
    return this.url({ csv: "export.csv", png: "figure.png", pdf: "figure.pdf" }[kind], params);
  }
}

const STORE = "gbd-sealed-session";

class SealedSource {
  constructor() {
    this.kind = "sealed";
    this.capabilities = { pdf: false, yearRange: false, serverFigures: false };
    this.bundle = null;
  }

  async session() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(STORE) || "null");
      if (saved) {
        this.bundle = await openBundle(fromB64(saved.key));
        return { authenticated: true, mode: "sealed", email: saved.email };
      }
    } catch {
      this.forget();
    }
    return { authenticated: false, mode: "sealed" };
  }

  async login(email, password) {
    const key = await unlock(email, password);
    this.bundle = await openBundle(key);
    const record = { email: email.trim().toLowerCase(), key: toB64(key) };
    try {
      // This tab only: closing it signs the reader out.
      sessionStorage.setItem(STORE, JSON.stringify(record));
    } catch {
      /* private mode: stay signed in until reload */
    }
    return { authenticated: true, mode: "sealed", email: record.email };
  }

  forget() {
    this.bundle = null;
    try {
      sessionStorage.removeItem(STORE);
    } catch {
      /* unavailable */
    }
  }

  async logout() {
    this.forget();
  }

  lookup(route, params = {}) {
    if (!this.bundle) throw new AuthError("Please sign in.");
    const key = requestKey(route, present(params));
    if (!(key in this.bundle.responses)) {
      throw new ApiError("That selection is not included in this published copy.", 404);
    }
    return structuredClone(this.bundle.responses[key]);
  }

  async meta() { return this.lookup("meta"); }
  async series() { return this.lookup("series"); }
  async rankedOptions() { return this.lookup("ranked/options"); }
  // A sealed copy holds whole series; year ranges are applied on the page.
  async trend({ year_from, year_to, ...params }) { return this.lookup("trend", params); }
  async ranked(params) { return this.lookup("ranked", params); }
  href() { return null; }
}

export function createSource(settings = {}) {
  return settings.mode === "sealed" ? new SealedSource() : new ServerSource();
}
