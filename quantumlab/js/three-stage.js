/**
 * The shared 3D stage. A room describes a small network (cities, links, markers) and the stage draws it:
 * matte spheres for cities, tubes whose radius is proportional to seats, and small beads for pairs.
 * Labels are HTML elements placed over the canvas. The scene only redraws while something changes: there is no idle loop.
 * Every change of state can be animated: show() with { animate: true } moves from the old picture to the new one,
 * travel() sends a bead along a route, and ring() flashes a city. All of them skip to the final state when motion is reduced.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { motionReduced } from "./ui.js";

const NODE_RADIUS = 0.4;
const TUBE_PER_SEAT = 0.04; // tube radius is proportional to seats
const BEAD_RADIUS = 0.13;
const MARKER_SIZE = 0.3;
const TRAVEL_Z = 0.55; // height of a travelling bead: above the tubes, level with the top of a city
const TRANSITION_MS = 360;
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
    moveMarker: noop, setAlt: noop, resetView: noop,
    /**
     * Nothing to draw, so every animated call is already finished.
     * @returns {Promise<void>} Already resolved.
     */
    show: () => Promise.resolve(),
    pulse: () => Promise.resolve(),
    travel: () => Promise.resolve(),
    ring: () => Promise.resolve(),
    wait: () => Promise.resolve(),
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
 * @returns {object} Stage API: show(spec, opts), tween(ms, draw), pulse(id), travel(path, opts), ring(id, color), wait(ms), moveMarker, setAlt, resetView. Every animated call returns a Promise.
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
  // epoch counts redraws: an animation started before a redraw is stopped, because its objects are gone
  const state = { nodeViews: new Map(), linkViews: new Map(), markers: new Map(), labelItems: [], lastSpec: null,
    fitKey: "", view: VIEW_DIRECTION, epoch: 0, width: 0, height: 0 };

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
   * Free the GPU memory of everything in the current content group and start an empty one.
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
    state.nodeViews = new Map(); // new maps, because the caller still holds the old ones to animate from
    state.linkViews = new Map();
    state.markers = new Map();
    state.labelItems = [];
    labels.replaceChildren();
  }

  /**
   * Make a matte material from a color object.
   * @param {THREE.Color} color The color.
   * @returns {THREE.MeshStandardMaterial} The material.
   */
  function matteColor(color) {
    return new THREE.MeshStandardMaterial({ color: color.clone(), roughness: 1, metalness: 0 });
  }

  /**
   * Make a matte material.
   * @param {string} color Token name or hex.
   * @returns {THREE.MeshStandardMaterial} The material.
   */
  function matte(color) {
    return matteColor(new THREE.Color(tokenColor(color)));
  }

  /**
   * Add an HTML label that follows a 3D point.
   * @param {HTMLElement} el The label element.
   * @param {THREE.Vector3} point Where it sits in the scene (the stage moves it while the point moves).
   * @param {boolean} [center] True to centre the label on the point instead of hanging it below.
   * @returns {{el: HTMLElement, point: THREE.Vector3, center: boolean}} The label record.
   */
  function addLabel(el, point, center = false) {
    labels.append(el);
    const item = { el, point, center };
    state.labelItems.push(item);
    return item;
  }

  // ---- animation driver: one frame loop that runs only while an animation is running --------------
  const running = new Set();
  let ticking = false;

  /**
   * One animation frame for every running tween, then a single render.
   * @param {number} now Time from requestAnimationFrame.
   * @returns {void}
   */
  function tick(now) {
    for (const a of [...running]) {
      if (a.start === null) {
        a.start = now;
      }
      const t = Math.min(1, Math.max(0, (now - a.start) / a.total));
      a.draw(easeOut(t));
      if (t >= 1) {
        running.delete(a);
        a.resolve();
      }
    }
    render();
    if (running.size > 0) {
      requestAnimationFrame(tick);
    } else {
      ticking = false;
    }
  }

  /**
   * Stop every running animation at once (their promises resolve). Used before a redraw, which deletes their objects.
   * @returns {void}
   */
  function cancelAnimations() {
    const stopped = [...running];
    running.clear();
    stopped.forEach((a) => a.resolve());
  }

  /**
   * Run an animation for a fixed time, calling draw(progress) each frame. Skipped when motion is reduced.
   * @param {number} ms Duration, kept between 120 and 400.
   * @param {function(number): void} draw Receives eased progress from 0 to 1.
   * @returns {Promise<void>} Resolves when finished (or when a redraw stops it).
   */
  function tween(ms, draw) {
    if (motionReduced()) {
      draw(1);
      render();
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      running.add({ start: null, total: Math.min(400, Math.max(120, ms)), draw, resolve });
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(tick);
      }
    });
  }

  /**
   * Wait a fixed time between the steps of a sequence (for example to stagger planes). Skipped when motion is reduced.
   * @param {number} ms Wait in milliseconds.
   * @returns {Promise<void>} Resolves after the wait.
   */
  function wait(ms) {
    return motionReduced() ? Promise.resolve() : new Promise((resolve) => { window.setTimeout(resolve, ms); });
  }

  // ---- cities ---------------------------------------------------------------------------------
  /**
   * Build a node: a sphere plus its HTML label (a button when it has a click handler).
   * @param {object} n Node spec: id, x, y, label, color, picked, onClick, title, hint, tabless.
   * @param {Map<*, object>} oldNodes Node views of the previous picture, to animate from.
   * @param {boolean} animate True when the picture changes with a transition.
   * @returns {void}
   */
  function addNode(n, oldNodes, animate) {
    const toColor = new THREE.Color(tokenColor(n.color || "ink"));
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(NODE_RADIUS, 32, 16), matteColor(toColor));
    content.add(mesh);
    const toPos = new THREE.Vector3(n.x, n.y, 0);
    const prev = animate ? oldNodes.get(n.id) : null;
    // a city that is new in this picture grows from nothing (pop-in); a known one slides and changes color
    const from = prev
      ? { pos: prev.cur.pos.clone(), color: prev.cur.color.clone(), scale: prev.cur.scale }
      : { pos: toPos.clone(), color: toColor.clone(), scale: animate ? 0 : 1 };
    const view = { mesh, from, toPos, toColor, toScale: 1, cur: from, labelItem: null, labelOffset: null };
    state.nodeViews.set(n.id, view);
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
    // tag sits on the sphere (away from every link label) or hangs below it
    view.labelOffset = n.onNode ? new THREE.Vector3(0, 0, NODE_RADIUS) : new THREE.Vector3(0, -NODE_RADIUS - 0.55, 0);
    view.labelItem = addLabel(el, new THREE.Vector3(), Boolean(n.onNode));
  }

  /**
   * Draw a city at progress t of its transition (position, color and size), and move its label with it.
   * @param {object} view A node view.
   * @param {number} t Progress from 0 (old picture) to 1 (new picture).
   * @returns {void}
   */
  function applyNode(view, t) {
    const { from } = view;
    const pos = from.pos.clone().lerp(view.toPos, t);
    const color = from.color.clone().lerp(view.toColor, t);
    const scale = from.scale + (view.toScale - from.scale) * t;
    view.mesh.position.copy(pos);
    view.mesh.material.color.copy(color);
    view.mesh.scale.setScalar(Math.max(scale, 0.001));
    view.mesh.visible = scale > 0.001;
    view.cur = { pos, color, scale };
    if (view.labelItem) {
      view.labelItem.point.set(pos.x + view.labelOffset.x, pos.y + view.labelOffset.y, view.labelOffset.z);
    }
  }

  // ---- links ----------------------------------------------------------------------------------
  /**
   * The curve of a link between two points: straight, or an arc that rises above the plane.
   * @param {object} spec Link spec (uses arc).
   * @param {THREE.Vector3} pa One end.
   * @param {THREE.Vector3} pb The other end.
   * @returns {THREE.Curve<THREE.Vector3>} The curve.
   */
  function curveFor(spec, pa, pb) {
    return spec.arc
      ? new THREE.QuadraticBezierCurve3(pa, pa.clone().lerp(pb, 0.5).add(new THREE.Vector3(0, spec.arc, 0.8)), pb)
      : new THREE.LineCurve3(pa, pb);
  }

  /**
   * Build a link: a tube (radius proportional to seats), optional beads, and an optional label.
   * The meshes are made here; applyLink() sets their size and place at a moment of the transition.
   * @param {object} l Link spec: from, to, seats, color, beads, beadColor, arc, lift, label, note, labelShift (scene x and y offset of the label), key.
   * @param {Map<*, object>} nodeSpecs Node specs by id.
   * @param {string} key Name of this link, the same in the old and the new picture.
   * @param {Map<string, object>} oldLinks Link views of the previous picture, to animate from.
   * @param {boolean} animate True when the picture changes with a transition.
   * @returns {void}
   */
  function addLink(l, nodeSpecs, key, oldLinks, animate) {
    const a = nodeSpecs.get(l.from);
    const b = nodeSpecs.get(l.to);
    const lift = l.lift || 0; // lifted tubes float above the plane, used to show a suggested answer
    const to = {
      a: new THREE.Vector3(a.x, a.y, lift), b: new THREE.Vector3(b.x, b.y, lift),
      radius: l.seats * TUBE_PER_SEAT, color: new THREE.Color(tokenColor(l.color || "muted")), beads: l.beads || 0,
    };
    const prev = animate ? oldLinks.get(key) : null;
    // a link that is new in this picture grows from nothing; a known one changes size, color and beads
    const from = prev
      ? { a: prev.cur.a.clone(), b: prev.cur.b.clone(), radius: prev.cur.radius, color: prev.cur.color.clone(), beads: prev.to.beads }
      : { a: to.a.clone(), b: to.b.clone(), radius: animate ? 0 : to.radius, color: to.color.clone(), beads: animate ? 0 : to.beads };
    const view = { key, spec: l, from, to, cur: from, tube: null, beads: [], labelItem: null, labelShift: null, ghost: false };
    const beadMaterial = matte(l.beadColor || "ink");
    for (let i = 0; i < Math.max(from.beads, to.beads); i += 1) {
      const bead = new THREE.Mesh(new THREE.SphereGeometry(BEAD_RADIUS, 16, 12), beadMaterial);
      content.add(bead);
      view.beads.push(bead);
    }
    if (l.label) {
      const el = document.createElement("span");
      el.className = `link-label${l.note ? " is-note" : ""}${l.small ? " is-small" : ""}`;
      el.textContent = l.label;
      const shift = l.labelShift || (l.small ? sideOffset(to.a, to.b) : { x: 0, y: l.note ? 0.4 : 0.55 });
      view.labelShift = new THREE.Vector3(shift.x, shift.y, 0);
      view.labelItem = addLabel(el, new THREE.Vector3());
    }
    state.linkViews.set(key, view);
  }

  /**
   * Build a link that is in the old picture but not in the new one: it shrinks away, then is removed.
   * @param {object} old The old link view.
   * @returns {object} The ghost link view.
   */
  function addGhostLink(old) {
    const from = { a: old.cur.a.clone(), b: old.cur.b.clone(), radius: old.cur.radius, color: old.cur.color.clone(), beads: old.to.beads };
    const to = { a: from.a.clone(), b: from.b.clone(), radius: 0, color: from.color.clone(), beads: 0 };
    const view = { key: old.key, spec: old.spec, from, to, cur: from, tube: null, beads: [], labelItem: null, labelShift: null, ghost: true };
    const beadMaterial = matte(old.spec.beadColor || "ink");
    for (let i = 0; i < from.beads; i += 1) {
      const bead = new THREE.Mesh(new THREE.SphereGeometry(BEAD_RADIUS, 16, 12), beadMaterial);
      content.add(bead);
      view.beads.push(bead);
    }
    return view;
  }

  /**
   * Draw a link at progress t of its transition: tube radius, color, ends, bead places and bead sizes, and its label.
   * Beads that appear come in one after another, and beads that go away leave one after another.
   * @param {object} view A link view.
   * @param {number} t Progress from 0 (old picture) to 1 (new picture).
   * @returns {void}
   */
  function applyLink(view, t) {
    const { from, to } = view;
    const pa = from.a.clone().lerp(to.a, t);
    const pb = from.b.clone().lerp(to.b, t);
    const radius = from.radius + (to.radius - from.radius) * t;
    const color = from.color.clone().lerp(to.color, t);
    const curve = curveFor(view.spec, pa, pb);
    if (radius > 1e-3) {
      if (!view.tube) {
        view.tube = new THREE.Mesh(new THREE.BufferGeometry(), matteColor(color));
        content.add(view.tube);
      }
      view.tube.geometry.dispose();
      view.tube.geometry = new THREE.TubeGeometry(curve, 32, radius, 12, false);
      view.tube.material.color.copy(color);
    }
    if (view.tube) {
      view.tube.visible = radius > 1e-3;
    }
    view.beads.forEach((bead, i) => {
      const inFrom = i < from.beads;
      const inTo = i < to.beads;
      const fracFrom = (i + 1) / (from.beads + 1);
      const fracTo = (i + 1) / (to.beads + 1);
      const frac = inFrom && inTo ? fracFrom + (fracTo - fracFrom) * t : inFrom ? fracFrom : fracTo;
      let size = 1;
      if (!inFrom) {
        size = Math.min(1, Math.max(0, t * (to.beads - from.beads) - (i - from.beads)));
      } else if (!inTo) {
        size = 1 - Math.min(1, Math.max(0, t * (from.beads - to.beads) - (i - to.beads)));
      }
      bead.position.copy(curve.getPoint(frac)).add(new THREE.Vector3(0, 0, Math.max(radius, 0) + BEAD_RADIUS * 0.8));
      bead.scale.setScalar(Math.max(size, 0.001));
      bead.visible = size > 0.001;
    });
    view.cur = { a: pa, b: pb, radius, color };
    if (view.labelItem) {
      view.labelItem.point.copy(curve.getPoint(0.5)).add(view.labelShift).add(new THREE.Vector3(0, 0, radius));
    }
  }

  /**
   * Whether a node or link looks the same in the old and the new picture (so it needs no animation frames).
   * @param {object} view A node view or a link view.
   * @returns {boolean} True when nothing about it changes.
   */
  function isUnchanged(view) {
    const { from } = view;
    if (view.mesh) {
      return from.pos.equals(view.toPos) && from.color.equals(view.toColor) && from.scale === view.toScale;
    }
    const { to } = view;
    return from.a.equals(to.a) && from.b.equals(to.b) && from.radius === to.radius && from.color.equals(to.color) && from.beads === to.beads;
  }

  /**
   * Apply a progress value to a node view or a link view.
   * @param {object} view A node view or a link view.
   * @param {number} t Progress from 0 to 1.
   * @returns {void}
   */
  function applyView(view, t) {
    if (view.mesh) {
      applyNode(view, t);
    } else {
      applyLink(view, t);
    }
  }

  /**
   * Build a city that is in the old picture but not in the new one: it shrinks away, then is removed.
   * @param {object} old The old node view.
   * @returns {object} The ghost node view.
   */
  function addGhostNode(old) {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(NODE_RADIUS, 32, 16), matteColor(old.cur.color));
    content.add(mesh);
    const from = { pos: old.cur.pos.clone(), color: old.cur.color.clone(), scale: old.cur.scale };
    return { mesh, from, toPos: from.pos.clone(), toColor: from.color.clone(), toScale: 0, cur: from, labelItem: null, labelOffset: null, ghost: true };
  }

  /**
   * Remove the meshes of ghost cities and links once their shrinking is done.
   * @param {object[]} ghosts Ghost views.
   * @returns {void}
   */
  function removeGhosts(ghosts) {
    ghosts.forEach((g) => {
      [g.mesh, g.tube, ...(g.beads || [])].filter(Boolean).forEach((obj) => {
        obj.removeFromParent();
        obj.geometry.dispose();
        obj.material.dispose();
      });
    });
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
   * Name each link of a spec: its own key if it has one, otherwise "from|to", plus a counter for repeats.
   * @param {object[]} specLinks Link specs in drawing order.
   * @returns {string[]} One key per link, the same in every picture that draws the same link.
   */
  function linkKeys(specLinks) {
    const seen = new Map();
    return specLinks.map((l) => {
      const base = l.key ?? `${l.from}|${l.to}`;
      const count = seen.get(base) || 0;
      seen.set(base, count + 1);
      return `${base}#${count}`;
    });
  }

  /**
   * Draw a whole picture, replacing the old one.
   * @param {{nodes: object[], links?: object[], markers?: object[], captions?: object[], pad?: number, view?: string, fitKey?: string}} spec The picture (pad is the free margin round the nodes, default 1.3; view "top" looks straight down; fitKey keeps the camera where the viewer left it while it stays the same). Node flag onNode puts the tag on the sphere; link flag small makes the label smaller; link key names a link so it can change smoothly.
   * @param {{animate?: boolean, ms?: number}} [opts] animate moves from the old picture to this one: tubes grow or shrink, beads come and go, colors change, new cities pop in and removed ones shrink away.
   * @returns {Promise<void>} Resolves when the transition has finished (at once without animate or with reduced motion).
   */
  function show(spec, opts = {}) {
    const oldNodes = state.nodeViews;
    const oldLinks = state.linkViews;
    state.epoch += 1;
    cancelAnimations();
    state.lastSpec = spec;
    state.view = spec.view === "top" ? TOP_VIEW_DIRECTION : VIEW_DIRECTION;
    disposeContent();
    scene.background = new THREE.Color(tokenColor("paper"));
    const animate = Boolean(opts.animate) && !motionReduced() && oldNodes.size > 0;
    const nodeSpecs = new Map(spec.nodes.map((n) => [n.id, n]));
    const specLinks = spec.links || [];
    const keys = linkKeys(specLinks);
    specLinks.forEach((l, i) => addLink(l, nodeSpecs, keys[i], oldLinks, animate));
    spec.nodes.forEach((n) => addNode(n, oldNodes, animate));
    const ghosts = [];
    if (animate) {
      oldLinks.forEach((old, key) => { if (!state.linkViews.has(key) && !old.ghost) { ghosts.push(addGhostLink(old)); } });
      oldNodes.forEach((old, id) => { if (!state.nodeViews.has(id) && !old.ghost) { ghosts.push(addGhostNode(old)); } });
    }
    (spec.markers || []).forEach(addMarker);
    (spec.captions || []).forEach(addCaption);
    const fitKey = (spec.fitKey ?? spec.nodes.map((n) => `${n.id}:${n.x}:${n.y}`).join("|")) + (spec.view || "");
    if (fitKey !== state.fitKey) {
      state.fitKey = fitKey;
      fitCamera(spec.nodes, spec.pad);
    }
    const views = [...state.linkViews.values(), ...state.nodeViews.values(), ...ghosts];
    const moving = animate ? views.filter((v) => !isUnchanged(v)) : [];
    views.filter((v) => !moving.includes(v)).forEach((v) => applyView(v, 1));
    moving.forEach((v) => applyView(v, 0));
    render();
    if (moving.length === 0) {
      removeGhosts(ghosts);
      return Promise.resolve();
    }
    return tween(opts.ms ?? TRANSITION_MS, (t) => moving.forEach((v) => applyView(v, t))).then(() => removeGhosts(ghosts));
  }

  /** Fit the canvas to its container whenever the container changes size (and only then: a redundant call would reset the viewer's turned view). */
  function resize() {
    const w = Math.max(host.clientWidth, 1);
    const h = Math.max(host.clientHeight, 1);
    if (w === state.width && h === state.height) {
      return;
    }
    state.width = w;
    state.height = h;
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
   * Send a bead along a route, city by city, then let it settle (it shrinks away at the last city).
   * Skipped when motion is reduced. A redraw during the trip ends it.
   * @param {Array<string|number>} path City ids from the start to the end.
   * @param {{color?: string, delay?: number, stopAt?: number, drop?: boolean}} [opts] color is a token name; delay waits first (ms); stopAt (0 to 1) stops part way along the last hop; drop makes the bead fall instead of settle.
   * @returns {Promise<void>} Resolves when the bead is gone.
   */
  async function travel(path, opts = {}) {
    const views = path.map((id) => state.nodeViews.get(id));
    if (motionReduced() || path.length < 2 || views.some((v) => !v)) {
      return;
    }
    const epoch = state.epoch;
    if (opts.delay) {
      await wait(opts.delay);
      if (epoch !== state.epoch) {
        return;
      }
    }
    const bead = new THREE.Mesh(new THREE.SphereGeometry(BEAD_RADIUS * 1.2, 16, 12), matte(opts.color || "ink"));
    /** The place above a city where the bead rides. @param {object} v Node view. @returns {THREE.Vector3} The point. */
    const above = (v) => new THREE.Vector3(v.mesh.position.x, v.mesh.position.y, TRAVEL_Z);
    bead.position.copy(above(views[0]));
    content.add(bead);
    const hops = path.length - 1;
    const hopMs = Math.min(300, Math.max(120, Math.floor(1000 / hops))); // a whole route stays near one second
    for (let i = 0; i < hops; i += 1) {
      const start = above(views[i]);
      const share = i === hops - 1 && opts.stopAt !== undefined ? opts.stopAt : 1;
      const end = start.clone().lerp(above(views[i + 1]), share);
      await tween(hopMs, (t) => bead.position.lerpVectors(start, end, t));
      if (epoch !== state.epoch) {
        return;
      }
    }
    const fallFrom = bead.position.z;
    await tween(opts.drop ? 160 : 120, (t) => {
      bead.position.z = fallFrom - (opts.drop ? 0.8 * t : 0);
      bead.scale.setScalar(Math.max(1 - t, 0.001));
    });
    bead.removeFromParent();
    bead.geometry.dispose();
    bead.material.dispose();
  }

  /**
   * Flash a flat ring that grows around a city and fades out: a swap happened there, or a request was blocked there.
   * The fade uses opacity on a 3D mesh, not on a page panel. Skipped when motion is reduced.
   * @param {string|number} id City id.
   * @param {string} [color] Token name; "fail" for a blocked request.
   * @returns {Promise<void>} Resolves when the ring is gone.
   */
  async function ring(id, color = "fail") {
    const view = state.nodeViews.get(id);
    if (!view || motionReduced()) {
      return;
    }
    const epoch = state.epoch;
    const material = new THREE.MeshBasicMaterial({ color: new THREE.Color(tokenColor(color)), transparent: true, opacity: 1, depthWrite: false, side: THREE.DoubleSide });
    const mesh = new THREE.Mesh(new THREE.RingGeometry(NODE_RADIUS * 1.05, NODE_RADIUS * 1.3, 48), material);
    mesh.position.set(view.mesh.position.x, view.mesh.position.y, NODE_RADIUS + 0.05);
    content.add(mesh);
    await tween(400, (t) => {
      mesh.scale.setScalar(1 + 2.2 * t);
      material.opacity = 1 - t;
    });
    if (epoch === state.epoch) {
      mesh.removeFromParent();
      render();
    }
    mesh.geometry.dispose();
    material.dispose();
  }

  return {
    show,
    tween,
    wait,
    travel,
    ring,
    /**
     * Swell a city sphere briefly, to show that something happened at it.
     * @param {string|number} id City id.
     * @returns {Promise<void>} Resolves when finished.
     */
    pulse(id) {
      const view = state.nodeViews.get(id);
      if (!view) {
        return Promise.resolve();
      }
      return tween(240, (t) => view.mesh.scale.setScalar(1 + 0.35 * Math.sin(Math.PI * t)));
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
