# Mind Palace Builder

A guided web app for building a "method of loci" memory palace: a five-lesson
interactive curriculum with hands-on practice, plus a real palace-building
tool with a spaced-repetition quiz.

## What it does

- **Learning path** (`/learn`): five sequential lessons -- why spatial memory
  works, choosing/sizing a route, building vivid associations, encoding
  numbers and abstract concepts, and avoiding common mistakes. Each lesson
  (after the first) requires a practice exercise before the next unlocks.
- **Palace builder** (`/palace/add`, `/palace/walk`): name a real route and
  place items with vivid associations at each stop.
- **Spaced review** (`/quiz/start`): quiz yourself on your palace; each
  location moves through Leitner-style review boxes (1, 2, 4, 7, 14, 30 days)
  based on whether you recalled it correctly.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000.

## Run with Docker

```bash
docker compose up --build
```

Data persists to `./data/mind_palace.json` on the host via a volume mount.

## Configuration

| Env var      | Default                        | Purpose                          |
|--------------|---------------------------------|-----------------------------------|
| `SECRET_KEY` | `dev-secret-change-me`          | Flask session signing key -- set a real value in production. |
| `DATA_FILE`  | `./data/mind_palace.json`       | Where palace data is stored.      |
| `PORT`       | `5000`                          | Port the app listens on.          |
