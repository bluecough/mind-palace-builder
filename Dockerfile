FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data is written here; mount a volume to persist it across container restarts.
RUN mkdir -p /app/data
ENV DATA_FILE=/app/data/mind_palace.json
ENV SECRET_KEY=change-me-in-production
ENV PORT=5000

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
