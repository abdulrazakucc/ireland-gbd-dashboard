/*
 * Opening the sealed copy of the results published on GitHub Pages.
 *
 * The build (scripts/build_static_site.py) encrypts every response the app can
 * ask for with one random AES-256-GCM key, and wraps that key once per account
 * with a key derived from the account's password: PBKDF2-HMAC-SHA256, the same
 * salt and iteration count as the users file. Here the browser repeats that
 * derivation from what the reader types. The right credentials unwrap the key
 * and decrypt the results; anything else fails the authentication tag and
 * reveals nothing. No password or email is ever sent anywhere.
 */

import { ApiError, AuthError } from "./errors.js";

const encoder = new TextEncoder();
const MAGIC = "GBDS1";
const CONTEXT = "gbd-sealed-v1";
const WRONG = "Email or password is incorrect.";

export const toB64 = (buffer) => btoa(String.fromCharCode(...new Uint8Array(buffer)));
export const fromB64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

/** The lookup key for one API request. Mirrors request_key() in the build. */
export function requestKey(route, params = {}) {
  const entries = Object.entries(params)
    .map(([name, value]) => [name, String(value)])
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return JSON.stringify([route, entries]);
}

async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function fetchOk(path) {
  let response;
  try {
    response = await fetch(path, { cache: "no-store" });
  } catch {
    throw new ApiError("The published results could not be loaded. Check your connection.");
  }
  if (!response.ok) throw new ApiError("The published results could not be loaded.", response.status);
  return response;
}

/** The results key, if these credentials belong to an account sealed into this copy. */
export async function unlock(email, password) {
  if (!window.isSecureContext || !window.crypto?.subtle || typeof DecompressionStream === "undefined") {
    throw new ApiError("This browser cannot open the protected results. Use a current version of Chrome, Edge, Firefox or Safari.");
  }
  const keys = await (await fetchOk("keys.json")).json();
  const id = await sha256Hex(`${CONTEXT}:${email.trim().toLowerCase()}`);
  const entry = keys.users.find((user) => user.id === id);
  const material = await crypto.subtle.importKey("raw", encoder.encode(password.normalize("NFKC")), "PBKDF2", false, ["deriveBits"]);
  // Derive even for an unknown email, so both kinds of failure take as long.
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt: entry ? fromB64(entry.salt) : new Uint8Array(16),
      iterations: entry ? entry.iterations : keys.iterations,
    },
    material,
    256,
  );
  if (!entry) throw new AuthError(WRONG);
  const wrappingKey = await crypto.subtle.importKey("raw", bits, "AES-GCM", false, ["decrypt"]);
  try {
    return await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: fromB64(entry.nonce), additionalData: encoder.encode(id) },
      wrappingKey,
      fromB64(entry.wrapped),
    );
  } catch {
    throw new AuthError(WRONG);
  }
}

/** Decrypt and decompress the results bundle with an unwrapped key. */
export async function openBundle(rawKey) {
  const bytes = new Uint8Array(await (await fetchOk("data.sealed")).arrayBuffer());
  if (new TextDecoder().decode(bytes.slice(0, MAGIC.length)) !== MAGIC) {
    throw new ApiError("The published results are in an unexpected format.");
  }
  const key = await crypto.subtle.importKey("raw", rawKey, "AES-GCM", false, ["decrypt"]);
  let plain;
  try {
    plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: bytes.slice(MAGIC.length, MAGIC.length + 12), additionalData: encoder.encode(CONTEXT) },
      key,
      bytes.slice(MAGIC.length + 12),
    );
  } catch {
    // The copy was republished with a new key since this browser signed in.
    throw new AuthError("The published results have been updated. Please sign in again.");
  }
  const stream = new Blob([plain]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}
