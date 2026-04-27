/**
 * Paste this entire script into your browser's DevTools console while
 * geico-org-chart.html is open.  It will:
 *
 *   1. Rename "ADO Features & Epics - Next 30 Days"
 *      → "ADO Features & Epics - Program Milestone Status"
 *
 *   2. Grey out every row whose State cell contains "REMOVED" or "CLOSED"
 *      (case-insensitive).
 *
 *   3. Sort rows so REMOVED/CLOSED items sink to the bottom, while
 *      everything above them is sorted chronologically by Target Date
 *      (ascending – earliest date first).
 */
(function () {
  "use strict";

  // ── 1. Rename the section title ──────────────────────────────────────────
  const OLD_TITLE = "ADO Features & Epics - Next 30 Days";
  const NEW_TITLE = "ADO Features & Epics - Program Milestone Status";

  // Walk all text nodes and element text content
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (node.nodeValue.includes(OLD_TITLE)) {
      node.nodeValue = node.nodeValue.replace(OLD_TITLE, NEW_TITLE);
    }
  }
  // Also patch any innerHTML that may have used &amp;
  document.body.querySelectorAll("*").forEach((el) => {
    if (el.childNodes.length === 1 && el.childNodes[0].nodeType === Node.TEXT_NODE) {
      if (el.textContent.includes(OLD_TITLE)) {
        el.textContent = el.textContent.replace(OLD_TITLE, NEW_TITLE);
      }
    }
  });

  // ── Helpers ───────────────────────────────────────────────────────────────
  function parseDate(text) {
    if (!text) return new Date(9998, 11, 31);
    const d = new Date(text.trim());
    return isNaN(d.getTime()) ? new Date(9998, 11, 31) : d;
  }

  function isRemovedOrClosed(row) {
    return Array.from(row.querySelectorAll("td")).some((td) =>
      /^\s*(removed|closed)\s*$/i.test(td.textContent)
    );
  }

  function greyOutRow(row) {
    row.style.color = "#999999";
    row.style.backgroundColor = "#f0f0f0";
    row.style.textDecoration = "line-through";
    row.querySelectorAll("td").forEach((td) => {
      td.style.color = "#999999";
    });
  }

  /**
   * Extract a target date from a row.
   * Strategy: look for the column whose header (in the same table) is
   * labelled something like "Target Date", "Target", "Due Date", etc.
   * Fall back to scanning every cell for a parseable date.
   */
  function getTargetDate(row, targetColIndex) {
    const cells = row.querySelectorAll("td");
    if (targetColIndex >= 0 && cells[targetColIndex]) {
      return parseDate(cells[targetColIndex].textContent);
    }
    // Fallback: last date-looking cell
    let best = new Date(9998, 11, 31);
    cells.forEach((td) => {
      const d = parseDate(td.textContent);
      if (d.getFullYear() !== 9998) best = d;
    });
    return best;
  }

  /**
   * Return the column index (0-based) that matches a "target date" header,
   * or -1 if none found.
   */
  function findTargetDateColumnIndex(table) {
    const headerRow = table.querySelector("thead tr, tbody tr:first-child");
    if (!headerRow) return -1;
    const headers = Array.from(headerRow.querySelectorAll("th, td"));
    return headers.findIndex((h) =>
      /target\s*date|due\s*date|target/i.test(h.textContent)
    );
  }

  // ── 2 & 3. Find the right section and process its table ──────────────────

  // Locate the section heading element
  let sectionHeading = null;
  document.body.querySelectorAll("*").forEach((el) => {
    if (
      el.textContent.trim().includes(NEW_TITLE) &&
      el.children.length === 0 // leaf text node container
    ) {
      sectionHeading = el;
    }
  });

  // Also try headings / elements with the title text (broader search)
  if (!sectionHeading) {
    document.body.querySelectorAll("h1,h2,h3,h4,h5,h6,th,td,div,span,p").forEach((el) => {
      if (el.textContent.includes(NEW_TITLE)) sectionHeading = el;
    });
  }

  if (!sectionHeading) {
    console.warn("Could not locate the section heading. Title was renamed but table was not sorted.");
    return;
  }

  // Walk forward in the DOM from the heading to find the next <table>
  function findNextTable(startEl) {
    let el = startEl;
    while (el) {
      // Try next sibling, then parent's next sibling, etc.
      if (el.nextElementSibling) {
        el = el.nextElementSibling;
        if (el.tagName === "TABLE") return el;
        const inner = el.querySelector("table");
        if (inner) return inner;
      } else {
        el = el.parentElement;
        if (!el) break;
      }
    }
    return null;
  }

  const table = findNextTable(sectionHeading) || document.querySelector("table");
  if (!table) {
    console.warn("No table found near the section heading.");
    return;
  }

  const targetColIndex = findTargetDateColumnIndex(table);

  // Process each tbody in the table
  const tbodies = table.querySelectorAll("tbody");
  tbodies.forEach((tbody) => {
    const allRows = Array.from(tbody.querySelectorAll("tr"));
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

    // Sort active rows by target date ascending
    active.sort(
      (a, b) =>
        getTargetDate(a, targetColIndex) - getTargetDate(b, targetColIndex)
    );

    // Re-append in desired order
    [...headerRows, ...active, ...removedClosed].forEach((row) =>
      tbody.appendChild(row)
    );
  });

  console.log("✓ Section title renamed, REMOVED/CLOSED rows greyed out and moved to bottom, active rows sorted by target date.");
})();
