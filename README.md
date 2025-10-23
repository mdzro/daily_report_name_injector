
# 🧩 Daily Report Name Injector (Fixed)

Upload your HTML daily report + `names.xlsx` and get back a new HTML where every table
that contains a **Transporter ID** column will also have a **Name** column (filled via mapping).

## 🚀 Quick start (Docker)
```bash
docker-compose up --build
# open http://localhost:5000
```

## 🧪 Dev mode
- Flask API: http://localhost:5000
- React dev server (optional): runs on port 45389 (see `frontend/package.json`), use `/process` for API.

## 🔐 Configuration
Create a `.env` file in the project root before starting the server:

```
ACCESS_PASSWORD=ABC99amzl00
# Optional: override the Flask session secret
# FLASK_SECRET_KEY=replace-me

# Values can be wrapped in single or double quotes if needed.
```

The `.env` file is ignored by git to keep secrets out of version control.

## 📁 Structure
```
daily_report_name_injector/
├── backend/
│   └── app.py
├── frontend/
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── build/               # prebuilt UI served by Flask
│   └── src/
│       ├── index.css
│       └── App.js
├── Dockerfile
├── docker-compose.yml
└── README.md
```
