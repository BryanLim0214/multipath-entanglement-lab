/**
 * The help ladder: five levels of help for every task (nudge, hint, stronger hint, show me, do it for me).
 * Hint text comes from data/hints.json. Progress per task is saved in localStorage, and the page still
 * works if storage fails. Help is always in the page flow and never covers the stage.
 */
import { h, storeGet, storeSet, announce } from "./ui.js";

export const LEVEL_NAMES = ["Nudge", "Hint", "Stronger hint", "Show me", "Do it for me"];
const NUDGE_DELAY_MS = 40000;
const WRONG_TRIES_FOR_NUDGE = 2;
const PROGRESS_KEY = "quantumlab.progress.v1";
const NUDGE_KEY = "quantumlab.nudges.v1";

let activeLadder = null;

/**
 * Press the "H" key: move the current task's ladder to its next level.
 * @returns {void}
 */
export function pressH() {
  if (activeLadder) {
    activeLadder.next();
  }
}

/**
 * Lower is better: solved with no help, then with hints, then done for me.
 * @param {{state: string, hints: number}} record A saved outcome.
 * @returns {number} Rank used to keep the best outcome.
 */
function outcomeRank(record) {
  if (record.state === "done") {
    return 1000;
  }
  return record.hints;
}

/**
 * The saved outcome of a task.
 * @param {string} taskId Task id from hints.json.
 * @returns {{state: string, hints: number}|null} Record, or null if the task has not been finished.
 */
export function readProgress(taskId) {
  const all = storeGet(PROGRESS_KEY, {});
  return all[taskId] || null;
}

/**
 * Plain-text progress for a task.
 * @param {string} taskId Task id.
 * @returns {string} "Not solved yet", "Solved", "Solved with N hints" or "Done for me".
 */
export function progressText(taskId) {
  const record = readProgress(taskId);
  if (!record) {
    return "Not solved yet";
  }
  if (record.state === "done") {
    return "Done for me";
  }
  if (record.hints === 0) {
    return "Solved";
  }
  return `Solved with ${record.hints} hint${record.hints === 1 ? "" : "s"}`;
}

/**
 * Save an outcome, keeping the better one if the task was finished before.
 * @param {string} taskId Task id.
 * @param {{state: string, hints: number}} record New outcome.
 * @returns {void}
 */
function saveProgress(taskId, record) {
  const all = storeGet(PROGRESS_KEY, {});
  if (!all[taskId] || outcomeRank(record) < outcomeRank(all[taskId])) {
    all[taskId] = record;
    storeSet(PROGRESS_KEY, all);
  }
}

/**
 * Create the help area for one task and start its nudge timer.
 * @param {{taskId: string, hints: object, handlers: {highlight: function(boolean): void, show: function(): void, doIt: function(): void, similar: function(): void}}} spec
 *   taskId is the key in hints.json; handlers are the task's own actions for levels 3 to 5.
 * @returns {{element: HTMLElement, next: function(): void, progress: function(): void, wrong: function(): void, solve: function(): void, dispose: function(): void}} Ladder handle.
 */
