FROM python:3.12-slim
WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=5
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils tesseract-ocr tesseract-ocr-ind && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir --default-timeout=180 --retries 5 -r requirements.txt
COPY . /app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
