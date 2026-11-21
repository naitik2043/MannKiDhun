# Product roadmap

This roadmap separates shipped product behaviour from capabilities that remain future work. It intentionally avoids describing the current catalogue as broader than it is.

## Available today

- Manual mood selection and an optional expression check-in. Camera inference is opt-in, treated as an estimate, and does not persist raw frames.
- Catalogue-grounded assistant discovery with a local rules fallback.
- **Match / Change / Explore** discovery modes, with a selectable target mood for Change.
- Hybrid recommendations using mood/vibe, catalogue metadata, declared preferences, and opt-in listening history.
- Recommendation explanations, Like / Not for me feedback, and signed positive/negative history scoring.
- **Personal Music DNA**, disabled by default and enabled only with explicit consent. It privately summarises top languages, genres, artists, and listening signals from the current account's activity.
- A private **Mood & Music Journal** for manually entered mood labels and notes. Journal entries are not generated from facial-expression estimates.
- **Adaptive session builder** that creates recommendations and saves the resulting track IDs to the playback queue. It is a queue snapshot, not a live autonomous player.
- Natural-language playlist refinement that adds up to five catalogue matches for instructions such as a calmer vibe, a language, a genre, or more artist variety. It does not silently remove existing tracks.
- **Public playlist sharing and community discovery**. Owners choose which playlists are public; visitors can browse and open those playlists read-only.
- Browser-side voice-to-text input in English (India) and Hindi, subject to SpeechRecognition support in the browser.
- Indian-language intent recognition for Hindi, Punjabi, Tamil, Telugu, Bengali, Marathi, Gujarati, Malayalam, Kannada, Urdu, and Sanskrit. The seeded catalogue still has limited coverage, so supported language detection does not guarantee matching tracks.

## Still planned

1. **True collaborative playlists** — multi-user editing, invitations, roles, conflict resolution, and activity history. Current public links are read-only.
2. **Richer India-first catalogue** — add verified track metadata and playback links across regional languages, Indian indie, Bollywood, Punjabi, and other scenes. No unverified or invented links should be added.
3. **Full player and adaptive playback** — a persistent player with real playback progress, skip handling, queue replacement, and session adaptation while a track is playing.
4. **Voice conversation** — spoken responses and hands-free conversation; current voice support only transcribes input in the browser.
5. **More advanced Music DNA** — transparent preference controls, diversity tuning, profile export/reset, and confidence/coverage indicators.

## Engineering priorities before durable production use

- Move user/library persistence from the free service's ephemeral SQLite filesystem to a durable managed database and file store.
- Add versioned database migrations, tested backups, and restore drills.
- Implement CSRF protections, login throttling, distributed rate limiting, security headers, and a reviewed origin policy.
- Configure real password recovery and verification email delivery.
- Add dependency scanning, deployment monitoring, and alerting.
- Evaluate the expression model on a labeled, subject-separated dataset and document its limitations before making any accuracy claims.

## Product principles

- The listener's manual choice always takes priority over an expression estimate.
- Camera access is optional; raw frames are processed in memory and are not part of listening history or the journal.
- Assistant recommendations come from the available catalogue rather than invented track names or playback URLs.
- Personalisation uses listening history for ranking or Music DNA only with explicit consent.
- Public sharing is opt-in and read-only for visitors until proper collaborative permissions are implemented.
- The product must explain its recommendations and keep the listener in control.
