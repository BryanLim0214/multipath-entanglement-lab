/**
 * The shared 3D stage. A room describes a small network (cities, links, markers) and the stage draws it:
 * matte spheres for cities, tubes whose radius is proportional to seats, and small beads for pairs.
 * Labels are HTML elements placed over the canvas. The scene only redraws when something changes.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { motionReduced } from "./ui.js";

const NODE_RADIUS = 0.4;
const TUBE_PER_SEAT = 0.04; // tube radius is proportional to seats
const BEAD_RADIUS = 0.13;
const MARKER_SIZE = 0.3;
const FOV = 40;
const VIEW_DIRECTION = new THREE.Vector3(0, -0.45, 0.9).normalize();
const TOP_VIEW_DIRECTION = new THREE.Vector3(0, -0.04, 1).normalize(); // nearly straight down, so rows are not squashed

/**
 * Read a color token (such as "mp") from the page's CSS, or pass a "#rrggbb" value straight through.
 * @param {string} name Token name without the leading dashes, or a hex color.
 * @returns {string} A CSS color string.
 */
export function tokenColor(name) {
  if (name.startsWith("#")) {
    return name;
  }
  return getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim() || "#888888";
}

/**
 * Color on the single fidelity ramp: teal at F = 0.95 and above, amber in the middle, red at F = 0.25.
 * @param {number} fidelity Fidelity between 0.25 and 1.
 * @returns {string} A "#rrggbb" color.
 */
export function rampColor(fidelity) {
  const share = Math.min(1, Math.max(0, (0.95 - fidelity) / (0.95 - 0.25)));
  const stops = [tokenColor("ramp-0"), tokenColor("ramp-1"), tokenColor("ramp-2")].map((c) => new THREE.Color(c));
  const out = new THREE.Color();
  if (share < 0.5) {
    out.lerpColors(stops[0], stops[1], share * 2);
  } else {
    out.lerpColors(stops[1], stops[2], (share - 0.5) * 2);
  }
  return `#${out.getHexString()}`;
}

/**
 * Offset for a small link label: half a unit to one fixed side of the link (above a horizontal link, right of a vertical one).
 * @param {THREE.Vector3} a One end of the link.
 * @param {THREE.Vector3} b The other end.
 * @returns {{x: number, y: number}} Scene offset from the link's midpoint.
 */
function sideOffset(a, b) {
  const length = Math.hypot(b.x - a.x, b.y - a.y) || 1;
  let nx = -(b.y - a.y) / length;
  let ny = (b.x - a.x) / length;
  if (ny < -1e-6 || (Math.abs(ny) <= 1e-6 && nx < 0)) {
    nx = -nx;
    ny = -ny;
  }
  return { x: nx * 0.5, y: ny * 0.5 };
}

/**
 * Smooth stop at the end of a motion (ease-out cubic).
 * @param {number} t Progress from 0 to 1.
 * @returns {number} Eased progress from 0 to 1.
 */
function easeOut(t) {
  return 1 - (1 - t) ** 3;
}

/**
 * A stage that does nothing, used when the browser cannot start WebGL.
 * @param {HTMLElement} host The stage container, which receives a plain-text message.
 * @returns {object} An object with the same methods as the real stage.
 */
function fallbackStage(host) {
  host.replaceChildren();
  const note = document.createElement("p");
  note.className = "stage-fallback";
  note.textContent = "Your browser could not start 3D graphics, so the picture is missing. "
    + "Everything in the text, tables and buttons on this page still works.";
  host.append(note);
  /** Does nothing. */
  const noop = () => {};
  return {
    show: noop, pulse: noop, moveMarker: noop, setAlt: noop, resetView: noop,
    /**
     * Run the last frame at once.
     * @param {number} ms Ignored.
     * @param {function(number): void} fn Draw function.
     * @returns {Promise<void>} Already resolved.
     */
    tween: (ms, fn) => { fn(1); return Promise.resolve(); },
  };
}

