/**
 * Entry point and router. It shows the landing page or one room (a story chapter or the Fig. 1 debugger)
 * based on the URL hash, owns the single shared 3D stage, and wires the theme, motion and H-key controls.
 */
import { h, storeGet, storeSet, loadJson } from "./ui.js";
import { createStage } from "./three-stage.js";
import { pressH, progressText } from "./help-ladder.js";

const ROOMS = [
  { route: "story/1", module: "./chapters/ch1.js", title: "1 Two questions", task: "ch1-coins", blurb: "Two coins in two cities. Flip them 20 times and see when they agree." },
  { route: "story/2", module: "./chapters/ch2.js", title: "2 Planes and rivers", task: "ch2-links", blurb: "Drag q and watch seats appear on roads, then compare 30 rounds with the exact bars." },
  { route: "story/3", module: "./chapters/ch3.js", title: "3 The matchmaker", task: "ch3-swap", blurb: "Join two pairs at the middle city, then phone the ends so the new pair is usable." },
  { route: "story/4", module: "./chapters/ch4.js", title: "4 Paint mixing", task: "ch4-fidelity", blurb: "Add middle cities until the pair is too washed out to use." },
  { route: "story/5", module: "./chapters/ch5.js", title: "5 Rush hour", task: "ch5-rush", blurb: "Draw roads for three requests with limited seats, then allow splitting." },
  { route: "fig1", module: "./fig1.js", title: "Fig. 1 debugger", task: "fig1-walk", blurb: "Step through the paper's worked example, including the one value the paper misprints." },
];
const LATER = [
  { title: "Arena", blurb: "Single-path and multipath networks replay the same real trace side by side." },
  { title: "Code Lab", blurb: "Write your own choose_paths rule and let the referee score it." },
];

const els = {
  landing: document.getElementById("view-landing"),
  lab: document.getElementById("view-lab"),
  narrative: document.getElementById("narrative"),
  extra: document.getElementById("stage-extra"),
  stageHost: document.getElementById("stage"),
  roomList: document.getElementById("room-list"),
  error: document.getElementById("load-error"),
};
let stage = null;
let disposeRoom = null;
let routeToken = 0;

/**
 * Apply the Reduce motion checkbox and remember it.
 * @returns {void}
 */
function setupMotionToggle() {
  const box = document.getElementById("reduce-motion");
  box.checked = storeGet("quantumlab.reduceMotion", false);
  /** Set or clear the page-wide reduce-motion flag and save the choice. */
  const apply = () => {
    if (box.checked) {
      document.documentElement.dataset.motion = "reduce";
    } else {
      delete document.documentElement.dataset.motion;
    }
    storeSet("quantumlab.reduceMotion", box.checked);
  };
  box.addEventListener("change", apply);
  apply();
}

/**
 * Wire the theme button, which cycles match system, light, dark.
 * @returns {void}
 */
function setupThemeButton() {
  const order = ["auto", "light", "dark"];
  const names = { auto: "match system", light: "light", dark: "dark" };
  const button = document.getElementById("theme-button");
  let current = storeGet("quantumlab.theme", "auto");
  /** Set the theme attribute, update the button text, and tell the stage to redraw. */
  const apply = () => {
    if (current === "auto") {
      delete document.documentElement.dataset.theme;
    } else {
      document.documentElement.dataset.theme = current;
    }
    button.textContent = `Theme: ${names[current]}`;
    document.dispatchEvent(new Event("themechange"));
  };
  button.addEventListener("click", () => {
    current = order[(order.indexOf(current) + 1) % order.length];
    storeSet("quantumlab.theme", current);
    apply();
  });
  apply();
}

/**
 * Send the H key to the help ladder, unless the viewer is typing in a field.
 * @returns {void}
 */
function setupHelpKey() {
  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const typing = target instanceof HTMLElement && (target.matches("input[type=number], input[type=text], textarea, select"));
    if ((event.key === "h" || event.key === "H") && !event.ctrlKey && !event.metaKey && !event.altKey && !typing) {
      pressH();
    }
  });
}

