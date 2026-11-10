FROM node:20-alpine AS frontend-build

WORKDIR /frontend

COPY CourseRecomV2/frontend/package*.json ./
RUN npm ci

COPY CourseRecomV2/frontend/ ./
ENV VITE_API_BASE_URL=/api \
    VITE_ENVIRONMENT=production
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=5

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils tesseract-ocr tesseract-ocr-ind && \
    rm -rf /var/lib/apt/lists/*

COPY CourseRecomV2/backend/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir --default-timeout=180 --retries 5 -r requirements.txt

COPY CourseRecomV2/backend /app
COPY --from=frontend-build /frontend/dist /app/app/static

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
