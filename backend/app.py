
import os
import tempfile
import pandas as pd
from flask import Flask, request, send_file, jsonify, send_from_directory
from bs4 import BeautifulSoup

app = Flask(__name__, static_folder=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_BUILD = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "build"))

def process_files(html_file, excel_file):
    # Read Excel mapping (exact headers: Transporter ID, Name)
    names_df = pd.read_excel(excel_file)
    names_df.columns = [c.strip() for c in names_df.columns]
    name_map = dict(zip(names_df["Transporter ID"].astype(str), names_df["Name"].astype(str)))

    soup = BeautifulSoup(html_file.read(), "html.parser")

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

        # Always insert a Name header immediately after Transporter ID
        name_th = soup.new_tag("th")
        name_th.string = "Name"
        header_cells[transporter_index].insert_after(name_th)

        # Insert Name cell for each data row
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds or len(tds) <= transporter_index:
                continue
            transporter_id = tds[transporter_index].get_text(strip=True)
            name_val = name_map.get(transporter_id, "")
            name_td = soup.new_tag("td")
            name_td.string = name_val
            tds[transporter_index].insert_after(name_td)

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