/**
 * Fill the landing page's room list, including the progress of each task.
 * @returns {void}
 */
function renderLanding() {
  const rooms = ROOMS.map((r) => h("li", {},
    h("h3", {}, h("a", { href: `#/${r.route}`, text: r.title })),
    h("p", { text: r.blurb }),
    h("p", { class: "progress", text: `Progress: ${progressText(r.task)}` })));
  const later = LATER.map((r) => h("li", {},
    h("h3", {}, r.title, " ", h("span", { class: "status-later", text: "(coming next)" })),
    h("p", { text: r.blurb })));
  els.roomList.replaceChildren(...rooms, ...later);
}

/**
 * Add Previous and Next links under a story chapter.
 * @param {number} index Position of the room in ROOMS.
 * @returns {HTMLElement} The nav element.
 */
function roomNav(index) {
  const prev = ROOMS[index - 1];
  const next = ROOMS[index + 1];
  return h("nav", { class: "btn-row", "aria-label": "Chapter navigation" },
    prev ? h("a", { class: "btn", href: `#/${prev.route}`, text: `Previous: ${prev.title}` }) : null,
    next ? h("a", { class: "btn btn-primary", href: `#/${next.route}`, text: `Next: ${next.title}` }) : null);
}

/**
 * Show a plain error message instead of a room.
 * @param {string} message What went wrong and what to do.
 * @returns {void}
 */
function showError(message) {
  els.error.hidden = false;
  els.error.textContent = message;
}

/**
 * Show or hide the two views and mark the current nav link.
 * @param {string} route Current route without the leading "#/".
 * @returns {void}
 */
function setView(route) {
  const isLab = route !== "";
  els.landing.hidden = isLab;
  els.lab.hidden = !isLab;
  els.error.hidden = true;
  document.querySelectorAll(".site-nav a").forEach((a) => {
    if (a.dataset.route === route) {
      a.setAttribute("aria-current", "page");
    } else {
      a.removeAttribute("aria-current");
    }
  });
}

/**
 * Handle a route change: tear down the old room, then build the new one.
 * @returns {Promise<void>} Resolves when the room is on screen.
 */
async function navigate() {
  const route = window.location.hash.replace(/^#\/?/, "");
  const token = routeToken + 1;
  routeToken = token;
  if (disposeRoom) {
    disposeRoom();
    disposeRoom = null;
  }
  els.narrative.replaceChildren();
  els.extra.replaceChildren();
  setView(route);
  if (route === "") {
    document.title = "QuantumLab: multipath entanglement distribution";
    renderLanding();
    return;
  }
  const index = ROOMS.findIndex((r) => r.route === route);
  if (index < 0) {
    window.location.hash = "#/";
    return;
  }
  try {
    const room = (await import(ROOMS[index].module)).default;
    const hints = await loadJson("hints.json");
    if (token !== routeToken) {
      return;
    }
    stage = stage || createStage(els.stageHost);
    const cleanup = await room.mount({ narrative: els.narrative, extra: els.extra, stage, hints });
    if (token !== routeToken) {
      cleanup();
      return;
    }
    disposeRoom = cleanup;
    if (index < 5) {
      els.narrative.append(roomNav(index));
    }
    document.title = `${ROOMS[index].title} | QuantumLab`;
    const title = document.getElementById("room-title");
    if (title) { title.focus({ preventScroll: true }); }
    window.scrollTo(0, 0);
  } catch (error) {
    showError(`This room could not load (${error.message}). If you opened the file directly, serve the folder instead, `
      + "for example with python -m http.server, or use the GitHub Pages address.");
  }
}

setupMotionToggle();
setupThemeButton();
setupHelpKey();
document.getElementById("reset-view").addEventListener("click", () => { if (stage) { stage.resetView(); } });
window.addEventListener("hashchange", navigate);
navigate();
