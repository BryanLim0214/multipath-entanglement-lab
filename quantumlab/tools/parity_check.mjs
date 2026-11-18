/**
 * Reads cases from standard input and prints what the JavaScript referee and formulas return,
 * so tests/test_quantumlab_data.py can compare them with the Python engine.
 * Input JSON: { instance, answers: [...], fidelity: [{F, f}], pmf: [{m, q}] }, and optionally
 * cases: [{ instance, answer }] when every case has its own instance (used for the Arena windows).
 */
import { validate } from "../js/referee.js";
import { maxIntermediate, pathFidelity, binomialPmf } from "../js/math.js";

/**
 * Read all of standard input as text.
 * @returns {Promise<string>} The text.
 */
async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf-8");
}

const input = JSON.parse(await readStdin());
const out = {
  referee: input.answers.map((answer) => validate(input.instance, answer)),
  limits: input.fidelity.map(({ F, f }) => maxIntermediate(F, f)),
  pathFidelity: input.fidelity.map(({ F }) => [1, 2, 5, 6].map((L) => pathFidelity(F, L))),
  pmf: input.pmf.map(({ m, q }) => binomialPmf(m, q)),
  cases: (input.cases || []).map(({ instance, answer }) => validate(instance, answer)),
};
process.stdout.write(JSON.stringify(out));
