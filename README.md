# MannKiDhun

**Music discovery for the mood, moment, and languages that make a song feel personal.**

[![CI](https://github.com/naitik2043/MannKiDhun/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/naitik2043/MannKiDhun/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/naitik2043/MannKiDhun)](LICENSE)
![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react)

[Demo](https://mannkidhun.onrender.com) · [Community playlists](https://mannkidhun.onrender.com/community) · [Catalogue sources](docs/CATALOGUE_SOURCES.md) · [Competitive analysis](docs/COMPETITIVE_ANALYSIS.md) · [17-upgrade status](docs/UPGRADE_STATUS.md) · [Product roadmap](docs/PRODUCT_ROADMAP.md)

MannKiDhun is an open-source music discovery application built with **React, Vite, Flask, and SQLite**. Listeners can choose a mood, describe a moment in natural language, optionally request an expression-based suggestion, and discover tracks from a curated catalogue. Recommendations can use declared music preferences, explicit feedback, and an optional listening context.

> **The listener stays in control.** Camera analysis is off by default. A facial-expression estimate is not a reliable measure of someone's inner emotional state, and it never overrides a manually selected mood.

## Product experience

| Capability | What it does |
| --- | --- |
| Mood check-in | Choose a vibe manually or opt into a five-frame facial-expression estimate. Camera estimates require explicit confirmation before a recommendation is shown; manual selection can correct the suggestion. |
| Match / Change / Explore | Match a current mood, move through a three-stage Change journey (starting mood → heuristic bridge → target), or Explore beyond mood filters. |
| Context-aware discovery | Select studying, travelling, evening, workout, or sleep. A transparent tag-affinity heuristic adjusts catalogue ranking. |
| Explainable recommendations | See catalogue-backed reasons and respond with Like or Not for me feedback. |
| Music Assistant | Search the local catalogue with text or browser speech dictation in Hindi / English (India). A confirmed check-in can prefill Match mode; local rules recognize common Roman Hinglish and selected native-script phrases. |
| Adaptive sessions | Build Match, Change, or Explore queues. Like / Not for me feedback can refresh the remaining session when you opt into history-based personalization. |
| Global player | One app-level YouTube player follows internal navigation, persists its queue locally, supports seek / previous / next / repeat, and advances automatically when an embedded track ends. |
| Group listening | Playlist owners can start six-hour invite-only rooms. Signed-in guests join with a bearer link; playlist playback state and recent participant presence sync through versioned polling. |
| Personal Music DNA | Opt in to a private summary of recurring languages, genres, artists, listening styles, and vibes. Export or reset the profile. |
| Mood & Music Journal | Write private mood notes and review recent patterns. Entries are manually created, never inferred from camera frames. |
| Playlists & community | Create playlists, publish them optionally, discover public playlists, invite viewers or editors, and start group listening rooms. |
| Personal library | Save tracks, review listening history, and manage music preferences. |
| Regional discovery | Starter catalogue includes Hindi, English, Punjabi, Bengali, Gujarati, Telugu, Tamil, Malayalam, and Marathi tracks. |

### How context-aware ranking works

A listener can optionally select a context in the Music Assistant. MannKiDhun compares that selection with existing catalogue tags such as \`calm\`, \`acoustic\`, \`driving\`, \`dance\`, and \`powerful\`, then blends the resulting affinity into the existing preference, vibe, artist, and feedback score. The recommendation response includes the selected context, match score, and matching tags so the influence is inspectable.

This is a **curated metadata heuristic**, not an audio-understanding model. It does not read location, calendar, activity sensors, heart rate, or wearable data. Its quality depends on the coverage and accuracy of the catalogue tags; richer, verified audio features are a roadmap item.

## Screens and routes

| Route | Purpose |
| --- | --- |
| \`/\` | Product landing page |
| \`/signup\`, \`/signin\` | Account creation and sign-in |
| \`/app\`, \`/mood-check\` | Mood check-in experience |
| \`/assistant\` | Music Assistant, discovery controls, adaptive queues, and playlist tools |
| \`/dashboard\` | Music preferences, listening history, Music DNA, journal, and personal music data |
| \`/profile\` | Account and profile settings |
| \`/community\` | Public playlist directory |
| \`/playlists/<id>\` | Read-only public playlist page |

## Technology

| Layer | Technologies |
| --- | --- |
| Frontend | React 18, Vite, Tailwind CSS, JavaScript |
| Backend | Python 3.11, Flask, Gunicorn |
| Persistence | SQLite, with a configurable data directory |
| Expression pipeline | MediaPipe Holistic, OpenCV, Keras / TensorFlow |
| Testing | Python \`unittest\`, Vitest, Testing Library |
| Player | YouTube IFrame Player API, browser Media Session API where supported |
| Deployment | Render Blueprint, GitHub Actions, CodeQL |

## Run locally

### Requirements

- Python 3.11
- Node.js 20.19+ or 22.12+
- A modern browser
- HTTPS or localhost for camera access

### Install

From the repository root:

\`\`\`powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
py -3.11 -m venv $pythonEnv
& "$pythonEnv\Scripts\python.exe" -m pip install --upgrade pip
& "$pythonEnv\Scripts\python.exe" -m pip install -r requirements.txt
npm ci
\`\`\`

### Start the backend

\`\`\`powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" app.py
\`\`\`

### Start the frontend

In a second terminal:

\`\`\`sh
npm run dev
\`\`\`

Open the Vite URL printed in the terminal (normally \`http://127.0.0.1:5173\`). The Vite development server proxies \`/api\` and \`/predict\` to Flask at \`http://127.0.0.1:5001\`. When the frontend Origin differs from the Flask host, set \`MANNKIDHUN_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\` in the Flask process before starting it. Create an account at \`/signup\`, then open the Assistant or mood check-in.

### Environment configuration

See [.env.example](.env.example) for the supported settings. The Flask application does **not** load \`.env\` automatically; configure variables in your shell or deployment platform.

| Variable | Purpose |
| --- | --- |
| \`MANNKIDHUN_SECRET_KEY\` | Stable Flask session-signing secret. Set this in every deployed environment. |
| \`MANNKIDHUN_COOKIE_SECURE\` | Set to \`1\` when the public site is served over HTTPS. |
| \`MANNKIDHUN_ALLOWED_ORIGINS\` | Comma-separated additional browser origins. Set your Vite development origin (normally localhost:5173 or 127.0.0.1:5173) when it differs from Flask's host. |
| \`MANNKIDHUN_DATA_DIR\` | Optional directory for the SQLite database and profile uploads. Defaults to \`./instance\`. |
| \`AI_ASSISTANT_API_KEY\` | Optional key for an OpenAI-compatible intent provider. Leave unset to use local rule-based intent parsing. |
| \`AI_ASSISTANT_API_URL\` | Optional HTTPS endpoint for the intent provider. |
| \`AI_ASSISTANT_MODEL\` | Model name sent to the configured intent provider. |

The optional assistant provider receives the current text request to extract structured search intent. It does not receive camera frames, session credentials, or listening history.

## Quality checks

Build the frontend:

\`\`\`sh
npm run build
\`\`\`

Run frontend tests:

\`\`\`sh
npm test
\`\`\`

Run backend tests (PowerShell):

\`\`\`powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" -m unittest discover -s tests
\`\`\`

GitHub Actions runs the production frontend build and both test suites on pushes and pull requests.

## Architecture

\`\`\`text
frontend/src/
  React pages, components, hooks, and styles
        |
        | same-origin JSON + session cookie
        v
app.py
  Flask routes, account/session handling, API validation
        |
        +--> recommendation_engine.py
        |      catalogue, preferences, feedback, context affinity
        |
        +--> music_assistant.py
        |      local intent parsing + optional structured provider
        |
        +--> model_loader.py / frame_validation.py
               optional expression estimate
        |
        v
SQLite database + profile uploads
\`\`\`

Key implementation files:

- \`app.py\`: Flask application, authentication, account APIs, assistant endpoints, playlist routes, and health check.
- \`database_migrations.py\`, \`database_ops.py\`: ordered SQLite schema migrations and integrity-checked online backup / restore utilities.
- \`frontend/src/context/PlayerContext.jsx\`: app-level YouTube player, persistent local queue, playback controls, and Media Session integration.
- \`recommendation_engine.py\`: catalogue setup, hybrid ranking, feedback scoring, saved songs, and playlist persistence.
- \`music_assistant.py\`: rule-based intent parsing with an optional structured-intent provider.
- \`model_loader.py\`, \`frame_validation.py\`, \`prediction_aggregation.py\`: model artifact checks, image-quality validation, and multi-frame estimate aggregation.
- \`frontend/src/\`: React application and browser-side camera / voice interactions.
- \`tests/\`: backend unit and API tests plus frontend component tests.
- \`docs/\`: architecture, API, database, deployment, security, catalogue sources, and market analysis.

## Privacy and responsible use

- Camera access requires a separate user action. Five temporary frames are sent for the expression check and are processed in memory; the expression endpoint does not save the frames to disk.
- The model's class scores are **not calibrated probabilities**. Frame consistency is not model accuracy. The model has not been established as reliable on a labeled, subject-separated evaluation dataset.
- An expression estimate must be explicitly confirmed before it can select the mood-based music suggestion; a manual choice always overrides it.
- Manual mood selection remains available without camera access. Facial expressions should not be used to infer a person's actual feelings or for health, employment, educational, or other consequential decisions.
- Music DNA is disabled until the listener opts in. Mood journal entries are manually written and private to the account.
- Listening-history personalisation is used only when the listener enables it for a request.
- Public playlist sharing is opt-in. A public playlist is read-only to visitors; private collaboration requires a time-limited viewer or editor invitation.

See [Security and privacy](docs/SECURITY.md) for safeguards and remaining hardening work.

## Deployment

The repository includes a Render Blueprint in [render.yaml](render.yaml). It builds the React app and runs Flask through Gunicorn. The included configuration uses Render's **Free** web-service plan and is intended for a demo.

**Important: the Free service has an ephemeral filesystem.** SQLite accounts, playlists, preferences, journal entries, and uploaded profile photos may be lost after a restart or redeploy. Do not treat the free demo as durable user storage.

For a persistent single-instance SQLite deployment on Render:

1. Use a paid Render web-service plan that supports a persistent disk.
2. Attach a persistent disk mounted at \`/var/data\`.
3. Set \`MANNKIDHUN_DATA_DIR=/var/data\` in the service environment.
4. Deploy and verify \`/healthz\`, then make and test a database backup.

The configurable data directory stores both \`moodwave.sqlite3\` and \`profile_uploads/\`. The app now applies versioned SQLite migrations at startup and includes integrity-checked manual backup / restore commands in [Database](docs/DATABASE.md). This is a deployment option, not an automatic upgrade of the Free Blueprint. For multi-instance or larger-scale production use, move to a managed database and object storage, schedule encrypted off-site backups, and rehearse restore procedures before onboarding real users.

See [Deployment and operations](docs/DEPLOYMENT.md) and [Database](docs/DATABASE.md).

## Known limitations

- The catalogue is a curated starter dataset, not a full music-licensing or streaming catalogue. Playback uses third-party embeds / links; MannKiDhun does not host or sublicense recordings.
- Context matching currently uses manually curated tags. There is no validated audio-feature model for tempo, energy, valence, or era.
- The global player uses the YouTube IFrame API; availability, autoplay, and track embedding depend on provider and browser restrictions. Its queue survives internal route navigation and reloads, but continuous playback cannot survive a full browser refresh or external navigation.
- Group listening rooms sync playlist playback state and recent presence through polling with optimistic version checks. They are not WebSocket-based and cannot guarantee sample-accurate audio synchronization.
- Voice features depend on the browser's speech APIs and may not be available in every browser.
- Kannada, Urdu, Sanskrit, and other regional-language catalogue coverage needs verified additions; language recognition in the assistant does not mean that tracks are already available.
- Password-reset and verification email delivery are not configured.
- Browser API mutations use a synchronizer-token CSRF cookie/header plus the configured origin allowlist. Requests omitting both Origin and Referer remain permitted for trusted non-browser / legacy compatibility.
- Login and assistant rate limits are process-local, not distributed.
- SQLite migrations and manual backup / restore tooling are included, but scheduled off-site backups and restore drills are not. Login and assistant limits remain process-local, and the Free Render filesystem is ephemeral; this is not a durable multi-worker production setup.

## Product and market research

See [the 17-upgrade implementation audit](docs/UPGRADE_STATUS.md) for an item-by-item status, evidence, and remaining scope.

See [Competitive analysis and differentiation](docs/COMPETITIVE_ANALYSIS.md) for a sourced review of adjacent products, an evidence-based positioning, and prioritized opportunities. The [Product roadmap](docs/PRODUCT_ROADMAP.md) distinguishes shipped capabilities from remaining work.

## License

Distributed under the [MIT License](LICENSE).
