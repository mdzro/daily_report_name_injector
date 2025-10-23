
FROM python:3.11-slim

WORKDIR /app
COPY backend ./backend
COPY frontend/build ./frontend/build

RUN pip install --no-cache-dir flask pandas openpyxl beautifulsoup4 python-dotenv

EXPOSE 5000
CMD ["python", "backend/app.py"]
