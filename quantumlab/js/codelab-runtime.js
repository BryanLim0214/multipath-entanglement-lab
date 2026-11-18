/**
 * Page side of the Code Lab's Python runtime: starts the worker, sends runs, and stops the worker when a run
 * takes too long. A stopped worker is replaced on the next run. It touches no page elements.
 */

/**
 * Create a runtime handle.
 * @param {function(string): void} onStatus Receives plain-language loading messages.
 * @returns {{ready: function(): Promise<void>, run: function(object, number): Promise<object>, restart: function(): void, dispose: function(): void}} Handle.
 */
export function createRuntime(onStatus) {
  let worker = null;
  let readyPromise = null;
  let nextId = 1;
  const pending = new Map();

  /**
   * Handle one message from the worker.
   * @param {object} message The message.
   * @param {function(): void} resolveReady Called on "ready".
   * @param {function(object): void} rejectReady Called on "error".
   * @returns {void}
   */
  function handle(message, resolveReady, rejectReady) {
    if (message.type === "progress") {
      onStatus(message.text);
    } else if (message.type === "ready") {
      resolveReady();
    } else if (message.type === "error") {
      rejectReady({ offline: Boolean(message.offline), message: message.message });
    } else if (message.type === "result" && pending.has(message.id)) {
      pending.get(message.id).resolve(message.data);
    } else if (message.type === "runError" && pending.has(message.id)) {
      pending.get(message.id).reject({ message: message.message });
    }
  }

  /**
   * Start a fresh worker and ask it to load Python.
   * @returns {Promise<void>} Resolves when Python and the engine are ready.
   */
  function start() {
    worker = new Worker(new URL("./codelab-worker.js", import.meta.url));
    readyPromise = new Promise((resolve, reject) => {
      worker.onmessage = (event) => handle(event.data, resolve, reject);
      worker.onerror = () => reject({ offline: false, message: "The Python worker could not start in this browser." });
    });
    worker.postMessage({ type: "init" });
    return readyPromise;
  }

  /**
   * Stop the worker and forget it.
   * @returns {void}
   */
  function stop() {
    if (worker) {
      worker.terminate();
    }
    worker = null;
    readyPromise = null;
    pending.clear();
  }

  return {
    /**
     * Wait for Python, starting it if needed.
     * @returns {Promise<void>} Resolves when ready, rejects with {offline, message}.
     */
    ready() {
      return readyPromise || start();
    },
    /**
     * Run the player's code with a time limit. On timeout the worker is stopped and the promise rejects with {timeout: true}.
     * @param {object} job Fields source, baseline, q, seeds, nSpec, zeroIllegal.
     * @param {number} limitMs Longest allowed run in milliseconds.
     * @returns {Promise<object>} The result dict from the adapter.
     */
    async run(job, limitMs) {
      await this.ready();
      return new Promise((resolve, reject) => {
        const id = nextId;
        nextId += 1;
        const timer = window.setTimeout(() => { stop(); reject({ timeout: true }); }, limitMs);
        pending.set(id, {
          resolve: (value) => { window.clearTimeout(timer); pending.delete(id); resolve(value); },
          reject: (error) => { window.clearTimeout(timer); pending.delete(id); reject(error); },
        });
        worker.postMessage({ type: "run", id, ...job });
      });
    },
    /**
     * Throw away the worker so the next call starts a new one (used for "Try again").
     * @returns {void}
     */
    restart() {
      stop();
    },
    /**
     * Stop the worker for good when the room closes.
     * @returns {void}
     */
    dispose() {
      stop();
    },
  };
}
