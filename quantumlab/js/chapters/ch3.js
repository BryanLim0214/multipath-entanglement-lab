/**
 * Chapter 3, "The matchmaker": a chain A, B, D. B joins its two coins (a swap), which creates an
 * A to D pair that is not usable until B phones the result to both ends.
 */
import { h, caption, predictBox } from "../ui.js";
import { createLadder } from "../help-ladder.js";
import { chapterHead, taskBox, outliner } from "./common.js";

const TASK_ID = "ch3-swap";
const POS = { A: { x: -4, y: -0.8 }, B: { x: 0, y: -0.8 }, D: { x: 4, y: -0.8 } };

/**
 * Build the chapter.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {function(): void} Cleanup function.
 */
function mount(ctx) {
  const { narrative, stage, hints } = ctx;
  const state = { phase: "start" };

  const joinButton = h("button", { class: "btn btn-primary", type: "button", text: "Join at B", disabled: true });
  const phoneButton = h("button", { class: "btn btn-primary", type: "button", text: "Phone A and D", disabled: true });
  const resetButton = h("button", { class: "btn", type: "button", text: "Start over" });
  const status = h("p", { "aria-live": "polite" });
  const guess = predictBox({
    name: "ch3-guess",
    legend: "right after B joins its two coins, can A and D use their new pair?",
    options: [{ value: "yes", label: "Yes, right away" }, { value: "no", label: "No, not yet" }],
    onChange: () => { joinButton.disabled = !guess.ready() || state.phase !== "start"; },
  });
  const ladder = createLadder({
    taskId: TASK_ID,
    hints,
    /** Task actions that help levels 3 to 5 call. */
    handlers: {
      highlight: outliner([joinButton, phoneButton]),
      show: () => { autoPlay(); },
      doIt: () => { autoPlay(); },
      similar: () => { reset(); },
    },
  });

  /**
   * Draw the chain in the current phase.
   * @returns {void}
   */
  function draw() {
    const fresh = state.phase === "start";
    const usable = state.phase === "called";
    const links = [
      { from: "A", to: "B", seats: 1, color: "mp", beads: fresh ? 1 : 0, beadColor: "ink", label: fresh ? "pair" : "used up" },
      { from: "B", to: "D", seats: 1, color: "mp", beads: fresh ? 1 : 0, beadColor: "ink", label: fresh ? "pair" : "used up" },
    ];
    if (!fresh) {
      links.push({ from: "A", to: "D", seats: 1.2, color: usable ? "mp" : "muted", arc: 2.2, beads: 1,
        beadColor: usable ? "ink" : "paper", label: usable ? "usable" : "not usable yet", note: !usable });
    }
    stage.show({
      nodes: ["A", "B", "D"].map((id) => ({ id, ...POS[id], label: id, color: id === "B" ? "ext" : "ink" })),
      links,
    });
    stage.setAlt(fresh
      ? "A chain of three cities, A, B and D. A shares a pair with B, and B shares a pair with D."
      : usable
        ? "A and D now share a usable pair, drawn as an arc above the chain. B's pairs are used up."
        : "B joined its two pairs. The A to D arc is grey and labeled not usable yet, because the call has not happened.");
  }

  /**
   * Update the status text and which buttons work.
   * @returns {void}
   */
  function refresh() {
    const text = {
      start: "A has a pair with B, and B has a pair with D. A and D share nothing yet.",
      joined: "B joined its two coins. A and D hold a pair, but neither knows how the join turned out.",
      called: "B phoned both ends. A and D can now use their pair.",
    };
    status.textContent = text[state.phase];
    joinButton.disabled = !(guess.ready() && state.phase === "start");
    phoneButton.disabled = state.phase !== "joined";
  }

  /**
   * B joins its two coins: B flashes, B's pairs are used up, and the grey A to D arc appears.
   * @returns {Promise<void>} Resolves after the flash.
   */
  async function join() {
    if (state.phase !== "start") { return; }
    await stage.pulse("B");
    state.phase = "joined";
    draw();
    refresh();
    if (guess.ready()) {
      const right = guess.value() === "no";
      guess.reveal("no", "No. The pair exists, but A and D still need B's result before they can fix their coins.");
      if (right) { ladder.progress(); } else { ladder.wrong(); }
      guess.clearChoice();
    }
  }

  /**
   * B phones A and D: two messages travel along the chain, then the arc turns usable.
   * @returns {Promise<void>} Resolves when the messages arrive.
   */
  async function phone() {
    if (state.phase !== "joined") { return; }
    phoneButton.disabled = true;
    const home = { x: POS.B.x, y: POS.B.y, z: 0.9 };
    const nodes = ["A", "B", "D"].map((id) => ({ id, ...POS[id], label: id, color: id === "B" ? "ext" : "ink" }));
    const links = [
      { from: "A", to: "B", seats: 1, color: "mp", label: "used up" },
      { from: "B", to: "D", seats: 1, color: "mp", label: "used up" },
      { from: "A", to: "D", seats: 1.2, color: "muted", arc: 2.2, beads: 1, beadColor: "paper", label: "not usable yet", note: true },
    ];
    stage.show({ nodes, links, markers: [{ id: "toA", color: "warn", ...home }, { id: "toD", color: "warn", ...home }] });
    await stage.tween(400, (t) => {
      stage.moveMarker("toA", home.x + (POS.A.x - home.x) * t, home.y, home.z);
      stage.moveMarker("toD", home.x + (POS.D.x - home.x) * t, home.y, home.z);
    });
    state.phase = "called";
    draw();
    refresh();
    ladder.solve();
  }

  /**
   * Go back to the start.
   * @returns {void}
   */
  function reset() {
    state.phase = "start";
    guess.reset();
    draw();
    refresh();
  }

  /**
   * Show me and Do it for me: join, then phone.
   * @returns {Promise<void>} Resolves when the call arrives.
   */
  async function autoPlay() {
    if (state.phase === "start") { await join(); }
    await phone();
  }

  joinButton.addEventListener("click", () => { join(); });
  phoneButton.addEventListener("click", () => { phone(); });
  resetButton.addEventListener("click", () => { reset(); ladder.progress(); });

  narrative.append(
    chapterHead("Chapter 3 of 6", "The matchmaker",
      "A and D are two cities with no direct link. The city in the middle, B, can introduce them."),
    caption({
      kid: "A middle city holds one coin paired with the left city, and one paired with the right city. It joins the two, then phones the result to both ends. Now the two end cities share a pair.",
      student: "Entanglement swapping is a Bell-state measurement at the middle node. It is followed by a classical message, so the end nodes can correct their qubits.",
      expert: "A Bell-state measurement plus a Pauli correction. The paper assumes every swap succeeds.",
      breaks: "The middle city's coins are used up. The end pair is unusable until the phone call arrives.",
    }),
    taskBox("Task: give A and D a pair they can use",
      guess.element,
      h("div", { class: "btn-row" }, joinButton, phoneButton, resetButton),
      status,
      h("p", { class: "muted" }, "The call is needed because B's result is random. Without it, A and D cannot tell which correction their coins need."),
      ladder.element));

  draw();
  refresh();
  return () => ladder.dispose();
}

export default { id: "ch3", number: 3, title: "The matchmaker", mount };
