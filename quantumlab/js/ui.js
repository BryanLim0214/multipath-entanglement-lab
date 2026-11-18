/**
 * Small page helpers used by every room: an element builder, safe storage, captions with the "?" button,
 * the "predict, then see" box, the reduce-motion switch, and a cached JSON loader.
 */

/**
 * Build a DOM element. Keys in attrs set properties or attributes; children are nodes or strings.
 * @param {string} tag Tag name, such as "p" or "button".
 * @param {Object<string, *>} [attrs] Properties: class, text, on* handlers, aria-* and data-* attributes.
 * @param {...(Node|string|null)} children Child nodes or text.
 * @returns {HTMLElement} The new element.
 */
export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) {
      continue;
    }
    if (key === "class") {
      node.className = value;
    } else if (key === "text") {
      node.textContent = value;
    } else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2), value);
    } else if (key === "role" || key.startsWith("aria-") || key.startsWith("data-")) {
      node.setAttribute(key, value);
    } else if (key in node && key !== "list") {
      node[key] = value;
    } else {
      node.setAttribute(key, value === true ? "" : value);
    }
  }
  for (const child of children) {
    if (child !== null && child !== undefined) {
      node.append(child);
    }
  }
  return node;
}

/**
 * Read a value from localStorage; returns the fallback if storage is blocked or empty.
 * @param {string} key Storage key.
 * @param {*} fallback Value to return on any failure.
 * @returns {*} Parsed JSON value or the fallback.
 */
export function storeGet(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch (error) {
    return fallback;
  }
}

/**
 * Write a value to localStorage; silently does nothing if storage fails.
 * @param {string} key Storage key.
 * @param {*} value Any JSON-friendly value.
 * @returns {boolean} True if the value was saved.
 */
export function storeSet(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Whether motion should be skipped: the page toggle or the system setting.
 * @returns {boolean} True when animations must be replaced by instant changes.
 */
export function motionReduced() {
  return document.documentElement.dataset.motion === "reduce"
    || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Say something to screen readers through the page's polite live region.
 * @param {string} text Message to announce.
 * @returns {void}
 */
export function announce(text) {
  const region = document.getElementById("live");
  if (region) {
    region.textContent = "";
    window.setTimeout(() => { region.textContent = text; }, 30);
  }
}

const jsonCache = new Map();

/**
 * Fetch a JSON file from data/ once and reuse it.
 * @param {string} name File name inside data/, such as "hints.json".
 * @returns {Promise<*>} Parsed JSON.
 */
export async function loadJson(name) {
  if (!jsonCache.has(name)) {
    const url = new URL(`../data/${name}`, import.meta.url);
    jsonCache.set(name, fetch(url).then((response) => {
      if (!response.ok) {
        throw new Error(`Could not load ${name} (HTTP ${response.status}).`);
      }
      return response.json();
    }));
  }
  return jsonCache.get(name);
}

/**
 * A caption: the kid line and the student line always show; the "?" button reveals the expert line
 * and the note on where the analogy breaks.
 * @param {{kid: string, student: string, expert: string, breaks: string}} lines The four texts.
 * @returns {HTMLElement} The caption element.
 */
export function caption({ kid, student, expert, breaks }) {
  const panel = h("div", { class: "caption-expert", hidden: true },
    h("p", {}, h("span", { class: "line-label", text: "Expert" }), expert),
    h("p", {}, h("span", { class: "line-label", text: "Where this breaks" }), breaks));
  const button = h("button", {
    class: "btn btn-small btn-help",
    type: "button",
    text: "?",
    "aria-expanded": "false",
    "aria-label": "Show the expert line and where this picture breaks",
    onclick: () => {
      const open = panel.hidden;
      panel.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
    },
  });
  return h("div", { class: "caption" },
    h("p", {}, h("span", { class: "line-label", text: "Kid" }), kid),
    h("p", {}, h("span", { class: "line-label", text: "Student" }), student, " ", button),
    panel);
}

/**
 * "Predict, then see": radio buttons the viewer must answer before the action runs.
 * The caller gates its action button with box.ready() and reports the outcome with box.reveal().
 * @param {{name: string, legend: string, options: {value: string, label: string}[], onChange?: function(): void}} spec Question setup.
 * @returns {{element: HTMLElement, ready: function(): boolean, value: function(): (string|null), reveal: function(string, string): void, reset: function(): void, clearChoice: function(): void}} Handle.
 */
export function predictBox({ name, legend, options, onChange }) {
  const verdict = h("p", { class: "verdict", hidden: true, role: "status" });
  const inputs = options.map((o) => h("input", {
    type: "radio", name, value: o.value, onchange: () => { if (onChange) { onChange(); } },
  }));
  const fieldset = h("fieldset", {},
    h("legend", { text: `Predict first: ${legend}` }),
    ...options.map((o, i) => h("label", { class: "choice" }, inputs[i], o.label)));
  /**
   * The chosen option.
   * @returns {string|null} Value of the checked radio, or null.
   */
  const value = () => (inputs.find((i) => i.checked) || {}).value || null;
  return {
    element: h("div", {}, fieldset, verdict),
    /**
     * Whether the viewer has made a guess.
     * @returns {boolean} True if a radio is checked.
     */
    ready: () => value() !== null,
    value,
    /**
     * Show whether the guess was right, with an explanation.
     * @param {string} actual The correct option value.
     * @param {string} explanation One or two plain sentences.
     * @returns {void}
     */
    reveal(actual, explanation) {
      const right = value() === actual;
      verdict.hidden = false;
      verdict.className = `verdict ${right ? "is-right" : "is-wrong"}`;
      verdict.textContent = `${right ? "You guessed right." : "Not this time."} ${explanation}`;
      announce(verdict.textContent);
    },
    /**
     * Clear the guess and hide the verdict.
     * @returns {void}
     */
    reset() {
      inputs.forEach((i) => { i.checked = false; });
      verdict.hidden = true;
    },
    /**
     * Clear the radios but keep the verdict visible, so the next run needs a new guess.
     * @returns {void}
     */
    clearChoice() {
      inputs.forEach((i) => { i.checked = false; });
    },
  };
}

/**
 * Format a number with a fixed count of decimals, for tables and meters.
 * @param {number} x The number.
 * @param {number} [digits] Decimal places.
 * @returns {string} Text such as "0.78".
 */
export function fixed(x, digits = 2) {
  return x.toFixed(digits);
}
