
import os
import secrets
import tempfile
import pandas as pd
from flask import (
    Flask,
    jsonify,
    request,
    send_file,
    send_from_directory,
    session,
)
from bs4 import BeautifulSoup
from dotenv import load_dotenv

app = Flask(__name__, static_folder=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_BUILD = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "build"))

load_dotenv()

ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD")
if not ACCESS_PASSWORD:
    raise RuntimeError("ACCESS_PASSWORD environment variable must be set")

app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))


def _is_authenticated():
    return session.get("authenticated", False)


def _get_span_value(cell, attr):
    try:
        return int(cell.get(attr, 1))
    except (TypeError, ValueError):
        return 1


def _iter_cells_with_positions(rows, cell_tags=("td", "th"), span_map=None):
    span_map = {} if span_map is None else span_map
    for tr in rows:
        layout = []
        col_idx = 0
        direct_cells = [cell for cell in tr.find_all(cell_tags, recursive=False)]
        cell_index = 0

        while cell_index < len(direct_cells):
            while col_idx in span_map:
                span_info = span_map[col_idx]
                layout.append(
                    {
                        "cell": span_info["cell"],
                        "column": col_idx,
                        "origin": "span",
                    }
                )
                span_info["remaining"] -= 1
                if span_info["remaining"] == 0:
                    del span_map[col_idx]
                col_idx += 1

            cell = direct_cells[cell_index]
            colspan = _get_span_value(cell, "colspan")
            rowspan = _get_span_value(cell, "rowspan")

            for offset in range(colspan):
                current_col = col_idx + offset
                layout.append({"cell": cell, "column": current_col, "origin": "direct"})
                if rowspan > 1:
                    span_map[current_col] = {
                        "cell": cell,
                        "remaining": rowspan - 1,
                    }

            col_idx += colspan
            cell_index += 1

        while True:
            remaining_cols = [idx for idx in span_map if idx >= col_idx]
            if not remaining_cols:
                break
            next_col = min(remaining_cols)
            while col_idx < next_col:
                col_idx += 1
            span_info = span_map[next_col]
            layout.append(
                {
                    "cell": span_info["cell"],
                    "column": next_col,
                    "origin": "span",
                }
            )
            span_info["remaining"] -= 1
            if span_info["remaining"] == 0:
                del span_map[next_col]
            col_idx = next_col + 1

        yield tr, sorted(layout, key=lambda entry: entry["column"])


def _shift_span_map(span_map, start_index):
    if not span_map:
        return
    shifted = {}
    for col, info in span_map.items():
        if col >= start_index:
            shifted[col + 1] = info
        else:
            shifted[col] = info
    span_map.clear()
    span_map.update(shifted)


@app.before_request
def require_authentication():
    if request.method == "OPTIONS":
        return None

    endpoint = request.endpoint or ""
    public_endpoints = {"login", "logout", "auth_status", "health", "serve_frontend"}
    if endpoint in public_endpoints:
        return None

    # Allow serving built static assets required to render the login page
    if request.path.startswith("/static") or request.path.startswith("/assets"):
        return None

    if not _is_authenticated():
        return jsonify({"error": "Authentication required"}), 401


@app.route("/auth/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    password = payload.get("password")
    if not password:
        return jsonify({"error": "Password is required"}), 400
    if password != ACCESS_PASSWORD:
        return jsonify({"error": "Invalid password"}), 401

    session["authenticated"] = True
    return jsonify({"authenticated": True}), 200


@app.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"authenticated": False}), 200


@app.route("/auth/status", methods=["GET"])
def auth_status():
    return jsonify({"authenticated": _is_authenticated()}), 200

def _candidate_transporter_keys(raw_value):
    if not raw_value:
        return []

    base_value = raw_value.strip()
    if not base_value:
        return []

    keys = [base_value]

    collapsed_spaces = " ".join(base_value.split())
    if collapsed_spaces and collapsed_spaces not in keys:
        keys.append(collapsed_spaces)

    digits_only = "".join(ch for ch in base_value if ch.isdigit())
    if digits_only and digits_only not in keys:
        keys.append(digits_only)

    if digits_only:
        stripped_digits = digits_only.lstrip("0") or "0"
        if stripped_digits and stripped_digits not in keys:
            keys.append(stripped_digits)

    return keys


