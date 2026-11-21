# Deployment and operations

## Render demo deployment

This repository includes a Render Blueprint in \`render.yaml\`. In the Render dashboard, create a Blueprint instance for \`naitik2043/MannKiDhun\` and select the \`main\` branch. The Blueprint installs Python dependencies, builds the React frontend, runs Flask with Gunicorn, generates a stable session secret, enables secure cookies, and checks \`/healthz\`.

The Blueprint intentionally uses Render's Free web-service plan. Free services can spin down while idle and their local filesystem is ephemeral. MannKiDhun stores accounts, playlists, listening history, preferences, journal entries, SQLite data, and profile photos on that filesystem. These records and files can be lost after restart, spin-down, or deployment. Treat this configuration as a demo only; do not collect important user data on it.

## Persistent SQLite storage on Render

The application supports a configurable data directory through \`MANNKIDHUN_DATA_DIR\`. It controls the location of both \`moodwave.sqlite3\` and \`profile_uploads/\`.

For a persistent single-instance SQLite deployment:

1. Use a paid Render web service that supports a persistent disk.
2. Attach a disk to the service and set its mount path to \`/var/data\`.
3. Add the environment variable \`MANNKIDHUN_DATA_DIR=/var/data\`.
4. Keep \`MANNKIDHUN_COOKIE_SECURE=1\` and a stable \`MANNKIDHUN_SECRET_KEY\`.
5. Deploy, verify \`/healthz\`, create a test account, and confirm that its profile photo and data remain after a controlled restart.
6. Back up the database and rehearse restoring it before treating the instance as production data storage.

The Free Blueprint does not attach a persistent disk. Setting the data-directory variable on a Free service does **not** make its filesystem durable. The application still uses SQLite, so this setup is for one application instance, not horizontally scaled multi-worker production.

For a larger deployment, migrate the SQLite-oriented persistence layer to a managed database and object storage, introduce versioned migrations, and perform load, backup, and restore testing.

## Current deployment status and limitations

GitHub Actions builds the frontend and runs both backend and frontend test suites for pushes and pull requests. The Render Blueprint is configured for automatic deploys from \`main\`. A successful GitHub workflow verifies the repository build and tests; it does not by itself prove that Render's deployment or the external site is healthy.

The bundled expression model is loaded during inference and requires substantial memory. If Render terminates the service during startup or health checks, inspect service logs and consider a larger instance.

PostgreSQL support, email delivery, automated backups, and a versioned migration framework are not included. \`python app.py\` starts Flask's development server and is for local development / smoke testing only.

## Local build and run

Install the requirements in [README.md](../README.md), then:

\`\`\`powershell
npm ci
npm run build
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" app.py
\`\`\`

The app serves the built frontend on port 5001 by default. For frontend development, run \`npm run dev\` in another terminal.

## Environment configuration

Use [.env.example](../.env.example) as a reference. The app does not automatically read \`.env\`; inject values through the shell or deployment platform.

- \`MANNKIDHUN_SECRET_KEY\`: stable session-signing secret.
- \`MANNKIDHUN_COOKIE_SECURE=1\`: enable secure session cookies behind HTTPS and emit HSTS.
- \`MANNKIDHUN_DATA_DIR\`: optional persistent data path; defaults to the repository's \`instance/\` directory.
- \`AI_ASSISTANT_API_KEY\`, \`AI_ASSISTANT_API_URL\`, and \`AI_ASSISTANT_MODEL\`: optional structured-intent provider configuration.

## Health, backups, and operational readiness

\`GET /healthz\` checks that the configured SQLite database responds without revealing database details. It is not a full model or provider readiness check.

Backups and restores are manual; see [DATABASE.md](./DATABASE.md). There is no migration rollback command: preserve a database backup before schema changes and test changes against a copy first.

Before collecting durable user data, establish persistent storage, tested backups / restore, monitoring, login throttling, distributed rate limiting, a production origin policy, email recovery, dependency scanning, and a security review.
