FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user; /data holds the SQLite database (mount a volume here).
RUN useradd --create-home --uid 1000 app && mkdir /data && chown app:app /data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .
USER app

ENV PYTHONUNBUFFERED=1 OMNIDOC_DB=/data/omnidoc.db
VOLUME /data
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
