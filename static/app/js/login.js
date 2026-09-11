/* The sign-in screen: the same on a laptop, a server, and the sealed Pages copy. */

import { h, icon } from "./ui.js";

export function renderLogin(root, { source, onSignedIn, notice = "" }) {
  const sealed = source.kind === "sealed";
  const error = h("p", { class: "login-error", role: "alert", hidden: !notice }, notice);
  const email = h("input", {
    id: "login-email",
    type: "email",
    name: "email",
    autocomplete: "username",
    inputmode: "email",
    required: true,
    placeholder: "name@organisation.org",
  });
  const password = h("input", {
    id: "login-password",
    type: "password",
    name: "password",
    autocomplete: "current-password",
    required: true,
    placeholder: "Your password",
  });
  const reveal = h("button", { type: "button", class: "reveal", "aria-label": "Show password", "aria-pressed": "false" }, icon("eye"));
  reveal.addEventListener("click", () => {
    const show = password.type === "password";
    password.type = show ? "text" : "password";
    reveal.setAttribute("aria-pressed", String(show));
    reveal.setAttribute("aria-label", show ? "Hide password" : "Show password");
    reveal.replaceChildren(icon(show ? "eyeOff" : "eye"));
    password.focus();
  });
  const label = h("span", {}, "Sign in");
  const submit = h("button", { type: "submit", class: "btn primary block" }, label, icon("arrow"));

  const form = h(
    "form",
    { class: "login-form", novalidate: true },
    h(
      "div",
      { class: "login-head" },
      h("span", { class: "badge" }, icon("lock"), "Approved users"),
      h("h2", {}, "Welcome back"),
      h("p", {}, "Sign in to explore the results."),
    ),
    h("label", { class: "field", for: "login-email" }, h("span", {}, "Email"), email),
    h("label", { class: "field", for: "login-password" }, h("span", {}, "Password"), h("div", { class: "password" }, password, reveal)),
    error,
    submit,
    h(
      "p",
      { class: "login-note" },
      icon("shield"),
      sealed
        ? "Results are decrypted on this device. Your password never leaves the browser."
        : "Your password is checked securely and never stored in the browser.",
    ),
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    if (!email.value.trim() || !password.value) {
      error.textContent = "Enter your email and password.";
      error.hidden = false;
      return;
    }
    submit.disabled = true;
    submit.classList.add("busy");
    label.textContent = sealed ? "Unlocking results…" : "Signing in…";
    try {
      const session = await source.login(email.value, password.value);
      password.value = "";
      onSignedIn(session);
    } catch (failure) {
      error.textContent = failure.message || "Sign-in failed. Try again.";
      error.hidden = false;
      password.select();
    } finally {
      submit.disabled = false;
      submit.classList.remove("busy");
      label.textContent = "Sign in";
    }
  });

  const brand = h(
    "section",
    { class: "login-brand" },
    h("a", { class: "login-home", href: "../" }, icon("left"), "Home"),
    h(
      "div",
      { class: "login-story" },
      h("img", { class: "login-logo", src: "../assets/ucc-logo.png", alt: "University College Cork" }),
      h("p", { class: "eyebrow" }, "School of Public Health"),
      h("h1", {}, "Global Health", h("br"), h("span", {}, "Evidence")),
      h("p", { class: "lead" }, "Global Burden of Disease estimates, presented with clarity — trends, leading causes and risks, and transparent forecasts."),
      h(
        "ul",
        { class: "login-points" },
        [
          ["trends", "Trends with 95% uncertainty intervals"],
          ["rankings", "Leading causes and risk factors"],
          ["present", "Presentation mode for talks and teaching"],
        ].map(([name, text]) => h("li", {}, icon(name), text)),
      ),
    ),
    h(
      "div",
      { class: "login-pi" },
      h("img", { src: "../assets/zubair-kabir.png", alt: "" }),
      h("div", {}, h("strong", {}, "Dr. Zubair Kabir"), h("span", {}, "Principal Investigator · University College Cork")),
    ),
  );

  root.replaceChildren(h("div", { class: "login" }, brand, h("section", { class: "login-panel" }, form)));
  email.focus();
}
