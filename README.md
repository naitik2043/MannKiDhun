# MannKiDhun

**Every feeling has a tune.**

MannKiDhun is a music-discovery web application that pairs optional facial-expression estimates and user-selected vibes with music recommendations. It includes a React frontend, a Flask API, a SQLite catalogue and account store, and a pre-trained Keras model.

> **Important:** An expression estimate is not a measurement of a person's feelings, a diagnosis, or a substitute for their own choice. Camera use is optional; users can select a vibe manually.

## Features

- **Discover (`/app`)** — Choose a vibe manually or explicitly enable the camera for a five-frame expression estimate. Camera access can be disabled at any time.
- **Music assistant (`/assistant`)** — Search the local catalogue in natural language. The assistant can play catalogue tracks through YouTube, save tracks, create playlists, add tracks to playlists, and append tracks to a saved queue.
- **Accounts and profile** — Sign up, sign in, update profile details, and change a password.
- **Preferences and recommendations** — Store language, genre, listening-style, and artist preferences; the recommendation engine can use those preferences and listening activity.
- **Music library APIs** — Manage saved songs, playlists, listening history, and playback-state data.
- **Responsive web experience** — Home page, dashboard, profile settings, FAQs, and light/dark theme.

### Feature boundaries

The vibe-check page currently picks from configured YouTube recommendations; it is not a streaming service. Assistant suggestions come from the local catalogue and can be embedded from YouTube, subject to provider and browser restrictions. The saved queue stores track IDs; it is not a synchronized or cross-device player.

The dashboard's featured playlists, categories, and recent-listening areas are placeholders. Password-reset and verification email delivery are not implemented, so account recovery is unavailable through a normal user flow. See [known limitations](#known-limitations) and the [deployment notes](docs/DEPLOYMENT.md) before hosting the app.

## Technology

- **Frontend:** React 18, Vite, Tailwind CSS, Vitest, and Testing Library
- **Backend:** Flask, SQLite, and Python
- **Expression analysis:** MediaPipe Holistic, OpenCV, and a Keras/TensorFlow model
- **Music playback:** YouTube links and embedded YouTube players

## Requirements

- Python 3.11
- Node.js 20.19+ or 22.12+
- A browser with camera support for expression analysis
- Internet access for YouTube playback; camera access requires HTTPS or `localhost`

## Install

Run these commands from the project root. On Windows, the virtual environment is placed under local application data because TensorFlow's deeply nested package paths may exceed Windows path limits in a long workspace path.

```powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
py -3.11 -m venv $pythonEnv
& "$pythonEnv\Scripts\python.exe" -m pip install -r requirements.txt
npm install
```

