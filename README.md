# 🎵 MannKiDhun

<p align="center">
  <strong>Every Feeling Has a Tune.</strong><br/>
  Discover music for your mood, moment, and musical taste.
</p>

<p align="center">
  <a href="https://mannkidhun.onrender.com/"><img src="https://img.shields.io/badge/Live%20Demo-Visit%20MannKiDhun-111827?style=for-the-badge&logo=render" alt="Live demo"/></a>
  <a href="https://github.com/naitik2043/MannKiDhun"><img src="https://img.shields.io/badge/GitHub-Source%20Code-181717?style=for-the-badge&logo=github" alt="Source code"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/actions/workflow/status/naitik2043/MannKiDhun/ci.yml?branch=main&label=CI&logo=githubactions" alt="CI status"/>
  <img src="https://img.shields.io/github/license/naitik2043/MannKiDhun?label=License" alt="MIT License"/>
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=20232A" alt="React 18"/>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/Flask-Backend-000000?logo=flask" alt="Flask"/>
</p>

**MannKiDhun** is an open-source, mood-aware music discovery application built with **React, Vite, Flask, and SQLite**. It helps listeners explore music using manual mood selection, natural-language requests, personal preferences, and optional camera-based expression suggestions.

The listener remains in control: camera access is off by default, expression suggestions are optional, and a manual mood choice can always be made instead.

> **Model transparency:** Expression scores are experimental, uncalibrated model outputs—not validated measurements of a person's emotions. Model performance has not yet been established on a labeled, subject-separated evaluation dataset. Music playback uses YouTube embeds and links rather than a native streaming service.

---

## ✨ Features

| Feature | Description |
| --- | --- |
| **Mood-based discovery** | Choose a mood manually and discover catalogue tracks that fit your selected vibe. |
| **Optional expression check-in** | Request an expression-based suggestion from a five-frame camera check-in. |
| **Privacy-conscious camera flow** | Camera access is disabled by default and starts only after an explicit user action. |
| **Match, Change & Explore** | Find music for the current vibe, move toward a target mood, or explore outside mood filters. |
| **Context-aware recommendations** | Optionally select studying, travelling, evening, workout, or sleep. Curated catalogue tags influence ranking. |
| **Explainable recommendations** | View catalogue-backed reasons and provide feedback such as Like or Not for me. |
| **Natural-language Music Assistant** | Search the catalogue using text; browser speech dictation is available where supported. |
| **Adaptive listening sessions** | Build recommendation queues and refresh upcoming tracks using feedback. |
| **Global music player** | Control a shared app-level YouTube player with queue, seek, previous, next, repeat, and Media Session support where available. |
| **Playlists & collaboration** | Create playlists, invite viewers or editors, publish playlists optionally, and discover public playlists. |
| **Group listening rooms** | Share playlist-scoped playback state with signed-in participants through versioned polling. |
| **Personal Music DNA** | Opt in to a private summary of recurring languages, genres, artists, listening styles, and vibes. |
| **Mood & Music Journal** | Create private, manually written mood notes and review recent patterns. |
| **Personal music library** | Save songs, review listening history, and manage music preferences. |
| **Responsive experience** | Use the application on different screen sizes with light and dark themes. |

## 🧰 Tech Stack

| Layer | Technologies |
| --- | --- |
| Frontend | React 18, Vite, Tailwind CSS, JavaScript |
| Backend | Python 3.11, Flask, Gunicorn |
| Database | SQLite, versioned schema migrations |
| Machine learning & computer vision | MediaPipe Holistic, OpenCV, TensorFlow, Keras |
| Testing | Python `unittest`, Vitest, React Testing Library |
| Music playback | YouTube IFrame Player API, browser Media Session API |
| CI & security analysis | GitHub Actions, CodeQL |
| Deployment | Render |

## 🖼️ Application Preview

<!-- Add current, real application screenshots here. Suggested sections: Landing page, Mood Check-in, Music Assistant, Dashboard, and Playlists. -->

## 🚀 Getting Started

### Prerequisites

- Python **3.11**
- Node.js **20.19+** or **22.12+**
- npm
- A modern browser
- HTTPS or localhost for camera access

### 1. Clone the repository

```bash
git clone https://github.com/naitik2043/MannKiDhun.git
cd MannKiDhun
```

### 2. Set up the Python environment

**Windows PowerShell:**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
npm ci
```

### 4. Configure environment variables

Review [`.env.example`](.env.example). The Flask application does **not** automatically load a `.env` file, so configure variables in your shell or deployment dashboard.

| Variable | Purpose |
| --- | --- |
| `MANNKIDHUN_SECRET_KEY` | Stable Flask session-signing secret. Set a strong secret in deployed environments. |
| `MANNKIDHUN_COOKIE_SECURE` | Set to `1` when the public application is served over HTTPS. |
| `MANNKIDHUN_ALLOWED_ORIGINS` | Comma-separated additional browser origins. Configure the Vite origin for local development when it differs from Flask's host. |
| `MANNKIDHUN_DATA_DIR` | Optional directory for the SQLite database and profile uploads. Defaults to `./instance`. |
| `AI_ASSISTANT_API_KEY` | Optional key for an OpenAI-compatible intent provider. Leave unset to use local rule-based intent parsing. |
| `AI_ASSISTANT_API_URL` | Optional HTTPS endpoint for the intent provider. |
| `AI_ASSISTANT_MODEL` | Model name sent to the configured intent provider. |

The optional assistant provider receives the current text request to extract structured search intent. It does not receive camera frames, session credentials, or listening history.

### 5. Run the backend

Activate the Python environment, then run:

```bash
python app.py
```

Flask starts at `http://127.0.0.1:5001` by default.