export function createLadder({ taskId, hints, handlers }) {
  const text = hints[taskId];
  const model = { level: 0, solved: false, wrong: 0, timer: null };
  const status = h("p", { class: "help-status" });
  const panel = h("div", { class: "help-panel" });
  const helpButton = h("button", { class: "btn", type: "button", onclick: () => next() });
  const doItButton = h("button", { class: "btn", type: "button", text: "Do it for me", onclick: () => goTo(5) });
  const nudgeBox = h("input", { type: "checkbox", checked: storeGet(NUDGE_KEY, true), onchange: onNudgeToggle });
  const element = h("div", { class: "help" },
    h("div", { class: "help-bar" }, helpButton, doItButton,
      h("label", { class: "nudge-toggle" }, nudgeBox, "Show nudges")),
    status, panel);

  /**
   * Remember the nudge switch and stop or restart the timer.
   * @returns {void}
   */
  function onNudgeToggle() {
    storeSet(NUDGE_KEY, nudgeBox.checked);
    startTimer();
  }

  /**
   * Update the button label and the progress line.
   * @returns {void}
   */
  function refreshChrome() {
    const upcoming = model.level < 5 ? LEVEL_NAMES[model.level] : null;
    helpButton.textContent = upcoming ? `${upcoming} (press H)` : "No more help levels";
    helpButton.disabled = upcoming === null;
    doItButton.disabled = model.level === 5;
    status.textContent = `Progress: ${progressText(taskId)}`;
  }

  /**
   * Show one help level as a card in the panel.
   * @param {number} level Level from 1 to 5.
   * @param {boolean} [auto] True for the automatic nudge, which can be dismissed.
   * @returns {void}
   */
  function renderLevel(level, auto = false) {
    const entry = text.levels[level - 1];
    const card = h("div", { class: "help-card" },
      h("h4", { text: `Help ${level} of 5: ${LEVEL_NAMES[level - 1]}` }),
      h("p", {}, entry.kid),
      h("p", {}, entry.student));
    if (level === 5 && text.breaks) {
      card.append(h("p", { class: "small" }, `Where this picture breaks: ${text.breaks}`));
    }
    if (auto || level === 1) {
      card.append(h("button", { class: "btn btn-small", type: "button", text: "Dismiss", onclick: () => card.remove() }));
    }
    if (level === 5) {
      card.append(h("button", { class: "btn btn-small", type: "button", text: "Try a similar one", onclick: similar }));
    }
    panel.replaceChildren(card);
    announce(`Help level ${level}. ${entry.kid} ${entry.student}`);
  }

  /**
   * Go straight to a level, running the task's own action for levels 3 to 5.
   * @param {number} level Target level from 1 to 5.
   * @param {boolean} [auto] True when the nudge timer opened it.
   * @returns {void}
   */
  function goTo(level, auto = false) {
    if (level <= model.level && !auto) {
      return;
    }
    model.level = Math.max(model.level, level);
    renderLevel(level, auto);
    if (level >= 3) {
      handlers.highlight(true);
    }
    if (level === 4) {
      handlers.show();
    }
    if (level === 5) {
      handlers.doIt();
      finish("done");
    }
    refreshChrome();
  }

  /**
   * Move to the next level.
   * @returns {void}
   */
  function next() {
    if (model.level < 5) {
      goTo(model.level + 1);
    }
  }

  /**
   * Record the outcome of the task.
   * @param {string} kind "solved" or "done".
   * @returns {void}
   */
  function finish(kind) {
    model.solved = true;
    window.clearTimeout(model.timer);
    handlers.highlight(false);
    const used = Math.min(Math.max(model.level - 1, 0), 3);
    saveProgress(taskId, kind === "done" ? { state: "done", hints: 3 } : { state: "solved", hints: used });
  }

  /**
   * Start a fresh attempt after "Try a similar one".
   * @returns {void}
   */
  function similar() {
    model.level = 0;
    model.solved = false;
    model.wrong = 0;
    panel.replaceChildren();
    handlers.highlight(false);
    handlers.similar();
    startTimer();
    refreshChrome();
  }

  /**
   * (Re)start the 40 second nudge timer, if nudges are on and the task is open.
   * @returns {void}
   */
  function startTimer() {
    window.clearTimeout(model.timer);
    if (nudgeBox.checked && !model.solved && model.level === 0) {
      model.timer = window.setTimeout(() => goTo(1, true), NUDGE_DELAY_MS);
    }
  }

  startTimer();
  refreshChrome();
  activeLadder = { next };

  return {
    element,
    next,
    /**
     * Tell the ladder the learner made progress, which restarts the 40 second timer.
     * @returns {void}
     */
    progress() {
      startTimer();
    },
    /**
     * Tell the ladder about a wrong try; two wrong tries open the nudge.
     * @returns {void}
     */
    wrong() {
      model.wrong += 1;
      if (model.wrong >= WRONG_TRIES_FOR_NUDGE && model.level === 0 && nudgeBox.checked && !model.solved) {
        goTo(1, true);
      }
    },
    /**
     * Tell the ladder the task goal is reached by the learner's own work.
     * @returns {void}
     */
    solve() {
      if (!model.solved && model.level < 5) {
        finish("solved");
        refreshChrome();
        announce(`Task finished. ${progressText(taskId)}.`);
      }
    },
    /**
     * Stop the timer and leave the page.
     * @returns {void}
     */
    dispose() {
      window.clearTimeout(model.timer);
      handlers.highlight(false);
      if (activeLadder && activeLadder.next === next) {
        activeLadder = null;
      }
    },
  };
}
