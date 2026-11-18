/**
 * Pieces every chapter uses: the heading block, a task box, and the outline used by "stronger hint".
 */
import { h } from "../ui.js";

/**
 * The heading block at the top of a chapter or room.
 * @param {string} label Small line above the title, such as "Chapter 1 of 5".
 * @param {string} title Sentence-case title.
 * @param {string} intro One or two plain sentences.
 * @returns {HTMLElement} The header element.
 */
export function chapterHead(label, title, intro) {
  return h("header", { class: "chapter-head" },
    h("p", { class: "chapter-no", text: label }),
    h("h2", { id: "room-title", tabIndex: -1, text: title }),
    h("p", { text: intro }));
}

/**
 * A boxed task: the one thing the viewer is asked to do in this chapter.
 * @param {string} title Task title.
 * @param {...Node} children Content of the box.
 * @returns {HTMLElement} The task element.
 */
export function taskBox(title, ...children) {
  return h("section", { class: "task" }, h("h3", { text: title }), ...children);
}

/**
 * Make a function that outlines a set of elements (used by the stronger hint).
 * @param {HTMLElement[]} elements Elements to outline.
 * @returns {function(boolean): void} Call with true to outline, false to clear.
 */
export function outliner(elements) {
  return (on) => elements.forEach((el) => el.classList.toggle("hint-target", on));
}