/**
 * Create the stage inside a container.
 * @param {HTMLElement} host Empty element with a fixed height (the .stage box).
 * @returns {{show: function(object): void, pulse: function(string): Promise<void>, moveMarker: function(string, number, number, number): void, setAlt: function(string): void, resetView: function(): void, tween: function(number, function(number): void): Promise<void>}} Stage API.
 */
export function createStage(host) {
  const canvas = document.createElement("canvas");
  canvas.tabIndex = 0;
  canvas.setAttribute("role", "img");
  const labels = document.createElement("div");
  labels.className = "stage-labels";
  host.replaceChildren(canvas, labels);

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  } catch (error) {
    return fallbackStage(host);
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 200);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8a8a, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.5);
  sun.position.set(3, -4, 8);
  scene.add(sun);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false; // damping needs a running loop; we only draw on change
  controls.listenToKeyEvents(canvas);
  controls.addEventListener("change", () => render());

  let content = new THREE.Group();
  scene.add(content);
  const state = { nodes: new Map(), markers: new Map(), labelItems: [], lastSpec: null, fitKey: "", view: VIEW_DIRECTION };

  /** Move every HTML label to where its 3D point is on screen. */
  function placeLabels() {
    const w = host.clientWidth;
    const h = host.clientHeight;
    for (const item of state.labelItems) {
      const p = item.point.clone().project(camera);
      const x = (p.x * 0.5 + 0.5) * w;
      const y = (-p.y * 0.5 + 0.5) * h;
      const down = item.center ? "calc(" + y.toFixed(1) + "px - 50%)" : `${y.toFixed(1)}px`;
      item.el.style.transform = `translate(calc(${x.toFixed(1)}px - 50%), ${down})`;
    }
  }

  /** Draw the scene once and update labels. */
  function render() {
    renderer.render(scene, camera);
    placeLabels();
  }

  /**
   * Point the camera at the nodes so all of them fit.
   * @param {{x: number, y: number}[]} nodes Node positions.
   * @param {number} [pad] Extra scene units kept free around the nodes.
   * @returns {void}
   */
  function fitCamera(nodes, pad = 1.3) {
    if (nodes.length === 0) {
      return;
    }
    const xs = nodes.map((n) => n.x);
    const ys = nodes.map((n) => n.y);
    const halfW = (Math.max(...xs) - Math.min(...xs)) / 2 + pad;
    const halfH = (Math.max(...ys) - Math.min(...ys)) / 2 + pad;
    const center = new THREE.Vector3((Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2, 0);
    const need = Math.max(halfH / 0.9, halfW / camera.aspect) / Math.tan((FOV * Math.PI) / 360);
    controls.target.copy(center);
    camera.position.copy(center).addScaledVector(state.view, need);
    camera.lookAt(center);
    controls.update();
  }

  /**
   * Free the GPU memory of everything in the current content group.
   * @returns {void}
   */
  function disposeContent() {
    content.traverse((obj) => {
      if (obj.geometry) {
        obj.geometry.dispose();
      }
      if (obj.material) {
        obj.material.dispose();
      }
    });
    scene.remove(content);
    content = new THREE.Group();
    scene.add(content);
    state.nodes.clear();
    state.markers.clear();
    state.labelItems = [];
    labels.replaceChildren();
  }

  /**
   * Make a matte material.
   * @param {string} color Token name or hex.
   * @returns {THREE.MeshStandardMaterial} The material.
   */
  function matte(color) {
    return new THREE.MeshStandardMaterial({ color: new THREE.Color(tokenColor(color)), roughness: 1, metalness: 0 });
  }

  /**
   * Add an HTML label that follows a 3D point.
   * @param {HTMLElement} el The label element.
   * @param {THREE.Vector3} point Where it sits in the scene.
   * @param {boolean} [center] True to centre the label on the point instead of hanging it below.
   * @returns {void}
   */
  function addLabel(el, point, center = false) {
    labels.append(el);
    state.labelItems.push({ el, point, center });
  }

  /**
   * Build a node: a sphere plus its HTML label (a button when it has a click handler).
   * @param {object} n Node spec: id, x, y, label, color, picked, onClick, title, hint, tabless.
   * @returns {void}
   */
  function addNode(n) {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(NODE_RADIUS, 32, 16), matte(n.color || "ink"));
    mesh.position.set(n.x, n.y, 0);
    content.add(mesh);
    state.nodes.set(n.id, mesh);
    const el = document.createElement(n.onClick ? "button" : "span");
    el.className = `node-label${n.picked ? " is-picked" : ""}${n.onNode ? " is-tight" : ""}`;
    el.textContent = n.label ?? String(n.id);
    if (n.onClick) {
      el.type = "button";
      el.addEventListener("click", () => n.onClick(n.id));
    }
    if (n.title) {
      el.setAttribute("aria-label", n.title);
    }
    if (n.hint) {
      el.classList.add("hint-target");
    }
    if (n.onClick && n.tabless) {
      el.tabIndex = -1;
      el.setAttribute("aria-hidden", "true");
    }
    if (n.onNode) {
      addLabel(el, new THREE.Vector3(n.x, n.y, NODE_RADIUS), true); // tag sits on the sphere, away from every link label
    } else {
      addLabel(el, new THREE.Vector3(n.x, n.y - NODE_RADIUS - 0.55, 0));
    }
  }

  /**
   * Build a link: a tube (radius proportional to seats), optional beads, and an optional label.
   * @param {object} l Link spec: from, to, seats, color, beads, beadColor, arc, lift, label, note, labelShift (scene x and y offset of the label).
   * @param {Map<*, object>} nodeSpecs Node specs by id.
   * @returns {void}
   */
  function addLink(l, nodeSpecs) {
    const a = nodeSpecs.get(l.from);
    const b = nodeSpecs.get(l.to);
    const lift = l.lift || 0; // lifted tubes float above the plane, used to show a suggested answer
    const p0 = new THREE.Vector3(a.x, a.y, lift);
    const p1 = new THREE.Vector3(b.x, b.y, lift);
    const curve = l.arc
      ? new THREE.QuadraticBezierCurve3(p0, p0.clone().lerp(p1, 0.5).add(new THREE.Vector3(0, l.arc, 0.8)), p1)
      : new THREE.LineCurve3(p0, p1);
    const radius = l.seats * TUBE_PER_SEAT;
    if (radius > 0) {
      content.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 32, radius, 12, false), matte(l.color || "muted")));
    }
    const beads = l.beads || 0;
    for (let i = 0; i < beads; i += 1) {
      const bead = new THREE.Mesh(new THREE.SphereGeometry(BEAD_RADIUS, 16, 12), matte(l.beadColor || "ink"));
      bead.position.copy(curve.getPoint((i + 1) / (beads + 1))).add(new THREE.Vector3(0, 0, radius + BEAD_RADIUS * 0.8));
      content.add(bead);
    }
    if (l.label) {
      const el = document.createElement("span");
      el.className = `link-label${l.note ? " is-note" : ""}${l.small ? " is-small" : ""}`;
      el.textContent = l.label;
      const mid = curve.getPoint(0.5);
      const shift = l.labelShift || (l.small ? sideOffset(p0, p1) : { x: 0, y: l.note ? 0.4 : 0.55 });
      addLabel(el, mid.add(new THREE.Vector3(shift.x, shift.y, radius)));
    }
  }

  /**
   * Build a marker: a small cube, used for a message or an attempt in flight.
   * @param {object} m Marker spec: id, x, y, z, color.
   * @returns {void}
   */
  function addMarker(m) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(MARKER_SIZE, MARKER_SIZE, MARKER_SIZE), matte(m.color || "ink"));
    mesh.position.set(m.x, m.y, m.z ?? 0.6);
    content.add(mesh);
    state.markers.set(m.id, mesh);
  }

  /**
   * Add a plain text title at a scene position (used by the Arena to name each network).
   * @param {{x: number, y: number, text: string}} c Caption spec.
   * @returns {void}
   */
  function addCaption(c) {
    const el = document.createElement("span");
    el.className = "stage-title";
    el.textContent = c.text;
    addLabel(el, new THREE.Vector3(c.x, c.y, 0));
  }

  /**
   * Draw a whole picture, replacing the old one.
   * @param {{nodes: object[], links?: object[], markers?: object[], captions?: object[], pad?: number, view?: string}} spec The picture (pad is the free margin round the nodes, default 1.3; view "top" looks straight down). Node flag onNode puts the tag on the sphere; link flag small makes the label smaller.
   * @returns {void}
   */
  function show(spec) {
    state.lastSpec = spec;
    state.view = spec.view === "top" ? TOP_VIEW_DIRECTION : VIEW_DIRECTION;
    disposeContent();
    scene.background = new THREE.Color(tokenColor("paper"));
    const nodeSpecs = new Map(spec.nodes.map((n) => [n.id, n]));
    (spec.links || []).forEach((l) => addLink(l, nodeSpecs));
    spec.nodes.forEach(addNode);
    (spec.markers || []).forEach(addMarker);
    (spec.captions || []).forEach(addCaption);
    const key = spec.nodes.map((n) => `${n.id}:${n.x}:${n.y}`).join("|") + (spec.view || "");
    if (key !== state.fitKey) {
      state.fitKey = key;
      fitCamera(spec.nodes, spec.pad);
    }
    render();
  }

  /** Fit the canvas to its container whenever the container changes size. */
  function resize() {
    const w = Math.max(host.clientWidth, 1);
    const h = Math.max(host.clientHeight, 1);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (state.lastSpec) {
      fitCamera(state.lastSpec.nodes, state.lastSpec.pad);
    }
    render();
  }
  new ResizeObserver(resize).observe(host);

  /** Redraw with fresh colors when the theme changes. */
  function onTheme() {
    if (state.lastSpec) {
      show(state.lastSpec);
    }
  }
  document.addEventListener("themechange", onTheme);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", onTheme);

  /**
   * Run an animation for a fixed time, calling draw(progress) each frame. Skipped when motion is reduced.
   * @param {number} ms Duration, kept between 120 and 400.
   * @param {function(number): void} draw Receives eased progress from 0 to 1.
   * @returns {Promise<void>} Resolves when finished.
   */
  function tween(ms, draw) {
    if (motionReduced()) {
      draw(1);
      render();
      return Promise.resolve();
    }
    const total = Math.min(400, Math.max(120, ms));
    return new Promise((resolve) => {
      const start = performance.now();
      /** One animation frame. @param {number} now Time from requestAnimationFrame. */
      function frame(now) {
        const t = Math.min(1, (now - start) / total);
        draw(easeOut(t));
        render();
        if (t < 1) {
          requestAnimationFrame(frame);
        } else {
          resolve();
        }
      }
      requestAnimationFrame(frame);
    });
  }

  return {
    show,
    tween,
    /**
     * Swell a city sphere briefly, to show that something happened at it.
     * @param {string|number} id City id.
     * @returns {Promise<void>} Resolves when finished.
     */
    pulse(id) {
      const mesh = state.nodes.get(id);
      if (!mesh) {
        return Promise.resolve();
      }
      return tween(240, (t) => mesh.scale.setScalar(1 + 0.35 * Math.sin(Math.PI * t)));
    },
    /**
     * Move a marker to a new place.
     * @param {string} id Marker id from the spec.
     * @param {number} x Scene x.
     * @param {number} y Scene y.
     * @param {number} z Scene z.
     * @returns {void}
     */
    moveMarker(id, x, y, z) {
      const mesh = state.markers.get(id);
      if (mesh) {
        mesh.position.set(x, y, z);
      }
    },
    /**
     * Set the text alternative that screen readers get for the canvas.
     * @param {string} text Plain description of what the picture shows.
     * @returns {void}
     */
    setAlt(text) {
      canvas.setAttribute("aria-label", `${text} Drag to turn the view, scroll to zoom, arrow keys move it.`);
    },
    /**
     * Put the camera back where it starts.
     * @returns {void}
     */
    resetView() {
      if (state.lastSpec) {
        fitCamera(state.lastSpec.nodes, state.lastSpec.pad);
        render();
      }
    },
  };
}
