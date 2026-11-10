import { useEffect, useState } from "react";
import Header from "./Header.jsx";
import SiteFooter from "./SiteFooter.jsx";

const suggestedPrompts = [
  "Suggest something peaceful for the evening",
  "Recommend romantic songs in Hindi",
  "I want energetic music for travelling",
  "Find motivational songs for studying",
];

function AssistantPage({ user, theme, toggleTheme }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Tell me what you’d like to listen to. I’ll suggest tracks available in MannKiDhun’s catalogue.",
    },
  ]);
  const [message, setMessage] = useState("");
  const [lastIntent, setLastIntent] = useState(null);
  const [usePreferences, setUsePreferences] = useState(false);
  const [useHistory, setUseHistory] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [playlists, setPlaylists] = useState([]);
  const [newPlaylistName, setNewPlaylistName] = useState("");
  const [selectedPlaylists, setSelectedPlaylists] = useState({});
  const [activeSong, setActiveSong] = useState(null);
  const [actionStatus, setActionStatus] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/v1/playlists")
      .then(async (response) => {
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(result?.error || "Could not load playlists.");
        if (active) setPlaylists(result.playlists || []);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      });
    return () => {
      active = false;
    };
  }, []);

  async function ask(prompt = message) {
    const text = prompt.trim();
    if (!text || loading) return;
    setMessage("");
    setError("");
    setActionStatus("");
    setMessages((current) => [...current, { role: "user", text }]);
    setLoading(true);

    try {
      const response = await fetch("/api/v1/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          previous_intent: lastIntent,
          use_preferences: usePreferences,
          use_history: useHistory,
        }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) throw new Error(result?.error || "The assistant couldn’t answer just now.");
      setLastIntent(result.intent);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: result.response,
          recommendations: result.recommendations,
        },
      ]);
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "We couldn’t reach MannKiDhun. Check your connection and try again."
          : requestError.message,
      );
    } finally {
      setLoading(false);
    }
  }

  async function requestJson(url, options) {
    const response = await fetch(url, options);
    const result = await response.json().catch(() => null);
    if (!response.ok) throw new Error(result?.error || "That action couldn’t be completed.");
    return result;
  }

  async function addToQueue(song) {
    setActionStatus("");
    try {
      const { state } = await requestJson("/api/v1/users/me/playback-state");
      const queue = Array.isArray(state.queue) ? state.queue : [];
      if (!queue.some((entry) => Number(entry?.id ?? entry) === song.id)) {
        queue.push(song.id);
      }
      await requestJson("/api/v1/users/me/playback-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...state, queue }),
      });
      setActionStatus(`${song.title} was added to your saved queue.`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function saveSong(song) {
    setActionStatus("");
    try {
      await requestJson("/api/v1/users/me/saved-songs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ song_id: song.id }),
      });
      setActionStatus(`${song.title} was saved to your library.`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function addToPlaylist(song) {
    const playlistId = selectedPlaylists[song.id];
    if (!playlistId) return;
    setActionStatus("");
    try {
      await requestJson(`/api/v1/playlists/${playlistId}/tracks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ song_id: song.id }),
      });
      setActionStatus(`${song.title} was added to the selected playlist.`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createPlaylist(event) {
    event.preventDefault();
    const name = newPlaylistName.trim();
    if (!name) return;
    setError("");
    setActionStatus("");
    try {
      const result = await requestJson("/api/v1/playlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      setPlaylists((current) => [...current, result.playlist]);
      setNewPlaylistName("");
      setActionStatus(`${result.playlist.name} was created.`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function playSong(song) {
    const trackId = song.provider_track_id;
    if (song.provider === "youtube" && typeof trackId === "string" && /^[\w-]{11}$/.test(trackId)) {
      setActiveSong(song);
      return;
    }

    try {
      const providerUrl = new URL(song.provider_url);
      if (providerUrl.protocol !== "https:") throw new Error("Unsupported playback URL.");
      window.open(providerUrl.toString(), "_blank", "noopener,noreferrer");
    } catch {
      setError("This catalogue track does not have a supported playback link.");
    }
  }

  function clearConversation() {
    setMessages([
      {
        role: "assistant",
        text: "Tell me what you’d like to listen to. I’ll suggest tracks available in MannKiDhun’s catalogue.",
      },
    ]);
    setLastIntent(null);
    setError("");
    setActionStatus("");
    setActiveSong(null);
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
        <main className="assistant-main">
          <section className="assistant-heading">
            <p className="section-eyebrow">MANNKIDHUN MUSIC ASSISTANT</p>
            <h1>What sounds right to you?</h1>
            <p>
              Describe a mood, genre, language, artist, or moment. Suggestions come
              from the available catalogue—not made-up song listings.
            </p>
          </section>

          <section className="assistant-panel" aria-label="Music assistant conversation">
            <div className="assistant-toolbar">
              <span><span className="assistant-online-dot" /> Ready to discover</span>
              <button type="button" className="assistant-clear" onClick={clearConversation}>
                Clear conversation
              </button>
            </div>
            <form id="assistant-playlists" className="assistant-create-playlist" onSubmit={createPlaylist}>
              <label htmlFor="assistant-playlist-name">Create a playlist</label>
              <div>
                <input
                  id="assistant-playlist-name"
                  value={newPlaylistName}
                  maxLength={80}
                  onChange={(event) => setNewPlaylistName(event.target.value)}
                  placeholder="Name your playlist"
                />
                <button type="submit" disabled={!newPlaylistName.trim()}>Create</button>
              </div>
            </form>

            {activeSong && (
              <div className="assistant-player">
                <iframe
                  src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(activeSong.provider_track_id)}?playsinline=1`}
                  title={`Play ${activeSong.title} by ${activeSong.artist}`}
                  allow="encrypted-media; picture-in-picture"
                  referrerPolicy="strict-origin-when-cross-origin"
                  allowFullScreen
                />
              </div>
            )}

            <div className="assistant-messages" aria-live="polite">
              {messages.map((entry, index) => (
                <article className={`assistant-message assistant-message-${entry.role}`} key={`${entry.role}-${index}`}>
                  <p>{entry.text}</p>
                  {entry.recommendations?.length > 0 && (
                    <div className="assistant-track-list">
                      {entry.recommendations.map((song) => (
                        <article className="assistant-track" key={song.id}>
                          <img
                            src={song.thumbnail_url || "/mannkidhun.svg"}
                            alt=""
                            loading="lazy"
                          />
                          <div className="assistant-track-info">
                            <strong>{song.title}</strong>
                            <span>{song.artist}{song.genre ? ` · ${song.genre}` : ""}</span>
                            {song.provider_url && (
                              <a href={song.provider_url} target="_blank" rel="noopener noreferrer">
                                Open track on provider
                              </a>
                            )}
                          </div>
                          <div className="assistant-track-actions">
                            <button type="button" onClick={() => playSong(song)}>Play</button>
                            <button type="button" onClick={() => saveSong(song)}>Save</button>
                            <button type="button" onClick={() => addToQueue(song)}>Add to queue</button>
                            {playlists.length > 0 && (
                              <div className="assistant-playlist-action">
                                <select
                                  aria-label={`Playlist for ${song.title}`}
                                  value={selectedPlaylists[song.id] || ""}
                                  onChange={(event) => setSelectedPlaylists((current) => ({
                                    ...current,
                                    [song.id]: event.target.value,
                                  }))}
                                >
                                  <option value="">Choose playlist</option>
                                  {playlists.map((playlist) => (
                                    <option key={playlist.id} value={playlist.id}>{playlist.name}</option>
                                  ))}
                                </select>
                                <button
                                  type="button"
                                  disabled={!selectedPlaylists[song.id]}
                                  onClick={() => addToPlaylist(song)}
                                >
                                  Add to playlist
                                </button>
                              </div>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </article>
              ))}
              {loading && (
                <p className="assistant-typing" role="status">
                  Finding available tracks<span aria-hidden="true">…</span>
                </p>
              )}
            </div>

            {error && <p className="assistant-error" role="alert">{error}</p>}
            {actionStatus && <p className="assistant-status" role="status">{actionStatus}</p>}

            {messages.length === 1 && (
              <div className="assistant-prompts" aria-label="Suggested requests">
                {suggestedPrompts.map((prompt) => (
                  <button type="button" key={prompt} onClick={() => ask(prompt)} disabled={loading}>
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            <form
              className="assistant-composer"
              onSubmit={(event) => {
                event.preventDefault();
                ask();
              }}
            >
              <label className="assistant-input-label" htmlFor="assistant-message">Your music request</label>
              <div className="assistant-input-row">
                <input
                  id="assistant-message"
                  value={message}
                  maxLength={500}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder="Try “peaceful Hindi music for the evening”…"
                  disabled={loading}
                />
                <button type="submit" disabled={loading || !message.trim()}>
                  {loading ? "Thinking…" : "Send"}
                </button>
              </div>
              <div className="assistant-controls">
                <label>
                  <input
                    type="checkbox"
                    checked={usePreferences}
                    onChange={(event) => setUsePreferences(event.target.checked)}
                  />
                  Use my saved music preferences
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={useHistory}
                    onChange={(event) => setUseHistory(event.target.checked)}
                  />
                  Use my listening activity
                </label>
              </div>
              <p className="assistant-privacy">
                Chat is kept in this tab and isn’t saved by MannKiDhun. Personal
                preferences and listening activity are used only when selected.
                If an AI provider is configured, only your current request is sent
                to it to identify search intent.
              </p>
            </form>
          </section>
        </main>
        <SiteFooter user={user} />
      </div>
    </div>
  );
}

export default AssistantPage;
