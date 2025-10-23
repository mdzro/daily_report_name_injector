
import hmac
import os
import tempfile
from pathlib import Path
import pandas as pd
from flask import (
    Flask,
    request,
    send_file,
    jsonify,
    send_from_directory,
    session,
)
from bs4 import BeautifulSoup

def load_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    with env_path.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip()


load_env()


app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_BUILD = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "build"))
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD")


@app.before_request
def enforce_password_protection():
    open_endpoints = {"login", "health", "session_status", "serve_frontend"}
    if request.endpoint in open_endpoints or request.method == "OPTIONS":
        return
    if session.get("authenticated"):
        return
    return jsonify({"error": "Unauthorized"}), 401

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
    if not session.get("authenticated"):
        return jsonify({"error": "Unauthorized"}), 401
    html_file = request.files.get("html_file")
    excel_file = request.files.get("excel_file")
    if not html_file or not excel_file:
        return jsonify({"error": "Both HTML and Excel files are required"}), 400
    out_path = process_files(html_file, excel_file)
    return send_file(out_path, as_attachment=True, download_name="report_with_names.html")


@app.route("/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    password = payload.get("password")
    stored_password = ACCESS_PASSWORD or ""
    if not password or not stored_password or not hmac.compare_digest(str(password), str(stored_password)):
        session.pop("authenticated", None)
        return jsonify({"success": False, "error": "Invalid password"}), 401
    session["authenticated"] = True
    return jsonify({"success": True})


@app.route("/session", methods=["GET"])
def session_status():
    return jsonify({"authenticated": bool(session.get("authenticated"))})

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