The trained model and label files are included in `model\`. The app creates or updates its SQLite database at `instance\moodwave.sqlite3` when the Flask application starts. Back up an existing database before running updated code against it; schema changes are not managed by a versioned migration system.

## Run locally

Start the Flask API in one PowerShell terminal:

```powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" app.py
```

The API listens at <http://127.0.0.1:5001> by default. In a second terminal, start Vite:

```powershell
npm run dev
```

Open the Vite URL shown in the terminal (normally <http://127.0.0.1:5173>). The Vite development server proxies `/api` and `/predict` to Flask. Create an account at `/signup`, then visit `/dashboard`, `/assistant`, or `/app`.

To use a Flask API at a different address, set `MANNKIDHUN_API_URL` before starting Vite. The legacy `MOODWAVE_API_URL` is also supported.

For local development, Flask generates a temporary session-signing key when `MANNKIDHUN_SECRET_KEY` is unset. Sessions will no longer be valid after a server restart. For a stable local session, set a private key in the server terminal before launching Flask:

```powershell
$env:MANNKIDHUN_SECRET_KEY = "<a long random secret>"
```

Set `MANNKIDHUN_COOKIE_SECURE=1` only when serving over HTTPS. The app does not load `.env` files automatically; configure environment variables through your shell or deployment platform.

## Build, test, and evaluate

Build the production frontend:

```powershell
npm run build
```

Run the backend and frontend test suites:

```powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" -m unittest discover -s tests
npm test
```

For local smoke testing, `python app.py` serves the built frontend at <http://127.0.0.1:5001>. This uses Flask's development server and is not a production server.

`model_evaluation.py` calculates metrics for supplied predictions; it does not train the model or generate predictions. Its CSV must contain `subject_id,split,true_label,predicted_label` columns and at least one held-out test row. Include train, validation, and test rows to check subject separation across all splits:

```powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" model_evaluation.py --predictions path\to\subject-separated-predictions.csv
```

The evaluator rejects subjects that appear in more than one split and reports metrics for the held-out test split. Record dataset provenance, licensing, capture conditions, and split methodology before treating results as a model benchmark.

## Optional assistant provider

By default, the assistant uses local rules to extract search intent. To use an OpenAI-compatible intent provider, configure these variables in the Flask server environment:

- `AI_ASSISTANT_API_KEY` — provider key; keep it server-side and out of source control.
- `AI_ASSISTANT_API_URL` — provider endpoint; HTTPS is required except for loopback development endpoints.
- `AI_ASSISTANT_MODEL` — provider model name.

When configured, only the user's current assistant message is sent to the provider for structured intent extraction. Preferences and listening history are not sent. Provider errors fall back to local intent parsing. The provider does not generate song listings or playback links; recommendations are restricted to catalogue entries.

## Expression analysis and privacy

The included model accepts 1,020 landmark values and returns six class scores. Its labels are `happy`, `neutral`, `surprise`, `rock`, `angry`, and `sad` after the API normalizes two legacy label names. MediaPipe Holistic supplies 468 face landmarks and up to 21 landmarks for each hand. The preprocessing is tied to the existing model; changing it or replacing the model requires compatible training and evaluation.

The browser captures five JPEG frames only after the user enables the camera and requests an analysis. It sends those frames to the Flask `/predict` endpoint for backend-side inference. Frames are processed in request memory and are not written to disk by this endpoint. The browser clears its temporary image data when the request completes and stops the camera when it is disabled or the analysis page is left. The optional assistant provider receives text only, not camera frames, account credentials, or listening history.

The backend rejects frames that fail face-detection or basic image-quality checks, and requires at least three usable frames for a multi-frame request. It averages the valid frame scores and asks the user to retry when frame predictions are too inconsistent. These quality checks are heuristics, and scores are not calibrated probabilities of a person's emotional state.

## Known limitations

- No labeled, subject-separated evaluation dataset is included. Accuracy, precision, recall, F1, demographic performance, hand-feature impact, and end-to-end performance have not been established.
- Confidence scores are not calibrated. Face quality checks do not reliably detect occlusion or extreme pose.
- Inference runs on the Flask backend, not in the browser. The legacy MediaPipe Holistic API is used.
- Password reset and email verification delivery are not configured.
- The database is local SQLite; there is no versioned migration framework, automated backup, or restore service.
- A production WSGI server, distributed rate limiting, and production monitoring are not included. GitHub Actions runs the test suites and frontend build, but does not deploy the app.

Do not use expression estimates for medical, diagnostic, employment, or other consequential decisions. See [Security and privacy](docs/SECURITY.md) for additional deployment gaps.

## Project layout

```text
app.py                    Flask application and API routes
recommendation_engine.py  Catalogue, recommendation, and library operations
music_assistant.py        Rule-based and optional provider intent parsing
model_loader.py           Model and metadata validation
prediction_aggregation.py Multi-frame prediction aggregation
frame_validation.py       Camera-frame quality checks
model_evaluation.py       Metrics for supplied held-out predictions
frontend/src/             React pages, components, hooks, and styles
tests/                    Python and frontend tests
docs/                     API, architecture, database, deployment, and security notes
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API_DOCUMENTATION.md)
- [Database notes](docs/DATABASE.md)
- [Deployment and operations](docs/DEPLOYMENT.md)
- [Security and privacy](docs/SECURITY.md)

For public deployment, review [Deployment and operations](docs/DEPLOYMENT.md) first. The current configuration is intended for local development and is not production-ready.

To create a Render demo, use the Blueprint in `render.yaml` and connect the `main` branch. It builds and serves both the frontend and API. This free demo uses temporary local storage, so account and library data may be lost when Render restarts or redeploys the service; review the [Render deployment notes](docs/DEPLOYMENT.md#render-free-demo-deployment) before sharing it with users.
