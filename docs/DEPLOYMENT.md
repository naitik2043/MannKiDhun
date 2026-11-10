# Deployment and operations

## Render (free, demo deployment)

This repository includes a Render Blueprint in `render.yaml`. In the Render dashboard, create a new Blueprint instance for `naitik2043/MannKiDhun` and select the `main` branch. The Blueprint builds the React frontend, installs the Python dependencies, starts Flask with Gunicorn, generates a stable session secret, enables secure cookies, and checks `/healthz`.

The Blueprint uses Render's free web-service plan so it does not create a paid resource. Free services can sleep while idle and their local filesystem is ephemeral. This app stores accounts, playlists, and profile uploads on that filesystem in SQLite and `instance/profile_uploads`; those records and files can be lost on restart or deploy. Use this deployment for a public demo only. For durable user data, move persistence to a managed database and object storage, or use a paid service with a persistent disk after choosing an appropriate plan. Do not collect important account data on the free deployment.

The bundled model is loaded during startup and requires substantial memory. If Render terminates the service during startup or health checks, inspect the service logs and move to a larger instance before using it.

## Current status

The repository includes a GitHub Actions workflow that runs the backend and frontend tests and builds the frontend on pushes and pull requests. The Render Blueprint uses Gunicorn for the demo deployment. PostgreSQL support, email delivery, and automated backup are not included. `python app.py` starts Flask's development server and is for local development/smoke testing only. The app is not configured for durable production user data.

## Local build and run

Install the requirements in [README.md](../README.md), then:

```powershell
npm run build
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" app.py
```

The app serves the built frontend at port 5001 by default. For frontend development, run `npm run dev` in another terminal. Do not run Vite's preview server as a production frontend server.

## Environment configuration

Use `.env.example` as a reference and inject secrets through the deployment platform; the app does not load `.env` automatically. Set a strong stable `MANNKIDHUN_SECRET_KEY`, `MANNKIDHUN_COOKIE_SECURE=1` behind HTTPS, and `AI_ASSISTANT_API_KEY` only when enabling the optional provider. The assistant provider base URL and model are configurable with `AI_ASSISTANT_API_URL` and `AI_ASSISTANT_MODEL`.

The Flask process currently binds to loopback by default. Deployment behind a reverse proxy, forwarded-header trust, HTTPS termination, origin policy, static asset serving, and process supervision must be configured and reviewed before exposure.

## Health and data

`GET /healthz` checks that the configured SQLite database responds without revealing database details. It is not a full model/provider readiness check. Backups and restores are manual; see [DATABASE.md](./DATABASE.md). There is no migration rollback command: preserve a database backup before schema changes and test changes against a copy first.

The Render Blueprint deploys automatically from `main` for the free demo. Before using this for durable production accounts, establish a persistent database and file store, backups and restore checks, monitoring, and the other operational controls described above.
