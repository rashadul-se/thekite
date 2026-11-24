# Elder Care Centre (1000 residents)

Layers: `domain` (data) -> `infrastructure` (Postgres, Redis, SQLite outbox) -> `services` (CareService facade, InsightEngine) -> `ui` (Streamlit). Wiring in `app/container.py`.

## Run locally
    docker compose up --build        # http://localhost:8501 (auto-seeds 1000 residents)

## Deploy on Render
1. Push to GitHub. 2. Render > New > Blueprint > select repo (uses `render.yaml`).
Render runs the Docker image natively; `k8s/` is for your own cluster (EKS/GKE/AKS).

## Offline
Toggle "Work offline": events save to the local SQLite outbox, then "Sync now" pushes them to Postgres in batches (idempotent via event_id).
