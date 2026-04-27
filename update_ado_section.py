"""
Script to update the ADO Features & Epics section in geico-org-chart.html:
  1. Rename section title from "ADO Features & Epics - Next 30 Days"
     to "ADO Features & Epics - Program Milestone Status"
  2. Grey out any rows with state REMOVED or CLOSED
  3. Sort rows so REMOVED/CLOSED items are at the bottom,
     and everything above them is in chronological order by TARGET DATE

Usage:
    python update_ado_section.py path/to/geico-org-chart.html

The script writes the modified content back to the same file (a .bak backup is
created first).
"""

import re
import sys
import shutil
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_date(text: str) -> datetime:
    """Try several common date formats; return a far-future date on failure."""
    text = text.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y",
                "%m/%d/%y", "%b %Y", "%B %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    # Unparseable dates go to the end (before removed/closed)
    return datetime(9998, 12, 31)


def is_removed_or_closed(row_html: str) -> bool:
    """Return True if the row contains a state cell with REMOVED or CLOSED."""
    lowered = row_html.lower()
    # Look for common patterns: a <td> whose text content is 'removed' or 'closed'
    return bool(re.search(r'>\s*(removed|closed)\s*<', lowered))


def extract_target_date(row_html: str) -> datetime:
    """
    Try to pull the target date out of the row HTML.
    Heuristic: look for the last column that looks like a date,
    or a <td> preceded by a header labelled 'target date'.
    Falls back to far-future date if none found.
    """
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)
    # Strip inner tags
    cell_texts = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]

    # Walk cells in reverse – target date is often one of the last columns
    for text in reversed(cell_texts):
        d = parse_date(text)
        if d.year != 9998:
            return d
    return datetime(9998, 12, 31)


def apply_grey_style(row_html: str) -> str:
    """
    Add inline style to grey out a <tr> row and its cells.
    If the <tr> already has a style attribute, append to it;
    otherwise add a new one.
    """
    grey_style = "color:#999999; background-color:#f0f0f0; text-decoration:line-through;"

    # Modify the opening <tr ...> tag
    def replace_tr(m):
        tag = m.group(0)
        if 'style=' in tag.lower():
            # Append to existing style value
            tag = re.sub(
                r'(style\s*=\s*["\'])([^"\']*?)(["\'])',
                lambda sm: sm.group(1) + sm.group(2).rstrip(';') + '; ' + grey_style + sm.group(3),
                tag, flags=re.IGNORECASE
            )
        else:
            tag = tag.rstrip('>').rstrip() + f' style="{grey_style}">'
        return tag

    row_html = re.sub(r'<tr[^>]*>', replace_tr, row_html, count=1, flags=re.IGNORECASE)
    return row_html


# ---------------------------------------------------------------------------
# Main transformation
# ---------------------------------------------------------------------------

def transform_html(html: str) -> str:
    # -----------------------------------------------------------------------
    # 1. Rename section title
    # -----------------------------------------------------------------------
    old_title = "ADO Features &amp; Epics - Next 30 Days"
    new_title = "ADO Features &amp; Epics - Program Milestone Status"
    # Also handle the non-escaped ampersand variant
    html = html.replace(old_title, new_title)
    html = html.replace(
        "ADO Features & Epics - Next 30 Days",
        "ADO Features & Epics - Program Milestone Status"
    )

    # -----------------------------------------------------------------------
    # 2 & 3. Find the table(s) inside the ADO Features section, then
    #         grey-out + sort rows.
    #
    # Strategy: locate the section heading, find the next <table>, reorder
    # its <tbody> rows.
    # -----------------------------------------------------------------------

    # Find all table bodies – we'll work on each one that belongs to the section.
    # Robust approach: find the section by its (new) title, then find the next table.

    section_pattern = re.compile(
        r'(ADO Features(?:\s*&amp;|\s*&)\s*Epics\s*[-–]\s*Program Milestone Status)',
        re.IGNORECASE
    )

    # Split the HTML at each <table … </table> boundary so we can identify
    # which table(s) follow the section header.
    table_pattern = re.compile(r'(<table[^>]*>)(.*?)(</table>)', re.DOTALL | re.IGNORECASE)

    def process_table(table_match):
        open_tag = table_match.group(1)
        body     = table_match.group(2)
        close_tag = table_match.group(3)

        # Find tbody sections
        tbody_pattern = re.compile(r'(<tbody[^>]*>)(.*?)(</tbody>)', re.DOTALL | re.IGNORECASE)

        def process_tbody(tbody_match):
            tb_open  = tbody_match.group(1)
            tb_body  = tbody_match.group(2)
            tb_close = tbody_match.group(3)

            # Split into individual rows (keep the full <tr>…</tr> blocks)
            rows = re.findall(r'<tr[^>]*>.*?</tr>', tb_body, re.DOTALL | re.IGNORECASE)
            if not rows:
                return tbody_match.group(0)

            # Separate header rows (containing <th>) from data rows
            header_rows = [r for r in rows if re.search(r'<th[\s>]', r, re.IGNORECASE)]
            data_rows   = [r for r in rows if not re.search(r'<th[\s>]', r, re.IGNORECASE)]

            if not data_rows:
                return tbody_match.group(0)

            removed_closed = []
            active = []
            for row in data_rows:
                if is_removed_or_closed(row):
                    removed_closed.append(apply_grey_style(row))
                else:
                    active.append(row)

            # Sort active rows chronologically by target date
            active.sort(key=extract_target_date)

            sorted_rows = header_rows + active + removed_closed
            new_tb_body = '\n'.join(sorted_rows)
            return tb_open + '\n' + new_tb_body + '\n' + tb_close

        new_body = tbody_pattern.sub(process_tbody, body)
        return open_tag + new_body + close_tag

    # We only want to process tables that come AFTER the section heading.
    # Split the document at the first occurrence of the section title.
    title_match = section_pattern.search(html)
    if title_match:
        before = html[:title_match.end()]
        after  = html[title_match.end():]

        # Find the first table in `after` and process it
        first_table = table_pattern.search(after)
        if first_table:
            processed_table = process_table(first_table)
            after = after[:first_table.start()] + processed_table + after[first_table.end():]

        html = before + after
    else:
        print("WARNING: Section heading not found. "
              "Only the title rename will be applied.")

    return html


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python update_ado_section.py <path-to-html-file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        sys.exit(1)

    # Backup
    backup_path = file_path.with_suffix('.bak.html')
    shutil.copy2(file_path, backup_path)
    print(f"Backup created: {backup_path}")

    html = file_path.read_text(encoding='utf-8', errors='replace')
    updated_html = transform_html(html)

    file_path.write_text(updated_html, encoding='utf-8')
    print(f"Done! Updated file written to: {file_path}")


if __name__ == '__main__':
    main()
