# Dockerfile
FROM python:3.12-slim

# System deps (psycopg2, etc.)
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Faster rebuilds: only copy requirements first if you have them
# If you use requirements.txt:
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# If you use pyproject.toml, replace above with:
# COPY pyproject.toml poetry.lock* ./
# RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false && poetry install --no-dev --no-interaction

# Now copy the rest
COPY . .

# Expose uvicorn port
EXPOSE 8000

# Env file is mounted by compose
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
