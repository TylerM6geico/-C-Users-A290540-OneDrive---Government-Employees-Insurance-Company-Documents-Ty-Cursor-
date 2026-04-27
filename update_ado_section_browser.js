/**
 * HOW TO USE
 * ----------
 * 1. Open  geico-org-chart.html  in your browser (Chrome / Edge / Firefox).
 * 2. Open DevTools  (F12  or  Ctrl+Shift+I).
 * 3. Go to the  Console  tab.
 * 4. Paste this entire script and press  Enter.
 *
 * What it does:
 *   1. Renames "ADO Features & Epics - Next 30 Days"
 *          →  "ADO Features & Epics - Program Milestone Status"
 *
 *   2. Greys out every row whose State column contains "REMOVED" or "CLOSED"
 *      (case-insensitive) and applies a strikethrough style.
 *
 *   3. Sorts rows so that:
 *        • Active rows (non-REMOVED/CLOSED) appear first, ordered chronologically
 *          by the Target Date column (earliest first).
 *        • REMOVED/CLOSED rows follow, preserving their relative order.
 *        • Header rows (<th>) always stay at the top of each tbody.
 *
 * After running the script you can use  File → Save As  (or Ctrl+S) in your
 * browser to save the modified page back to disk.
 */
(function () {
  "use strict";

  /* ── Constants ─────────────────────────────────────────────────────────── */
  const OLD_TITLE = "ADO Features & Epics - Next 30 Days";
  const NEW_TITLE = "ADO Features & Epics - Program Milestone Status";

  const GREY_STYLES = {
    color: "#999999",
    backgroundColor: "#f0f0f0",
    textDecoration: "line-through",
    opacity: "0.6",
  };

  const FAR_FUTURE = new Date(9999, 11, 31);

  /* ── Helpers ────────────────────────────────────────────────────────────── */

  /** Parse a date string; returns FAR_FUTURE when it cannot be parsed. */
  function parseDate(text) {
    if (!text || !text.trim()) return FAR_FUTURE;
    const d = new Date(text.trim());
    return isNaN(d.getTime()) ? FAR_FUTURE : d;
  }

  /** True when a <tr> has a cell whose sole text is "REMOVED" or "CLOSED". */
  function isRemovedOrClosed(row) {
    return Array.from(row.querySelectorAll("td")).some((td) =>
      /^\s*(removed|closed)\s*$/i.test(td.textContent)
    );
  }

  /** Apply grey / strikethrough style to a row and all its cells. */
  function greyOutRow(row) {
    Object.assign(row.style, GREY_STYLES);
    row.querySelectorAll("td, th").forEach((cell) =>
      Object.assign(cell.style, GREY_STYLES)
    );
  }

  /**
   * Return the 0-based column index whose header text best matches
   * "Target Date" or "Due Date".  Returns -1 when not found.
   */
  function findTargetDateColIndex(table) {
    const headerRow =
      table.querySelector("thead tr") ||
      table.querySelector("tbody tr:first-child");
    if (!headerRow) return -1;

    const headers = Array.from(headerRow.querySelectorAll("th, td"));

    // Prefer an exact "target date" or "due date" match
    let idx = headers.findIndex((h) =>
      /target\s*date|due\s*date/i.test(h.textContent)
    );
    if (idx !== -1) return idx;

    // Broader fallback: any header that mentions "target", "due", or "date"
    return headers.findIndex((h) =>
      /target|due|date/i.test(h.textContent)
    );
  }

  /**
   * Extract the target date from a data row.
   * Uses the known column index when available; otherwise scans every cell.
   */
  function getTargetDate(row, colIndex) {
    const cells = row.querySelectorAll("td");

    if (colIndex >= 0 && cells[colIndex]) {
      const d = parseDate(cells[colIndex].textContent);
      if (d !== FAR_FUTURE) return d;
    }

    // Fallback: scan all cells (right-to-left, target date is often last)
    let best = FAR_FUTURE;
    Array.from(cells)
      .reverse()
      .forEach((td) => {
        const d = parseDate(td.textContent);
        if (d < best) best = d;
      });
    return best;
  }

  /* ── Step 1: Rename the section title ──────────────────────────────────── */

  let renamed = false;

  // Walk text nodes directly – most reliable way to rename text
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let textNode;
  while ((textNode = walker.nextNode())) {
    if (textNode.nodeValue.includes(OLD_TITLE)) {
      textNode.nodeValue = textNode.nodeValue.replaceAll(OLD_TITLE, NEW_TITLE);
      renamed = true;
    }
  }

  if (!renamed) {
    console.warn(
      `Title "${OLD_TITLE}" not found in text nodes. ` +
      "The page may already be updated or uses a different encoding."
    );
  } else {
    console.log(`✓ Title renamed to "${NEW_TITLE}"`);
  }

  /* ── Step 2 & 3: Find the section heading, then its table ──────────────── */

  // Find the element whose text content contains the (now-renamed) title.
  // Prefer the deepest / most-specific matching element.
  let headingEl = null;
  document.body
    .querySelectorAll("h1,h2,h3,h4,h5,h6,th,td,div,span,p,caption,label")
    .forEach((el) => {
      if (
        el.textContent.includes(NEW_TITLE) &&
        // Prefer leaf-like elements (no sub-elements with the same text)
        !Array.from(el.children).some((c) => c.textContent.includes(NEW_TITLE))
      ) {
        headingEl = el;
      }
    });

  if (!headingEl) {
    // Broader fallback
    document.body.querySelectorAll("*").forEach((el) => {
      if (el.textContent.includes(NEW_TITLE)) headingEl = el;
    });
  }

  if (!headingEl) {
    console.warn(
      "Could not locate the section heading element. " +
      "Greying / sorting will NOT be applied."
    );
    return;
  }

  /**
   * Walk forward through the DOM from startEl looking for a <table>.
   * Checks next siblings (and their descendants), then moves up to the parent
   * and repeats.  Returns null when none is found.
   */
  function findNextTable(startEl) {
    let el = startEl;
    while (el) {
      let sib = el.nextElementSibling;
      while (sib) {
        if (sib.tagName === "TABLE") return sib;
        const inner = sib.querySelector("table");
        if (inner) return inner;
        sib = sib.nextElementSibling;
      }
      el = el.parentElement;
    }
    return null;
  }

  const table = findNextTable(headingEl);
  if (!table) {
    console.warn(
      "No <table> found after the section heading. " +
      "Greying / sorting will NOT be applied."
    );
    return;
  }

  const targetColIndex = findTargetDateColIndex(table);
  if (targetColIndex === -1) {
    console.warn(
      'No "Target Date" column found in table headers. ' +
      "Active rows will not be sorted (REMOVED/CLOSED will still be moved to bottom)."
    );
  }

  /* ── Process each tbody ─────────────────────────────────────────────────── */

  const tbodies = table.querySelectorAll("tbody");
  if (!tbodies.length) {
    // Fallback: treat the whole table as a single section
    processRows(table, targetColIndex);
  } else {
    tbodies.forEach((tbody) => processRows(tbody, targetColIndex));
  }

  function processRows(container, colIndex) {
    const allRows = Array.from(container.querySelectorAll(":scope > tr"));
    if (!allRows.length) return;

    const headerRows = allRows.filter((r) => r.querySelector("th"));
    const dataRows   = allRows.filter((r) => !r.querySelector("th"));
    if (!dataRows.length) return;

    const removedClosed = [];
    const active = [];

    dataRows.forEach((row) => {
      if (isRemovedOrClosed(row)) {
        greyOutRow(row);
        removedClosed.push(row);
      } else {
        active.push(row);
      }
    });

    // Stable chronological sort of active rows
    active.sort(
      (a, b) => getTargetDate(a, colIndex) - getTargetDate(b, colIndex)
    );

    // Re-insert rows in the desired order
    [...headerRows, ...active, ...removedClosed].forEach((row) =>
      container.appendChild(row)
    );
  }

  const removedCount = Array.from(table.querySelectorAll("tr")).filter(
    isRemovedOrClosed
  ).length;

  console.log(
    `✓ Done — ${removedCount} REMOVED/CLOSED row(s) greyed out and moved to ` +
    `the bottom; active rows sorted chronologically by Target Date.`
  );
  console.log(
    'Tip: Use File → Save As (or Ctrl+S) to save the updated page to disk.'
  );
})();
