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

    loadHistory();
    loadPlaylists();
    return () => { active = false; };
  }, []);

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
