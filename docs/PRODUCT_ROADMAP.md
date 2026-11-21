# Product roadmap

This roadmap separates capabilities already present in the repository from ideas that still need implementation. A roadmap item is not a claim that the feature is currently available.

## Available today

- Manual mood selection and an optional expression check-in. Camera inference is opt-in, is treated as an estimate, and does not persist raw frames.
- Catalogue-grounded music discovery through the assistant, with local intent parsing as a fallback when the optional intent provider is unavailable.
- Hybrid recommendation scoring using mood/vibe, catalogue metadata, user preferences, and interaction history.
- Recommendation explanations surfaced in the assistant.
- Explicit Like and Not for me feedback, with positive and negative history weights.
- Saved songs, user playlists, listening-history endpoints, and playback-state storage.
- Dashboard sections for recent listening activity and user playlist summaries.
- Hindi and English catalogue entries and preference filters, subject to the catalogue's actual coverage.

## Next product increments

1. **Match / Change / Explore modes** — make the listener's intent explicit: fit the current mood, move toward a selected mood, or browse beyond the current mood.
2. **Personal Music DNA** — build a transparent preference profile from genres, languages, artists, tags, and consented feedback, with controls to reset it.
3. **Adaptive listening sessions** — adjust a session playlist from new feedback without taking control away from the listener.
4. **Natural-language playlist editing** — let users request changes such as calmer tracks, more Hindi songs, or greater artist variety.
5. **Mood and music journal** — offer optional user-entered reflections and private listening insights; never store raw camera frames as journal content.
6. **India-first catalogue enrichment** — improve reliable coverage for Bollywood, Indian indie, Punjabi, and regional-language discovery using verified track metadata.
7. **Collaborative discovery** — add shared playlists only after ownership, visibility, consent, and abuse controls are designed.
8. **Voice interaction** — consider speech input as an accessibility and convenience layer after the text assistant is stable.

## Engineering priorities before durable production use

- Move user/library persistence from the free service's ephemeral SQLite filesystem to a durable managed database and file store.
- Add versioned database migrations, tested backups, and restore drills.
- Implement CSRF protections, login throttling, distributed rate limiting, security headers, and a reviewed origin policy.
- Configure real password recovery and verification email delivery.
- Add dependency scanning, deployment monitoring, and alerting.
- Evaluate the expression model on a labeled, subject-separated dataset and document its limitations before making any accuracy claims.

## Product principles

- The listener's manual choice always takes priority over an expression estimate.
- Camera access is optional; raw frames are processed in memory and are not part of listening history.
- Assistant recommendations come from the available catalogue rather than invented track names or playback links.
- Personalisation uses preferences/history only with explicit consent.
- The product must explain its recommendations and keep the listener in control.
