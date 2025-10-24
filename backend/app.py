
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

def process_files(html_file, excel_file):
    # Read Excel mapping (exact headers: Transporter ID, Name)
    names_df = pd.read_excel(excel_file)
    names_df.columns = [c.strip() for c in names_df.columns]
    name_map = dict(zip(names_df["Transporter ID"].astype(str), names_df["Name"].astype(str)))

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
        headers = [th.get_text(strip=True) for th in header_cells]
        transporter_index = headers.index("Transporter ID")

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

        # Always place the Name header immediately after Transporter ID
        if len(header_cells) <= transporter_index + 1 or header_cells[transporter_index + 1].get_text(strip=True) != "Name":
            name_th = soup.new_tag("th")
            name_th.string = "Name"
            header_cells[transporter_index].insert_after(name_th)
            header_cells = header_row.find_all("th")

        name_col_index = transporter_index + 1

        # Insert or update the Name cell for each data row
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds or len(tds) <= transporter_index:
                continue
            transporter_id = tds[transporter_index].get_text(strip=True)
            name_val = name_map.get(transporter_id, "")

            if len(tds) > name_col_index:
                tds[name_col_index].string = name_val
            else:
                name_td = soup.new_tag("td")
                name_td.string = name_val
                tds[transporter_index].insert_after(name_td)

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
