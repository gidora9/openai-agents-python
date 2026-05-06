# Deployable Agents Service

This FastAPI wrapper deploys this fork of the OpenAI Agents SDK.
It serves the repository's realtime demo GUI at `/`, a realtime WebSocket at
`/ws/{session_id}`, and API endpoints at `/health` and `/run`.

## Environment

Required:

- `OPENAI_API_KEY`

Optional:

- `SERVICE_API_KEY`: if set, calls to `POST /run` must include `Authorization: Bearer <value>`.
- `OPENAI_AGENT_MODEL`: default model for runs when the request does not provide one.
- `AGENT_INSTRUCTIONS`: default assistant instructions.

## Local Run

```bash
uv run uvicorn deploy.agent_service.app:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Open the realtime GUI:

```bash
open http://localhost:8000
```

Run the agent:

```bash
curl -X POST http://localhost:8000/run \
  -H 'Content-Type: application/json' \
  -d '{"message":"Say hello in one sentence."}'
```

If `SERVICE_API_KEY` is set, add:

```bash
-H 'Authorization: Bearer YOUR_SERVICE_API_KEY'
```

## Deploy

Use the repo root as the deploy root.

### Vercel

This repo includes a root `app.py` entrypoint for Vercel's FastAPI runtime.
Set `OPENAI_API_KEY` in the Vercel project environment before calling `/run`.

### Render or Docker

Build command:

```bash
pip install -r requirements-deploy.txt
```

Start command:

```bash
uvicorn deploy.agent_service.app:app --host 0.0.0.0 --port $PORT
```
