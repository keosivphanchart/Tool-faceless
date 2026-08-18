FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir ".[all]"

EXPOSE 8000
CMD ["uvicorn", "faceless_pipeline.main:app", "--host", "0.0.0.0", "--port", "8000"]
