# MannKiDhun

**A more personal way to find music for the moment.**

[Open the live demo](https://mannkidhun.onrender.com) · [Community playlists](https://mannkidhun.onrender.com/community) · [Regional catalogue sources](docs/CATALOGUE_SOURCES.md) · [Architecture](docs/ARCHITECTURE.md) · [API reference](docs/API_DOCUMENTATION.md) · [Deployment guide](docs/DEPLOYMENT.md) · [Security and privacy](docs/SECURITY.md) · [Product roadmap](docs/PRODUCT_ROADMAP.md)

MannKiDhun is an open-source music discovery app with a **JavaScript/React frontend** and a **Python/Flask backend**. Choose a vibe yourself or optionally request an expression-based starting suggestion, then explore music that fits the moment.

> Camera use is off by default. An expression estimate is only a suggestion—not a measurement, diagnosis, or substitute for a person’s own choice.

## What you can do

- Choose a mood manually or request an optional, five-frame expression check-in. Camera estimates remain suggestions that you can ignore.
- Discover tracks with the catalogue-grounded music assistant, including a rules-based fallback when the optional AI intent provider is unavailable.
- See why a track was recommended, then use **Like** or **Not for me** to provide feedback that influences future history-aware ranking.
- Play catalogue tracks through YouTube embeds or provider links; assistant playback activity is recorded in your listening history.
- Save tracks, create playlists, and manage your preferences for language, genre, listening style, and artists.
- Choose **Match**, **Change**, or **Explore** discovery modes, then build an adaptive listening queue using your selected preferences and (only when you opt in) listening activity.
- Refine a playlist with natural-language requests such as “add peaceful music”, “more Hindi songs”, or “more variety”. Refinement adds matching catalogue tracks; it does not silently remove existing songs.
- Enable **Personal Music DNA** to see private summaries of your favourite languages, genres, and artists from saved preferences and account activity. This is opt-in and can be disabled.
- Keep a private, manually written **Mood & Music Journal**. Journal entries are separate from camera inference and do not contain camera frames.
- Use browser-supported voice input in English (India) or Hindi to dictate a text request.
- Share a playlist publicly and browse the community directory. You can also invite editors or viewers with expiring links, change collaborator roles, and revoke access. Editors can add/remove/reorder tracks; visitors to public links remain read-only.
- Refine playlists with natural-language commands to add tracks, remove a named/last track, or move a track to the beginning/end.
- Build an adaptive queue and use Start, Previous, and Next controls. Queue progress is saved to your account; the current YouTube embed is not a full automatic streaming player.
- Dictate requests in English (India) or Hindi using browser speech recognition, and use Read aloud for spoken assistant responses where the browser supports speech synthesis.
- Explore Indian-language intent filters including Hindi, Punjabi, Tamil, Telugu, Bengali, Marathi, Gujarati, Malayalam, Kannada, Urdu, and Sanskrit. The starter catalogue includes verified Punjabi, Bengali, Gujarati, and Telugu additions; other languages require more verified track entries.
- Use the dashboard to review recent listening activity, saved playlists, Music DNA, and journal entries.
- Use the responsive interface on desktop or mobile, with light and dark themes.

**Feature boundaries:** MannKiDhun is a music discovery app, not a licensed streaming service; playback is provided through YouTube embeds and external provider links. The saved queue stores track IDs and is not a synchronized, cross-session player. Adaptive sessions save a queue snapshot; they do not run a continuous player or reorder a playing queue in real time. Natural-language playlist editing adds, removes, or reorders catalogue tracks based on explicit commands. Collaborative editors can make changes through authenticated endpoints; public visitors remain read-only. Invitation links are bearer links that expire after seven days and can be revoked. Voice input and spoken responses depend on browser speech APIs. Language recognition is broader than the seeded catalogue, so some languages may still return few or no matches. Password-reset and verification email delivery are not configured. The current free Render deployment uses ephemeral local storage, so account and library data can be lost when the service restarts or redeploys.

## Technology

| Area | Technologies |
| --- | --- |
| Languages | Python, JavaScript/JSX, HTML, CSS |
| Frontend | React 18, Vite, Tailwind CSS |
| Backend | Flask, Gunicorn |
| Data | SQLite |
| Expression check-in | MediaPipe Holistic, OpenCV, Keras/TensorFlow |
| Quality | unittest, Vitest, Testing Library |

## Requirements

- Python 3.11
- Node.js 20.19+ or 22.12+
- A modern browser; camera features require HTTPS or localhost
- Internet access for YouTube playback

## Run locally

Install the backend dependencies and frontend packages from the repository root. On Windows, a short virtual-environment path avoids TensorFlow’s long package paths:

```powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
py -3.11 -m venv $pythonEnv
& "$pythonEnv\Scripts\python.exe" -m pip install -r requirements.txt
npm ci
```

Start Flask in one terminal:

```powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" app.py
```

Start the frontend in another terminal:

```sh
npm run dev
```

Open the Vite address printed in the terminal (normally <http://127.0.0.1:5173>). The development server proxies `/api` and `/predict` to Flask at <http://127.0.0.1:5001>. Create an account at `/signup`, then explore `/app`, `/assistant`, or `/dashboard`.

For a stable local session key, set `MANNKIDHUN_SECRET_KEY` in the Flask terminal before starting the server. For HTTPS deployments, set `MANNKIDHUN_COOKIE_SECURE=1`. Keep secrets out of source control; configure them through the deployment platform.

## Build and test

Build the production frontend:

```sh
npm run build
```

Run both test suites:

```powershell
$pythonEnv = Join-Path $env:LOCALAPPDATA "mannkidhun-venv"
& "$pythonEnv\Scripts\python.exe" -m unittest discover -s tests
npm test
```

The Flask development server is for local use only. Production deployments should use the WSGI command and platform configuration in `render.yaml`.

## Architecture

- `app.py` serves the built frontend and provides the Flask API, including authenticated preferences, listening history, mood journal, Music DNA, playlist refinement, adaptive sessions, and public playlist read endpoints.
- `frontend/src/` contains the React application.
- `recommendation_engine.py` manages the catalogue, recommendations, playlists, and listening data.
- `music_assistant.py` parses search intent locally; an optional provider can be configured.
- `model_loader.py`, `frame_validation.py`, and `prediction_aggregation.py` handle model validation and expression-analysis requests.
- `docs/` contains architecture, API, database, deployment, and security documentation.

## Privacy and responsible use

The browser requests camera access only after the user enables the camera and asks for an expression check. It sends five frames to the backend for inference; this endpoint processes them in memory and does not save them to disk. The optional text-intent provider receives only the current assistant message—not camera frames, credentials, or listening history.

The model’s scores are not calibrated probabilities, and its performance has not been established on a labeled, subject-separated evaluation dataset. Do not use its output for medical, diagnostic, employment, or other consequential decisions. See [Security and privacy](docs/SECURITY.md) for deployment considerations.

## Deploy on Render

The repository includes a Render Blueprint. Connect the `main` branch and deploy `render.yaml); the Blueprint builds the frontend and starts Flask with Gunicorn. See the [deployment and operations guide](docs/DEPLOYMENT.md) before sharing the demo.

The current Free service is suitable for a demo: its local SQLite database and profile files are temporary and may be lost when the service restarts or redeploys. Free instances also spin down when idle. Use durable storage and an appropriate plan before relying on user data.

## License

Distributed under the [MIT License](LICENSE).