### 6. Run the frontend

In a second terminal:

```bash
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://127.0.0.1:5173`). The Vite development server proxies `/api` and `/predict` requests to Flask at port `5001`.

If the Vite origin differs from the Flask host, set the allowed origin before starting the backend:

**PowerShell**
```powershell
$env:MANNKIDHUN_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
python app.py
```

**macOS / Linux**
```bash
MANNKIDHUN_ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173" python app.py
```

Create an account at `/signup`, then open the Music Assistant or mood check-in.

## 🧪 Quality Checks

Run the production frontend build:

```bash
npm run build
```

Run frontend tests:

```bash
npm test
```

Run backend tests:

```bash
python -m unittest discover -s tests
```

GitHub Actions runs the frontend build and backend / frontend test suites on pushes and pull requests. CodeQL performs static security analysis.

## 🏗️ Architecture

```text
MannKiDhun
│
├── frontend/                  React + Vite application
│   └── src/
│       ├── components/        Reusable UI components
│       ├── context/           Shared player and app state
│       ├── hooks/             Camera and interaction hooks
│       ├── pages/             Application pages
│       └── styles/             UI styles
│
├── app.py                     Flask routes and application entry point
├── recommendation_engine.py   Catalogue, ranking, playlists and feedback
├── music_assistant.py         Natural-language music intent extraction
├── model_loader.py            Emotion-model artifact validation and loading
├── frame_validation.py        Input image-quality checks
├── prediction_aggregation.py  Multi-frame output aggregation
├── database_migrations.py     Versioned SQLite migrations
├── database_ops.py            Database backup / restore utilities
├── model/                     Model and label artifacts
├── tests/                     Backend and frontend tests
└── docs/                      Architecture, API, security and operations docs
```

For detailed design and operational notes, see:

- [Security and privacy](docs/SECURITY.md)
- [API documentation](docs/API.md)
- [Database and backups](docs/DATABASE.md)
- [Deployment and operations](docs/DEPLOYMENT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Catalogue sources](docs/CATALOGUE_SOURCES.md)
- [Product roadmap](docs/PRODUCT_ROADMAP.md)
- [Upgrade implementation status](docs/UPGRADE_STATUS.md)
- [Competitive analysis](docs/COMPETITIVE_ANALYSIS.md)

## 🔐 Privacy & Responsible Use

- Camera access requires an explicit user action; it is not enabled automatically.
- Five temporary frames are sent for expression analysis and processed in memory by the expression endpoint; the endpoint does not save the frames to disk.
- Model class scores are **not calibrated probabilities**. Frame consistency is not model accuracy, and the model has not been established as reliable on a labeled, subject-separated evaluation dataset.
- An expression estimate must be explicitly confirmed before it can select a mood-based suggestion. A manual selection remains available and can override the estimate.
- Facial expressions should not be treated as proof of a person's actual feelings or used for health, employment, educational, or other consequential decisions.
- Music DNA is disabled until the listener opts in. Mood journal entries are manually written and private to the account.
- Listening-history personalization is used only when enabled by the listener for a request.
- Public playlist sharing is optional. Private collaboration uses time-limited viewer or editor invitations.

## 🎧 Playback & Catalogue Notes

MannKiDhun uses a curated starter catalogue. It is not a full music-licensing or streaming catalogue, and the application does not host or sublicense recordings. Playback depends on third-party YouTube embeds and links; track availability, embedding permissions, and autoplay behavior are controlled by the provider and browser.

Context-aware ranking currently uses manually curated catalogue tags. It is a transparent metadata heuristic—not an audio-understanding model—and does not read location, calendar, activity sensors, heart rate, or wearable data.

## ☁️ Deployment

The repository includes a [Render Blueprint](render.yaml) that builds the React application and runs Flask through Gunicorn. The checked-in Blueprint uses Render's **Free** web-service plan and is intended for a demo.

> **Important:** The Render Free service uses an ephemeral filesystem. SQLite accounts, playlists, preferences, journal entries, and uploaded profile photos may be lost after a restart or redeploy. Do not treat the Free demo as durable user storage.

For persistent single-instance SQLite storage on Render:

1. Use a paid web-service plan that supports a persistent disk.
2. Attach a persistent disk mounted at `/var/data`.
3. Set `MANNKIDHUN_DATA_DIR=/var/data`.
4. Deploy, verify `/healthz`, and test a database backup and restore.

For multi-instance production use, move to a managed database and object storage, introduce shared rate limiting, schedule encrypted off-site backups, and rehearse recovery procedures.

See [Deployment](docs/DEPLOYMENT.md) and [Database](docs/DATABASE.md).

## ⚠️ Known Limitations

- The curated catalogue is a starter dataset and not a licensed streaming catalogue.
- Expression outputs are experimental and have not been validated as reliable emotion measurements.
- Context matching depends on the coverage and quality of manually curated metadata tags.
- Group listening rooms synchronize playlist state and recent presence through polling; they are not WebSocket-based and cannot guarantee sample-accurate audio synchronization.
- Browser speech features depend on speech APIs supported by the user's browser.
- Password-reset and verification email delivery are not configured.
- Login and assistant rate limits are process-local. Their in-memory registries are bounded, but the limits are not shared across workers or hosts.
- The Render Free deployment uses ephemeral storage and is not a durable production data store.

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for the full license text.

---

<p align="center">
  Built with 🎵 by <a href="https://github.com/naitik2043">Naitik Gupta</a>
</p>
