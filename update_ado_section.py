"""
Transforms geico-org-chart.html in place:

  1. Renames the section title
         "ADO Features & Epics - Next 30 Days"
       → "ADO Features & Epics - Program Milestone Status"

  2. Greys out every table row whose State cell contains "REMOVED" or "CLOSED"
     (case-insensitive) and strikes through its text.

  3. Sorts table rows so that:
       • Active rows (not REMOVED/CLOSED) come first, ordered chronologically
         by the value in the "Target Date" column (earliest → latest).
       • REMOVED/CLOSED rows follow, in their original relative order.
       • Header rows (<th> cells) are always kept at the top.

Usage:
    python update_ado_section.py path/to/geico-org-chart.html

A timestamped .bak.html backup is created before the file is modified.
"""

import re
import sys
import shutil
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    "%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y",
    "%B %d, %Y", "%b %d, %Y",
    "%m/%d/%y",
    "%b %Y", "%B %Y",
)
_FAR_FUTURE = datetime(9999, 12, 31)


def _parse_date(text: str) -> datetime:
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return _FAR_FUTURE


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

_TD_TEXT_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)
_TH_TEXT_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.DOTALL | re.IGNORECASE)
_STRIP_TAGS_RE = re.compile(r"<[^>]+>")
_REMOVED_CLOSED_RE = re.compile(r">\s*(removed|closed)\s*<", re.IGNORECASE)


def _cell_text(cell_html: str) -> str:
    return _STRIP_TAGS_RE.sub("", cell_html).strip()


def _is_removed_or_closed(row_html: str) -> bool:
    return bool(_REMOVED_CLOSED_RE.search(row_html))


def _header_texts(table_html: str) -> list[str]:
    """Return the text of all <th> cells in the first header row found."""
    header_row_match = re.search(
        r"<tr[^>]*>((?:(?!</tr>).)*?<th[\s>](?:(?!</tr>).)*?)</tr>",
        table_html, re.DOTALL | re.IGNORECASE
    )
    if not header_row_match:
        return []
    return [_cell_text(m.group(0)) for m in _TH_TEXT_RE.finditer(header_row_match.group(0))]


def _target_date_col_index(header_texts: list[str]) -> int:
    """Return the 0-based column index whose header best matches 'target date'."""
    for i, h in enumerate(header_texts):
        if re.search(r"target\s*date|due\s*date", h, re.IGNORECASE):
            return i
    for i, h in enumerate(header_texts):
        if re.search(r"target|due|date", h, re.IGNORECASE):
            return i
    return -1


def _extract_target_date(row_html: str, col_index: int) -> datetime:
    cells = _TD_TEXT_RE.findall(row_html)
    cell_texts = [_cell_text(c) for c in cells]

    if 0 <= col_index < len(cell_texts):
        d = _parse_date(cell_texts[col_index])
        if d != _FAR_FUTURE:
            return d

    # Fallback: scan all cells for a parseable date
    for text in reversed(cell_texts):
        d = _parse_date(text)
        if d != _FAR_FUTURE:
            return d

    return _FAR_FUTURE


# ---------------------------------------------------------------------------
# Greying-out
# ---------------------------------------------------------------------------

_GREY_STYLE = (
    "color:#999999;"
    "background-color:#f0f0f0;"
    "text-decoration:line-through;"
    "opacity:0.6;"
)


def _apply_grey_style(row_html: str) -> str:
    """Inject/append greying style to the opening <tr> tag."""

    def _patch_tr(m: re.Match) -> str:
        tag = m.group(0)
        style_match = re.search(r'(style\s*=\s*)(["\'])([^"\']*?)(\2)', tag, re.IGNORECASE)
        if style_match:
            existing = style_match.group(3).rstrip(";")
            replacement = (
                style_match.group(1)
                + style_match.group(2)
                + existing + "; " + _GREY_STYLE
                + style_match.group(4)
            )
            tag = tag[: style_match.start()] + replacement + tag[style_match.end():]
        else:
            tag = tag[:-1] + f' style="{_GREY_STYLE}">'
        return tag

    return re.sub(r"<tr[^>]*>", _patch_tr, row_html, count=1, flags=re.IGNORECASE)


