# Product roadmap

This roadmap separates shipped behaviour from the remaining product work. Implemented features are listed with their current boundaries rather than overstating a prototype as a production service.

## Available today

- Manual mood selection and optional expression check-in; camera inference remains opt-in and raw frames are not saved.
- **Match / Change / Explore** modes, including explicit current/target mood choices.
- Catalogue-grounded music assistant, local intent fallback, explainable recommendations, Like / Not for me feedback, and signed positive/negative history ranking.
- **Personal Music DNA**, disabled by default, with private summaries for languages, genres, artists, listening tags, and recurring vibes.
- **Mood & Music Journal**, with manually entered moods and private notes.
- **Adaptive queue builder**, saved playback queue, and Start / Previous / Next controls. It is still a queue snapshot; tracks do not auto-advance when the YouTube embed ends.
- Natural-language playlist editing for add, remove, and reorder actions.
- Public playlists plus a community directory; invite-based viewer/editor collaboration with seven-day links, role changes, collaborator removal, and invite revocation.
- Browser-based voice dictation in Hindi and English (India), plus browser Read aloud for assistant replies.
- Verified initial regional catalogue additions for Punjabi, Bengali, Gujarati, Telugu, Tamil, Malayalam, and Marathi, alongside existing Hindi and English starter tracks. Supported language intent parsing is broader than currently populated songs.

## Remaining product work

1. **Full player experience** — a persistent site-wide player, media-session integration, automatic track-ended detection, durable position tracking, repeat/shuffle, and queue hand-off across pages. Current controls are assistant-page scoped and manually advanced.
2. **Real-time collaborative sessions** — live presence, simultaneous editing indicators, conflict resolution, activity stream, and invited-user notifications. Current collaboration is authenticated role-based editing without live presence.
3. **Verified India-first catalogue expansion** — continue adding sourced tracks for Kannada, Urdu, and other regional scenes. Never invent provider IDs or playback URLs.
4. **Richer context and personalization** — energy/tempo/era metadata, user-tunable diversity, profile coverage/confidence, export/reset, and session adaptation based on activity during playback.
5. **Conversational voice** — turn-taking, interruptible speech, and spoken follow-up questions. Current support is browser dictation plus text-to-speech.
6. **Wearable/context integrations** — only after privacy, consent, and reliability design.

## Engineering priorities before durable production use

- Move user/library persistence from free Render ephemeral SQLite storage to a managed durable database and file store.
- Add versioned migrations, tested backups, and restore drills.
- Implement CSRF protections, login throttling, distributed rate limiting, security headers, and a reviewed origin policy.
- Configure real password recovery and verification email delivery.
- Add dependency scanning, deployment monitoring, and alerting.
- Evaluate the expression model on a labeled, subject-separated dataset before making accuracy claims.

## Product principles

- The listener's manual choice always takes priority over an expression estimate.
- Camera access is optional; raw frames are not part of listening history or the journal.
- Recommendations come from the verified catalogue, never fabricated track names or IDs.
- Listening-history-based personalization requires explicit consent.
- Public sharing is opt-in; visitors are read-only unless they accept a role-based invite.
- Keep the listener informed and in control.
