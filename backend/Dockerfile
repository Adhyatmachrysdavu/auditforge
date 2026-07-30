FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependensi sistem untuk WeasyPrint (render PDF: Pango/Cairo/GDK-Pixbuf) + font.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        libffi-dev \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (better layer caching)
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install -e .

# Copy the rest (scripts, etc.)
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