# ---------------------------------------------------------------------------
# tbody processing
# ---------------------------------------------------------------------------

_TR_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.DOTALL | re.IGNORECASE)
_TH_IN_ROW_RE = re.compile(r"<th[\s>]", re.IGNORECASE)
_TBODY_RE = re.compile(r"(<tbody[^>]*>)(.*?)(</tbody>)", re.DOTALL | re.IGNORECASE)
_TABLE_RE = re.compile(r"(<table[^>]*>)(.*?)(</table>)", re.DOTALL | re.IGNORECASE)


def _process_tbody(tb_open: str, tb_body: str, tb_close: str, col_index: int) -> str:
    rows = _TR_RE.findall(tb_body)
    if not rows:
        return tb_open + tb_body + tb_close

    header_rows = [r for r in rows if _TH_IN_ROW_RE.search(r)]
    data_rows = [r for r in rows if not _TH_IN_ROW_RE.search(r)]

    removed_closed: list[str] = []
    active: list[str] = []

    for row in data_rows:
        if _is_removed_or_closed(row):
            removed_closed.append(_apply_grey_style(row))
        else:
            active.append(row)

    active.sort(key=lambda r: _extract_target_date(r, col_index))

    sorted_rows = header_rows + active + removed_closed
    return tb_open + "\n" + "\n".join(sorted_rows) + "\n" + tb_close


def _process_table(table_match: re.Match) -> str:
    open_tag = table_match.group(1)
    inner = table_match.group(2)
    close_tag = table_match.group(3)

    header_texts = _header_texts(open_tag + inner + close_tag)
    col_index = _target_date_col_index(header_texts)

    def _replace_tbody(m: re.Match) -> str:
        return _process_tbody(m.group(1), m.group(2), m.group(3), col_index)

    new_inner = _TBODY_RE.sub(_replace_tbody, inner)
    return open_tag + new_inner + close_tag


# ---------------------------------------------------------------------------
# Main transformation
# ---------------------------------------------------------------------------

_OLD_TITLE_AMP = "ADO Features &amp; Epics - Next 30 Days"
_NEW_TITLE_AMP = "ADO Features &amp; Epics - Program Milestone Status"
_OLD_TITLE_RAW = "ADO Features & Epics - Next 30 Days"
_NEW_TITLE_RAW = "ADO Features & Epics - Program Milestone Status"

_SECTION_RE = re.compile(
    r"ADO\s+Features\s*(?:&amp;|&)\s*Epics\s*[-–]\s*Program Milestone Status",
    re.IGNORECASE,
)


def transform_html(html: str) -> str:
    # 1. Rename the title (both escaped and unescaped ampersand variants)
    html = html.replace(_OLD_TITLE_AMP, _NEW_TITLE_AMP)
    html = html.replace(_OLD_TITLE_RAW, _NEW_TITLE_RAW)

    # 2 & 3. Find the section heading, then process the first table that follows.
    title_match = _SECTION_RE.search(html)
    if not title_match:
        print(
            "WARNING: Section heading not found after rename. "
            "Greying/sorting were NOT applied."
        )
        return html

    before = html[: title_match.end()]
    after = html[title_match.end():]

    first_table = _TABLE_RE.search(after)
    if not first_table:
        print(
            "WARNING: No <table> found after the section heading. "
            "Greying/sorting were NOT applied."
        )
        return html

    processed = _process_table(first_table)
    after = after[: first_table.start()] + processed + after[first_table.end():]
    return before + after


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python update_ado_section.py <path-to-html-file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        sys.exit(1)

    backup_path = file_path.with_suffix(".bak.html")
    shutil.copy2(file_path, backup_path)
    print(f"Backup created: {backup_path}")

    html = file_path.read_text(encoding="utf-8", errors="replace")
    updated = transform_html(html)

    file_path.write_text(updated, encoding="utf-8")
    print(f"Done — updated file written to: {file_path}")


if __name__ == "__main__":
    main()