def process_files(html_file, excel_file):
    # Read Excel mapping (exact headers: Transporter ID, Name)
    names_df = pd.read_excel(excel_file, dtype=str)
    names_df.columns = [c.strip() for c in names_df.columns]
    names_df = names_df.fillna("")

    def _normalize_cell(value):
        if value is None:
            return ""
        return str(value).strip()

    transporter_ids = (
        names_df.get("Transporter ID", pd.Series(dtype=str))
        .map(_normalize_cell)
        .reset_index(drop=True)
    )
    transporter_names = (
        names_df.get("Name", pd.Series(dtype=str))
        .map(_normalize_cell)
        .reset_index(drop=True)
    )

    name_map = {}
    for idx, transporter_id in transporter_ids.items():
        if not transporter_id:
            continue

        name_value = transporter_names.iloc[idx]
        if not name_value:
            continue

        for key in _candidate_transporter_keys(transporter_id):
            name_map.setdefault(key, name_value)

    soup = BeautifulSoup(html_file.read(), "html.parser")

    enhanced_table_ids = []
    table_counter = 0

    # For every table that has a 'Transporter ID' header
    for table in soup.find_all("table"):
        header_row = None
        for tr in table.find_all("tr"):
            ths = tr.find_all("th")
            if any(th.get_text(strip=True) == "Transporter ID" for th in ths):
                header_row = tr
                break
        if not header_row:
            continue

        header_cells = header_row.find_all("th")
        transporter_index = None
        transporter_header_cell = None
        current_col = 0
        for th in header_cells:
            header_text = th.get_text(strip=True)
            colspan = _get_span_value(th, "colspan")
            if header_text == "Transporter ID":
                transporter_index = current_col
                transporter_header_cell = th
                break
            current_col += colspan

        if transporter_index is None:
            continue

        name_col_index = transporter_index + 1

        # Ensure the header row is inside a <thead>
        if header_row.parent.name != "thead":
            thead = soup.new_tag("thead")
            header_row.wrap(thead)

        # Ensure a <tbody> exists for easier scripting
        tbody = table.find("tbody")
        if not tbody:
            tbody = soup.new_tag("tbody")
            data_rows = []
            for candidate_row in table.find_all("tr"):
                if candidate_row is header_row:
                    continue
                if candidate_row.find_parent("thead"):
                    continue
                if candidate_row.find_all("td"):
                    data_rows.append(candidate_row)
            for row in data_rows:
                tbody.append(row.extract())
            table.append(tbody)

        header_layout_iter = _iter_cells_with_positions([header_row], ("th",), {})
        try:
            _, header_layout = next(header_layout_iter)
        except StopIteration:
            header_layout = []
        existing_name_entry = next(
            (
                entry
                for entry in header_layout
                if entry["column"] == name_col_index
                and entry["cell"].get_text(strip=True) == "Name"
            ),
            None,
        )

        if existing_name_entry:
            name_header_cell = existing_name_entry["cell"]
        else:
            name_header_cell = soup.new_tag("th")
            name_header_cell.string = "Name"
            if transporter_header_cell:
                for attr, value in transporter_header_cell.attrs.items():
                    if attr in {"colspan", "id"}:
                        continue
                    if attr == "class":
                        name_header_cell[attr] = (
                            list(value) if isinstance(value, (list, tuple)) else value
                        )
                    else:
                        name_header_cell[attr] = value
            transporter_header_cell.insert_after(name_header_cell)

        header_rows = []
        for candidate in table.find_all("tr"):
            if candidate.find_all("th"):
                header_rows.append(candidate)
            elif header_rows:
                break

        header_span_tracker = {}
        cell_column_map = {}
        for _, row_entries in _iter_cells_with_positions(
            header_rows, ("th",), header_span_tracker
        ):
            for entry in row_entries:
                cell_column_map.setdefault(entry["cell"], set()).add(entry["column"])

        for cell, columns in cell_column_map.items():
            if cell in {transporter_header_cell, name_header_cell}:
                continue
            if transporter_index in columns:
                updated_colspan = _get_span_value(cell, "colspan") + 1
                cell["colspan"] = str(updated_colspan)

        for tbody_section in table.find_all("tbody"):
            body_span_tracker = {}
            for tr, layout in _iter_cells_with_positions(
                tbody_section.find_all("tr"), ("td", "th"), body_span_tracker
            ):
                if not tr.find_all("td"):
                    continue

                transporter_entry = next(
                    (entry for entry in layout if entry["column"] == transporter_index),
                    None,
                )
                if not transporter_entry:
                    continue

                transporter_cell = transporter_entry["cell"]
                if (
                    transporter_entry["origin"] != "direct"
                    or transporter_cell.parent is not tr
                ):
                    continue

                transporter_id = transporter_cell.get_text(strip=True)

                name_val = ""
                for key in _candidate_transporter_keys(transporter_id):
                    if key in name_map:
                        name_val = name_map[key]
                        break

                name_entry = next(
                    (entry for entry in layout if entry["column"] == name_col_index),
                    None,
                )

                if (
                    name_entry
                    and name_entry["origin"] == "direct"
                    and name_entry["cell"].parent is tr
                ):
                    name_cell = name_entry["cell"]
                    name_cell.clear()
                    name_cell.append(name_val)
                    continue

                name_td = soup.new_tag("td")
                name_td.string = name_val
                transporter_cell.insert_after(name_td)

                transporter_rowspan = _get_span_value(transporter_cell, "rowspan")
                if transporter_rowspan > 1:
                    name_td["rowspan"] = transporter_rowspan

                _shift_span_map(body_span_tracker, name_col_index)

                if transporter_rowspan > 1:
                    body_span_tracker[name_col_index] = {
                        "cell": name_td,
                        "remaining": transporter_rowspan - 1,
                    }

        table_classes = table.get("class", [])
        if "modern-table" not in table_classes:
            table_classes.append("modern-table")
            table["class"] = table_classes

        table_id = table.get("id")
        if not table_id:
            table_counter += 1
            table_id = f"enhanced-table-{table_counter}"
            table["id"] = table_id

        enhanced_table_ids.append(table_id)

        # Wrap table with container and add search input if not already present
        parent_container = table.find_parent("div", class_="table-enhanced-container")
        if not parent_container:
            container = soup.new_tag("div", attrs={"class": "table-enhanced-container"})
            table.wrap(container)
            search_wrapper = soup.new_tag("div", attrs={"class": "table-search-wrapper"})
            search_input = soup.new_tag(
                "input",
                attrs={
                    "type": "search",
                    "placeholder": "Search table...",
                    "class": "table-search-input",
                    "data-target": table_id,
                },
            )
            search_wrapper.append(search_input)
            container = table.find_parent("div", class_="table-enhanced-container")
            container.insert(0, search_wrapper)
        else:
            # Ensure the search input targets the correct table id
            search_input = parent_container.find("input", class_="table-search-input")
            if search_input:
                search_input["data-target"] = table_id

    if enhanced_table_ids:
        # Inject modern table styles if not already present
        if not soup.find("style", id="enhanced-table-styles"):
            style_tag = soup.new_tag("style", id="enhanced-table-styles")
            style_tag.string = """
.table-enhanced-container {
  margin: 2.5rem 0;
  padding: 2rem;
  border-radius: 1.25rem;
  border: 1px solid #e5e7eb;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: 0 18px 45px -20px rgba(15, 23, 42, 0.35);
}

.table-search-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 1rem;
}

.table-search-input {
  width: 100%;
  max-width: 260px;
  padding: 0.65rem 1rem;
  border-radius: 9999px;
  border: 1px solid #cbd5f5;
  background-color: rgba(241, 245, 249, 0.8);
  color: #0f172a;
  font-size: 0.95rem;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.table-search-input:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
  background-color: #ffffff;
}

table.modern-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  overflow: hidden;
}

table.modern-table thead th {
  background: linear-gradient(135deg, #4338ca, #2563eb);
  color: #f8fafc;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.75rem;
  padding: 0.9rem 1rem;
  position: relative;
  cursor: pointer;
  user-select: none;
}

table.modern-table thead th::after {
  content: '';
  position: absolute;
  right: 1rem;
  top: 50%;
  transform: translateY(-50%);
  border: 4px solid transparent;
  border-top-color: rgba(248, 250, 252, 0.6);
  opacity: 0;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

table.modern-table thead th[data-sort-direction="asc"]::after {
  opacity: 1;
  transform: translateY(-50%) rotate(180deg);
}

table.modern-table thead th[data-sort-direction="desc"]::after {
  opacity: 1;
}

table.modern-table tbody tr {
  background-color: rgba(248, 250, 252, 0.7);
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

table.modern-table tbody tr:nth-child(even) {
  background-color: rgba(226, 232, 240, 0.6);
}

table.modern-table tbody tr:hover {
  background-color: #eef2ff;
  transform: translateY(-2px);
  box-shadow: 0 12px 24px -16px rgba(37, 99, 235, 0.45);
}

table.modern-table td {
  padding: 0.85rem 1rem;
  color: #1e293b;
  font-size: 0.92rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.3);
}

table.modern-table tbody tr:last-child td {
  border-bottom: none;
}
"""
            if soup.head:
                soup.head.append(style_tag)
            else:
                soup.insert(0, style_tag)

        # Inject sorting and search script if not already present
        if not soup.find("script", id="enhanced-table-script"):
            script_tag = soup.new_tag("script", id="enhanced-table-script")
            script_tag.string = """
document.addEventListener('DOMContentLoaded', function () {
  const getCellValue = (row, index) => {
    const cell = row.cells[index];
    if (!cell) return '';
    return cell.textContent.trim();
  };

  const isNumeric = (value) => {
    if (!value) return false;
    const number = Number(value.replace(/[^0-9.-]+/g, ''));
    return !Number.isNaN(number) && value.match(/[0-9]/);
  };

  document.querySelectorAll('table.modern-table').forEach((table) => {
    const headers = table.querySelectorAll('thead th');
    headers.forEach((header, columnIndex) => {
      header.addEventListener('click', () => {
        const tbody = table.tBodies[0];
        if (!tbody) return;

        const currentDirection = header.getAttribute('data-sort-direction');
        const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';

        headers.forEach((h) => h.removeAttribute('data-sort-direction'));
        header.setAttribute('data-sort-direction', newDirection);

        const rows = Array.from(tbody.rows);
        const multiplier = newDirection === 'asc' ? 1 : -1;

        rows.sort((rowA, rowB) => {
          const aValue = getCellValue(rowA, columnIndex);
          const bValue = getCellValue(rowB, columnIndex);

          const aNumeric = isNumeric(aValue);
          const bNumeric = isNumeric(bValue);

          if (aNumeric && bNumeric) {
            const aNumber = Number(aValue.replace(/[^0-9.-]+/g, ''));
            const bNumber = Number(bValue.replace(/[^0-9.-]+/g, ''));
            return (aNumber - bNumber) * multiplier;
          }

          return aValue.localeCompare(bValue, undefined, { sensitivity: 'base' }) * multiplier;
        });

        rows.forEach((row) => tbody.appendChild(row));
      });
    });
  });

  document.querySelectorAll('.table-search-input').forEach((input) => {
    const targetId = input.getAttribute('data-target');
    const table = document.getElementById(targetId);
    if (!table) return;

    const tbody = table.tBodies[0];
    if (!tbody) return;

    input.addEventListener('input', () => {
      const query = input.value.trim().toLowerCase();
      Array.from(tbody.rows).forEach((row) => {
        const text = row.textContent.trim().toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  });
});
"""
            if soup.body:
                soup.body.append(script_tag)
            else:
                soup.append(script_tag)

    # Save to temp file
    out_path = tempfile.NamedTemporaryFile(delete=False, suffix="_with_names.html").name
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(str(soup))
    return out_path

@app.route("/process", methods=["POST"])
def process():
    html_file = request.files.get("html_file")
    excel_file = request.files.get("excel_file")
    if not html_file or not excel_file:
        return jsonify({"error": "Both HTML and Excel files are required"}), 400
    out_path = process_files(html_file, excel_file)
    return send_file(out_path, as_attachment=True, download_name="report_with_names.html")

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path and os.path.exists(os.path.join(FRONTEND_BUILD, path)):
        return send_from_directory(FRONTEND_BUILD, path)
    return send_from_directory(FRONTEND_BUILD, "index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
