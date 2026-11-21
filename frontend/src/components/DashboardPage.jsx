import { useEffect, useState } from "react";
import Header from "./Header.jsx";
import SiteFooter from "./SiteFooter.jsx";

function formatActivityDate(value) {
  if (typeof value !== "string" || !value) return "";
  const normalized = value.includes("T") ? value : value.replace(" ", "T") + "Z";
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

function interactionLabel(type) {
  const labels = {
    play: "Played",
    listen: "Listened",
    complete: "Completed",
    like: "Liked",
    skip: "Skipped",
  };
  return labels[type] || "Activity";
}

function DashboardPage({ user, theme, toggleTheme }) {
  const firstName = user?.name?.trim().split(/\s+/)[0] || "there";
  const [history, setHistory] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [playlistsLoading, setPlaylistsLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [playlistsError, setPlaylistsError] = useState("");
  const [journalEntries, setJournalEntries] = useState([]);
  const [journalInsights, setJournalInsights] = useState([]);
  const [journalMood, setJournalMood] = useState("neutral");
  const [journalNote, setJournalNote] = useState("");
  const [journalLoading, setJournalLoading] = useState(true);
  const [journalStatus, setJournalStatus] = useState("");
  const [journalError, setJournalError] = useState("");
  const [musicDna, setMusicDna] = useState(null);
  const [musicDnaLoading, setMusicDnaLoading] = useState(true);
  const [musicDnaBusy, setMusicDnaBusy] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadHistory() {
      try {
        const response = await fetch("/api/v1/users/me/listening-history");
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(result?.error || "Could not load listening history.");
        if (active) setHistory(Array.isArray(result?.history) ? result.history : []);
      } catch (error) {
        if (active) setHistoryError(error.message || "Could not load listening history.");
      } finally {
        if (active) setHistoryLoading(false);
      }
    }

    async function loadPlaylists() {
      try {
        const response = await fetch("/api/v1/playlists");
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(result?.error || "Could not load your playlists.");
        if (active) setPlaylists(Array.isArray(result?.playlists) ? result.playlists : []);
      } catch (error) {
        if (active) setPlaylistsError(error.message || "Could not load your playlists.");
      } finally {
        if (active) setPlaylistsLoading(false);
      }
    }

    async function loadJournal() {
      try {
        const response = await fetch("/api/v1/users/me/mood-journal");
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(result?.error || "Could not load your mood journal.");
        if (active) {
          setJournalEntries(Array.isArray(result?.entries) ? result.entries : []);
          setJournalInsights(Array.isArray(result?.mood_summary) ? result.mood_summary : []);
        }
      } catch (error) {
        if (active) setJournalError(error.message || "Could not load your mood journal.");
      } finally {
        if (active) setJournalLoading(false);
      }
    }

    async function loadMusicDna() {
      try {
        const response = await fetch("/api/v1/users/me/music-dna");
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(result?.error || "Could not load Music DNA.");
        if (active) setMusicDna(result);
      } catch (error) {
        if (active) setMusicDna({ enabled: false, error: error.message });
      } finally {
        if (active) setMusicDnaLoading(false);
      }
    }

    loadHistory();
    loadPlaylists();
    loadJournal();
    loadMusicDna();
    return () => { active = false; };
  }, []);

  async function saveJournalEntry(event) {
    event.preventDefault();
    setJournalError("");
    setJournalStatus("");
    try {
      const response = await fetch("/api/v1/users/me/mood-journal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mood: journalMood, note: journalNote }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(result?.error || "Could not save your journal entry.");
      setJournalEntries((current) => [result.entry, ...current].slice(0, 30));
      setJournalNote("");
      setJournalStatus("Your private mood note was saved.");
    } catch (error) {
      setJournalError(error.message || "Could not save your journal entry.");
    }
  }

  async function deleteJournalEntry(entryId) {
    setJournalError("");
    setJournalStatus("");
    try {
      const response = await fetch(`/api/v1/users/me/mood-journal/${entryId}`, { method: "DELETE" });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(result?.error || "Could not delete this entry.");
      setJournalEntries((current) => current.filter((entry) => entry.id !== entryId));
      setJournalStatus("Journal entry deleted.");
    } catch (error) {
      setJournalError(error.message || "Could not delete this entry.");
    }
  }

  async function toggleMusicDna() {
    setMusicDnaBusy(true);
    try {
      const enabled = !musicDna?.enabled;
      const response = await fetch("/api/v1/users/me/music-dna/consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(result?.error || "Could not update Music DNA consent.");
      if (enabled) {
        const dnaResponse = await fetch("/api/v1/users/me/music-dna");
        const dnaResult = await dnaResponse.json().catch(() => null);
        if (!dnaResponse.ok) throw new Error(dnaResult?.error || "Could not build Music DNA.");
        setMusicDna(dnaResult);
      } else {
        setMusicDna({ enabled: false, message: "Music DNA is turned off." });
      }
    } catch (error) {
      setJournalError(error.message || "Could not update Music DNA.");
    } finally {
      setMusicDnaBusy(false);
    }
  }

  async function resetMusicDna() {
    const confirmed = window.confirm(
      "Reset Music DNA and listening history? This deletes your plays, likes, skips, and recommendation feedback. Saved songs and your declared preferences will be kept."
    );
    if (!confirmed) return;
    setMusicDnaBusy(true);
    setJournalError("");
    try {
      const response = await fetch("/api/v1/users/me/music-dna", { method: "DELETE" });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(result?.error || "Could not reset Music DNA.");
      setMusicDna({ enabled: false, message: "Music DNA has been reset." });
      setHistory([]);
      setJournalStatus("Music DNA and listening history were reset. Saved songs and declared preferences were kept.");
    } catch (error) {
      setJournalError(error.message || "Could not reset Music DNA.");
    } finally {
      setMusicDnaBusy(false);
    }
  }

  function renderDnaItems(title, items) {
    return (
      <div className="dashboard-dna-group">
        <h3>{title}</h3>
        {items?.length ? (
          <div className="flex flex-wrap gap-2">
            {items.map((item) => (
              <span className="dashboard-dna-chip" key={item.name}>
                {item.name}
              </span>
            ))}
          </div>
        ) : <p>Not enough listening activity yet.</p>}
      </div>
    );
  }

  async function signOut() {
    const response = await fetch("/api/auth/logout", { method: "POST" });
    if (!response.ok) throw new Error("Could not sign out. Please try again.");
    window.location.assign("/");
  }

  return (
    <div className="app-shell">
      <div className="page-shell mx-auto min-h-screen w-[min(1120px,calc(100%-40px))]">
        <Header theme={theme} onToggleTheme={toggleTheme} user={user} onSignOut={signOut} />
        <main className="dashboard-main grid gap-9 pt-[38px] pb-[14px] max-[760px]:gap-7 max-[760px]:pt-7">
          <section className="dashboard-welcome flex items-center justify-between gap-5 max-[600px]:items-start max-[600px]:flex-col">
            <div>
              <p className="section-eyebrow">YOUR LISTENING SPACE</p>
              <h1>Welcome, {firstName}.</h1>
              <p>Find a song for this moment, your way.</p>
            </div>
            <div className="dashboard-welcome-actions grid justify-items-end gap-[9px] max-[600px]:justify-items-start">
              <a className="nav-cta dashboard-welcome-cta" href="/app">
                Start a vibe check <span aria-hidden="true">→</span>
              </a>
              <a className="dashboard-text-link" href="/assistant">
                Ask the music assistant <span aria-hidden="true">→</span>
              </a>
            </div>
          </section>

          <section className="dashboard-section" aria-labelledby="music-dna-title">
            <div className="dashboard-section-heading">
              <div>
                <p className="section-eyebrow">YOUR TASTE, MADE CLEAR</p>
                <h2 id="music-dna-title">Personal Music DNA</h2>
              </div>
            </div>
            {musicDnaLoading ? (
              <p role="status">Building your listening profile…</p>
            ) : musicDna?.enabled ? (
              <div className="dashboard-empty grid gap-4">
                <p>Your profile is based on the catalogue tracks and feedback linked to your account.</p>
                <div className="grid grid-cols-2 gap-4 max-[520px]:grid-cols-1">
                  {renderDnaItems("Top languages", musicDna.top_languages)}
                  {renderDnaItems("Top genres", musicDna.top_genres)}
                  {renderDnaItems("Favourite artists", musicDna.top_artists)}
                  {renderDnaItems("Favourite listening styles", musicDna.top_tags)}
                  {renderDnaItems("Vibes you return to", musicDna.top_vibes)}
                  <div className="dashboard-dna-group">
                    <h3>Listening signals</h3>
                    <p>{musicDna.summary?.plays || 0} plays · {musicDna.summary?.likes || 0} likes · {musicDna.summary?.skips || 0} skips</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button type="button" className="dashboard-text-link" onClick={toggleMusicDna} disabled={musicDnaBusy}>
                    {musicDnaBusy ? "Updating…" : "Turn off Music DNA"}
                  </button>
                  <button type="button" className="dashboard-text-link" onClick={resetMusicDna} disabled={musicDnaBusy}>
                    Reset DNA & listening history
                  </button>
                </div>
              </div>
            ) : (
              <div className="dashboard-empty">
                <span className="dashboard-empty-icon" aria-hidden="true">♫</span>
                <div>
                  <h3>Your taste profile is yours to enable</h3>
                  <p>With your permission, MannKiDhun summarises your saved preferences and listening feedback into a private profile. You can turn it off at any time.</p>
                </div>
                <button type="button" className="dashboard-text-link" onClick={toggleMusicDna} disabled={musicDnaBusy}>
                  {musicDnaBusy ? "Enabling…" : "Enable my Music DNA"}
                </button>
              </div>
            )}
          </section>

          <section className="dashboard-section" aria-labelledby="journal-title">
            <div className="dashboard-section-heading">
              <div>
                <p className="section-eyebrow">A PRIVATE CHECK-IN</p>
                <h2 id="journal-title">Mood & music journal</h2>
              </div>
            </div>
            <form className="dashboard-empty dashboard-journal-form" onSubmit={saveJournalEntry}>
              <p>Record how you feel in your own words. Entries are private to your account; camera frames and expression estimates are never added here.</p>
              <label className="grid gap-1">
                How are you feeling?
                <select value={journalMood} onChange={(event) => setJournalMood(event.target.value)}>
                  <option value="neutral">Neutral</option>
                  <option value="happy">Happy</option>
                  <option value="sad">Sad</option>
                  <option value="relaxed">Relaxed</option>
                  <option value="energetic">Energetic</option>
                  <option value="romantic">Romantic</option>
                  <option value="focused">Focused</option>
                  <option value="motivational">Motivated</option>
                  <option value="devotional">Spiritual</option>
                </select>
              </label>
              <label className="grid gap-1">
                Note (optional)
                <textarea
                  value={journalNote}
                  onChange={(event) => setJournalNote(event.target.value)}
                  maxLength={500}
                  rows={3}
                  placeholder="A few words about your day or the music you want…"
                />
              </label>
              <button type="submit" disabled={!journalMood}>Save private entry</button>
            </form>
            {journalError && <p className="assistant-error" role="alert">{journalError}</p>}
            {journalStatus && <p className="assistant-status" role="status">{journalStatus}</p>}
            {journalInsights.length > 0 && (
              <div className="dashboard-empty grid gap-2">
                <h3>Recent mood patterns · your last 30 entries</h3>
                <div className="flex flex-wrap gap-2">
                  {journalInsights.map((item) => (
                    <span className="dashboard-dna-chip" key={item.mood}>
                      {item.mood} · {item.entries}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {journalLoading ? (
              <p role="status">Loading your journal…</p>
            ) : journalEntries.length ? (
              <div className="grid gap-3">
                {journalEntries.slice(0, 5).map((entry) => (
                  <article className="dashboard-empty flex items-start justify-between gap-3" key={entry.id}>
                    <div>
                      <h3>{entry.mood}</h3>
                      {entry.note && <p>{entry.note}</p>}
                      <p>{formatActivityDate(entry.created_at)}</p>
                    </div>
                    <button type="button" className="dashboard-text-link" onClick={() => deleteJournalEntry(entry.id)}>
                      Delete
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <p>No journal entries yet. Add a small check-in above.</p>
            )}
          </section>

          <section
            className="dashboard-discover grid min-h-[280px] grid-cols-[minmax(0,1fr)_minmax(190px,0.65fr)] items-center gap-[22px] overflow-hidden p-[clamp(24px,5vw,42px)] max-[520px]:grid-cols-1"
            aria-labelledby="discover-title"
          >
            <div className="dashboard-discover-copy">
              <p className="section-eyebrow">DISCOVER MUSIC</p>
              <h2 id="discover-title">Find a tune for right now.</h2>
              <p>
                Choose a vibe yourself or opt into an expression check-in.
                Either way, the result is only a suggestion—you decide what feels right.
              </p>
              <a className="nav-cta" href="/app">
                Explore by vibe <span aria-hidden="true">→</span>
              </a>
              <a className="dashboard-text-link" href="/assistant">
                Describe what you want to hear <span aria-hidden="true">→</span>
              </a>
            </div>
            <div className="dashboard-sound-art" aria-hidden="true">
              <span className="dashboard-sound-orbit" />
              <span className="dashboard-sound-note">♫</span>
              <span className="dashboard-sound-wave">♪ &nbsp; ♫ &nbsp; ♪</span>
            </div>
          </section>

          <section className="dashboard-section" aria-labelledby="recent-title">
            <div className="dashboard-section-heading">
              <div>
                <p className="section-eyebrow">YOUR LISTENING ACTIVITY</p>
                <h2 id="recent-title">Recently played</h2>
              </div>
            </div>
            {historyLoading ? (
              <p role="status">Loading your listening history…</p>
            ) : historyError ? (
              <p className="assistant-error" role="alert">{historyError}</p>
            ) : history.length > 0 ? (
              <div className="grid gap-3">
                {history.slice(0, 5).map((track, index) => {
                  const playedOn = formatActivityDate(track.created_at);
                  return (
                    <article
                      className="dashboard-empty flex items-center justify-between gap-4 max-[520px]:items-start"
                      key={index}
                    >
                      <div className="min-w-0">
                        <h3 className="truncate">{track.title}</h3>
                        <p>{track.artist || "Unknown artist"}{track.language ? " · " + track.language : ""}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <span>{interactionLabel(track.interaction_type)}</span>
                        {playedOn && <p>{playedOn}</p>}
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="dashboard-empty">
                <span className="dashboard-empty-icon" aria-hidden="true">♫</span>
                <div>
                  <h3>Your listening history starts here</h3>
                  <p>Play a track from the Music Assistant and it will appear here.</p>
                </div>
                <a href="/assistant">Explore the catalogue <span aria-hidden="true">→</span></a>
              </div>
            )}
          </section>

          <section className="dashboard-section" aria-labelledby="playlists-title">
            <div className="dashboard-section-heading">
              <div>
                <p className="section-eyebrow">YOUR COLLECTIONS</p>
                <h2 id="playlists-title">Your playlists</h2>
              </div>
              <a className="dashboard-text-link" href="/assistant#assistant-playlists">
                Create playlist <span aria-hidden="true">→</span>
              </a>
            </div>
            {playlistsLoading ? (
              <p role="status">Loading your playlists…</p>
            ) : playlistsError ? (
              <p className="assistant-error" role="alert">{playlistsError}</p>
            ) : playlists.length > 0 ? (
              <div className="grid gap-3">
                {playlists.map((playlist) => (
                  <article
                    className="dashboard-empty flex items-center justify-between gap-4 max-[520px]:items-start"
                    key={playlist.id}
                  >
                    <div className="min-w-0">
                      <h3 className="truncate">{playlist.name}</h3>
                      <p>{playlist.track_count === 1 ? "1 track" : (playlist.track_count || 0) + " tracks"}</p>
                    </div>
                    <a className="dashboard-text-link shrink-0" href="/assistant#assistant-playlists">
                      Add songs <span aria-hidden="true">→</span>
                    </a>
                  </article>
                ))}
              </div>
            ) : (
              <div className="dashboard-empty">
                <span className="dashboard-empty-icon" aria-hidden="true">♫</span>
                <div>
                  <h3>Keep the songs you love together</h3>
                  <p>Create a playlist and add tracks from the Music Assistant.</p>
                </div>
                <a href="/assistant#assistant-playlists">Create a playlist <span aria-hidden="true">→</span></a>
              </div>
            )}
          </section>
        </main>
        <SiteFooter user={user} />
      </div>
    </div>
  );
}

export default DashboardPage;
