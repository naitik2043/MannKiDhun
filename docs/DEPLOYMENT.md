# Deployment and operations

## Current status

The repository includes a GitHub Actions workflow that runs the backend and frontend tests and builds the frontend on pushes and pull requests. It does not include a production WSGI server, container definition, PostgreSQL configuration, email delivery, or automated backup job. `python app.py` starts Flask's development server and is for local development/smoke testing only. The project is not production-ready as currently configured.

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

Never deploy automatically based on this repository's current configuration. Establish a production WSGI server, durable database/volume, secret provisioning, HTTPS, logs/monitoring, and backup/restore procedure first.
