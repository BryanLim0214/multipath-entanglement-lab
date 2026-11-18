/**
 * Web Worker for the Code Lab. It starts Pyodide (Python in the browser, pinned from cdn.jsdelivr.net),
 * writes the real engine files from src/qmp into the Python file system, loads the adapter in py/, and runs
 * the player's code. The page terminates this worker if a run takes too long, so a loop cannot freeze the page.
 * Messages in: {type: "init"} and {type: "run", id, source, baseline, q, seeds, nSpec, zeroIllegal}.
 * Messages out: progress, ready, error, result, runError.
 */
const PYODIDE_VERSION = "0.26.4";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const PACKAGES = ["numpy", "networkx", "scipy", "pyyaml"]; // pulp is not available in Pyodide, and nothing loaded here needs it
// Only these engine modules are loaded. ilp.py imports pulp at the top, so it is left out; sim.py does not import it.
const ENGINE_FILES = ["__init__", "core", "model", "fidelity", "heuristic", "sim", "stats"];
const HOME = "/home/pyodide";

let pyodide = null;

/**
 * Tell the page how loading is going.
 * @param {string} text Plain-language status.
 * @returns {void}
 */
function progress(text) {
  self.postMessage({ type: "progress", text });
}

/**
 * Download a text file that sits next to this site's pages.
 * @param {string} relative Path relative to this worker file.
 * @returns {Promise<string>} The file text.
 */
async function fetchText(relative) {
  const url = new URL(relative, self.location.href);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${relative} (HTTP ${response.status}).`);
  }
  return response.text();
}

/**
 * Start Python, install the packages, and copy the engine and adapter files in.
 * @returns {Promise<void>} Resolves when the adapter can be imported.
 */
async function init() {
  progress("Downloading Python (Pyodide) from cdn.jsdelivr.net. The first time takes a while.");
  try {
    importScripts(`${PYODIDE_URL}pyodide.js`);
  } catch (error) {
    self.postMessage({ type: "error", offline: true, message: "Python could not be downloaded from cdn.jsdelivr.net." });
    return;
  }
  pyodide = await self.loadPyodide({ indexURL: PYODIDE_URL });
  progress(`Loading ${PACKAGES.join(", ")}.`);
  await pyodide.loadPackage(PACKAGES);
  progress("Loading the engine files from src/qmp and the adapter from quantumlab/py.");
  pyodide.FS.mkdirTree(`${HOME}/qmp`);
  pyodide.FS.mkdirTree(`${HOME}/lab`);
  for (const name of ENGINE_FILES) {
    pyodide.FS.writeFile(`${HOME}/qmp/${name}.py`, await fetchText(`../../src/qmp/${name}.py`));
  }
  pyodide.FS.writeFile(`${HOME}/lab/codelab_adapter.py`, await fetchText("../py/codelab_adapter.py"));
  pyodide.runPython(`import sys\nsys.path[:0] = ["${HOME}", "${HOME}/lab"]\nimport codelab_adapter`);
  self.postMessage({ type: "ready" });
}

/**
 * Score the player's code and send back the JSON result.
 * @param {{id: number, source: string, baseline: string, q: number, seeds: number[], nSpec: string, zeroIllegal: boolean}} job The run request.
 * @returns {void}
 */
function run(job) {
  const adapter = pyodide.pyimport("codelab_adapter");
  try {
    const text = adapter.run_challenge_json(job.source, job.baseline, job.q, JSON.stringify(job.seeds), job.nSpec, job.zeroIllegal);
    self.postMessage({ type: "result", id: job.id, data: JSON.parse(text) });
  } finally {
    adapter.destroy();
  }
}

self.onmessage = async (event) => {
  const message = event.data;
  try {
    if (message.type === "init") {
      await init();
    } else if (message.type === "run") {
      run(message);
    }
  } catch (error) {
    self.postMessage({ type: message.type === "run" ? "runError" : "error", id: message.id, offline: false, message: String(error.message || error) });
  }
};
