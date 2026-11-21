import { useEffect, useRef, useState } from "react";
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
  const [mode, setMode] = useState("match");
  const [currentMood, setCurrentMood] = useState("");
  const [targetMood, setTargetMood] = useState("relaxed");
  const [isPublicPlaylist, setIsPublicPlaylist] = useState(false);
  const [refinePlaylistId, setRefinePlaylistId] = useState("");
  const [collaboratorsByPlaylist, setCollaboratorsByPlaylist] = useState({});
  const [refineInstruction, setRefineInstruction] = useState("");
  const [voiceLanguage, setVoiceLanguage] = useState("en-IN");
  const [isListening, setIsListening] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [sessionTracks, setSessionTracks] = useState([]);
  const [sessionIndex, setSessionIndex] = useState(-1);
  const recognitionRef = useRef(null);

  useEffect(() => {
    let active = true;

    async function loadPlaylists() {
      const params = new URLSearchParams(window.location.search);
      const invitePlaylist = params.get("invite_playlist");
      const inviteToken = params.get("invite_token");

      if (invitePlaylist && inviteToken && /^\\d+$/.test(invitePlaylist)) {
        try {
          const inviteResponse = await fetch(`/api/v1/playlists/${invitePlaylist}/invites/accept`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: inviteToken }),
          });
          const inviteResult = await inviteResponse.json().catch(() => null);
          if (!inviteResponse.ok) {
            throw new Error(inviteResult?.error || "This playlist invitation could not be accepted.");
          }
          if (active) {
            setActionStatus(`You joined ${inviteResult.playlist.name} as a ${inviteResult.playlist.role}.`);
          }
          window.sessionStorage.removeItem("mannkidhun_pending_playlist_invite");
          window.history.replaceState({}, document.title, window.location.pathname);
        } catch (inviteError) {
          window.sessionStorage.removeItem("mannkidhun_pending_playlist_invite");
          if (active) setError(inviteError.message || "This playlist invitation could not be accepted.");
        }
      }

      try {
        const response = await fetch("/api/v1/playlists");
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(result?.error || "Could not load playlists.");
        if (active) setPlaylists(result.playlists || []);
      } catch (requestError) {
        if (active) setError(requestError.message || "Could not load playlists.");
      }
    }

    loadPlaylists();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => () => {
    if (recognitionRef.current) recognitionRef.current.stop();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
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
          mode,
          current_mood: currentMood || null,
          target_mood: mode === "change" ? targetMood : null,
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

  async function buildAdaptiveSession() {
    setError("");
    setActionStatus("");
    try {
      const result = await requestJson("/api/v1/users/me/adaptive-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          mood: mode === "change" ? targetMood : currentMood || null,
          use_preferences: usePreferences,
          use_history: useHistory,
          limit: 8,
        }),
      });
      const tracks = Array.isArray(result.recommendations) ? result.recommendations : [];
      setSessionTracks(tracks);
      setSessionIndex(-1);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: result.message || "Your adaptive listening session is ready.",
        },
      ]);
      setActionStatus("Your adaptive session is saved to your listening queue. Start it when you're ready.");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function refinePlaylist(event) {
    event.preventDefault();
    const instruction = refineInstruction.trim();
    if (!refinePlaylistId || !instruction) return;
    setError("");
    setActionStatus("");
    try {
      const result = await requestJson(`/api/v1/playlists/${refinePlaylistId}/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction }),
      });
      setPlaylists((current) => current.map((playlist) =>
        playlist.id === Number(refinePlaylistId)
          ? { ...playlist, track_count: result.playlist?.tracks?.length ?? playlist.track_count }
          : playlist
      ));
      setRefineInstruction("");
      if (result.removed_count) {
        setActionStatus(`Removed ${result.removed_count} track(s) from ${result.playlist.name}.`);
      } else if (result.reordered) {
        setActionStatus(`Moved ${result.moved_track.title} in ${result.playlist.name}.`);
      } else {
        setActionStatus(
          result.added_count
            ? `Added ${result.added_count} track(s) to ${result.playlist.name}.`
            : "No new catalogue tracks matched that instruction. Try a mood, language, genre, or artist.",
        );
      }
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function loadCollaborators(playlist) {
    setError("");
    try {
      const result = await requestJson(`/api/v1/playlists/${playlist.id}/collaborators`);
      setCollaboratorsByPlaylist((current) => ({ ...current, [playlist.id]: result.collaborators || [] }));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function updateCollaboratorRole(playlist, collaborator, role) {
    try {
      await requestJson(`/api/v1/playlists/${playlist.id}/collaborators/${collaborator.user_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      await loadCollaborators(playlist);
      setActionStatus(`${collaborator.name}'s access is now ${role}.`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function removeCollaborator(playlist, collaborator) {
    try {
      await requestJson(`/api/v1/playlists/${playlist.id}/collaborators/${collaborator.user_id}`, {
        method: "DELETE",
      });
      await loadCollaborators(playlist);
      setActionStatus(`${collaborator.name} no longer has access to this playlist.`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createCollaboratorInvite(playlist) {
    setError("");
    setActionStatus("");
    try {
      const result = await requestJson(`/api/v1/playlists/${playlist.id}/invites`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "editor" }),
      });
      try {
        await navigator.clipboard.writeText(result.invite_url);
        setActionStatus("Editor invitation link copied. It expires on " + result.expires_at + ".");
      } catch {
        setActionStatus("Share this editor invitation link: " + result.invite_url);
      }
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function togglePlaylistSharing(playlist) {
    setError("");
    setActionStatus("");
    try {
      const result = await requestJson(`/api/v1/playlists/${playlist.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_public: !playlist.is_public }),
      });
      const updated = result.playlist || { ...playlist, is_public: !playlist.is_public };
      setPlaylists((current) => current.map((item) => item.id === playlist.id ? updated : item));
      if (updated.is_public) {
        const shareUrl = `${window.location.origin}/playlists/${playlist.id}`;
        try {
          await navigator.clipboard.writeText(shareUrl);
          setActionStatus("Public playlist link copied: " + shareUrl);
        } catch {
          setActionStatus("Playlist is public. Share this link: " + shareUrl);
        }
      } else {
        setActionStatus("Playlist is private again.");
      }
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function playSessionTrack(index) {
    if (index < 0 || index >= sessionTracks.length) return;
    const song = sessionTracks[index];
    setSessionIndex(index);
    playSong(song);
    try {
      const { state } = await requestJson("/api/v1/users/me/playback-state");
      await requestJson("/api/v1/users/me/playback-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...state,
          current_song_id: song.id,
          position_ms: 0,
          queue: sessionTracks.map((track) => track.id),
        }),
      });
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function speakMessage(text) {
    if (!text || !("speechSynthesis" in window) || typeof window.SpeechSynthesisUtterance !== "function") {
      setVoiceError("Spoken responses are not supported in this browser.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.lang = voiceLanguage;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    setVoiceError("");
    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  function stopSpeaking() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }

  function startVoiceInput() {
    setVoiceError("");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceError("Voice input is not supported in this browser. You can type your request instead.");
      return;
    }
    if (recognitionRef.current) recognitionRef.current.stop();
    const recognition = new SpeechRecognition();
    recognition.lang = voiceLanguage;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript;
      if (transcript) setMessage((current) => (current ? current + " " : "") + transcript);
    };
    recognition.onerror = () => setVoiceError("We couldn't capture that voice request. Please try again.");
    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    setIsListening(true);
    try {
      recognition.start();
    } catch {
      setIsListening(false);
      setVoiceError("Voice input could not start. Please try again.");
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

  async function sendFeedback(song, eventType) {
    setError("");
    setActionStatus("");
    try {
      await requestJson("/api/v1/users/me/listening-history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          song_id: song.id,
          event_type: eventType,
          source: "assistant",
        }),
      });
      setActionStatus(
        eventType === "like"
          ? "Thanks — your positive feedback has been saved."
          : "Thanks — this track will be ranked lower in future history-based suggestions.",
      );
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
        body: JSON.stringify({ name, is_public: isPublicPlaylist }),
      });
      setPlaylists((current) => [...current, { ...result.playlist, role: "owner", is_owner: true }]);
      setNewPlaylistName("");
      setIsPublicPlaylist(false);
      setActionStatus(`${result.playlist.name} was created.`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function recordPlay(song) {
    fetch("/api/v1/users/me/listening-history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        song_id: song.id,
        event_type: "play",
        source: "assistant",
      }),
    }).catch(() => {
      // Keep playback available even when history recording is temporarily offline.
    });
  }

  function playSong(song) {
    const trackId = song.provider_track_id;
    if (song.provider === "youtube" && typeof trackId === "string" && /^[\w-]{11}$/.test(trackId)) {
      recordPlay(song);
      setActiveSong(song);
      return;
    }

    try {
      const providerUrl = new URL(song.provider_url);
      if (providerUrl.protocol !== "https:") throw new Error("Unsupported playback URL.");
      recordPlay(song);
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
            <section className="assistant-discovery-controls" aria-label="Discovery mode">
              <label>
                Discovery mode
                <select value={mode} onChange={(event) => setMode(event.target.value)}>
                  <option value="match">Match my mood</option>
                  <option value="change">Change my mood</option>
                  <option value="explore">Explore freely</option>
                </select>
              </label>
              {mode === "match" && (
                <label>
                  Current mood (optional)
                  <select value={currentMood} onChange={(event) => setCurrentMood(event.target.value)}>
                    <option value="">Use the mood in my request</option>
                    <option value="happy">Happy</option>
                    <option value="sad">Sad</option>
                    <option value="relaxed">Relaxed</option>
                    <option value="energetic">Energetic</option>
                    <option value="romantic">Romantic</option>
                    <option value="focused">Focused</option>
                    <option value="motivational">Motivational</option>
                    <option value="devotional">Devotional</option>
                  </select>
                </label>
              )}
              {mode === "change" && (
                <label>
                  Mood you want to move toward
                  <select value={targetMood} onChange={(event) => setTargetMood(event.target.value)}>
                    <option value="happy">Happy</option>
                    <option value="sad">Sad</option>
                    <option value="relaxed">Relaxed</option>
                    <option value="energetic">Energetic</option>
                    <option value="romantic">Romantic</option>
                    <option value="focused">Focused</option>
                    <option value="motivational">Motivational</option>
                    <option value="devotional">Devotional</option>
                  </select>
                </label>
              )}
              <button type="button" onClick={buildAdaptiveSession} disabled={loading}>
                Build adaptive session
              </button>
            </section>
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
              <label className="assistant-public-toggle">
                <input
                  type="checkbox"
                  checked={isPublicPlaylist}
                  onChange={(event) => setIsPublicPlaylist(event.target.checked)}
                />
                Make this playlist public and shareable
              </label>
            </form>
            {playlists.length > 0 && (
              <section className="assistant-playlist-tools" aria-label="Playlist tools">
                <h2>Your playlists</h2>
                {playlists.map((playlist) => (
                  <div className="assistant-playlist-row" key={playlist.id}>
                    <span>
                      {playlist.name} · {playlist.track_count || 0} tracks
                      {playlist.is_owner ? " · Owner" : " · " + (playlist.role || "Collaborator")}
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {playlist.is_owner && (
                        <>
                          <button type="button" onClick={() => createCollaboratorInvite(playlist)}>
                            Invite editor
                          </button>
                          <button type="button" onClick={() => loadCollaborators(playlist)}>
                            Manage collaborators
                          </button>
                          <button type="button" onClick={() => togglePlaylistSharing(playlist)}>
                            {playlist.is_public ? "Copy public link / Make private" : "Make public"}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
                {playlists.filter((playlist) => playlist.is_owner && collaboratorsByPlaylist[playlist.id]).map((playlist) => (
                  <div className="assistant-collaborator-list" key={`collaborators-${playlist.id}`}>
                    <h3>People editing {playlist.name}</h3>
                    {collaboratorsByPlaylist[playlist.id].length ? collaboratorsByPlaylist[playlist.id].map((collaborator) => (
                      <div className="assistant-playlist-row" key={collaborator.user_id}>
                        <span>{collaborator.name}</span>
                        <select
                          aria-label={`Role for ${collaborator.name}`}
                          value={collaborator.role}
                          onChange={(event) => updateCollaboratorRole(playlist, collaborator, event.target.value)}
                        >
                          <option value="viewer">Viewer</option>
                          <option value="editor">Editor</option>
                        </select>
                        <button type="button" onClick={() => removeCollaborator(playlist, collaborator)}>
                          Remove access
                        </button>
                      </div>
                    )) : <p>No collaborators have joined yet.</p>}
                  </div>
                ))}
                <form className="assistant-refine-playlist" onSubmit={refinePlaylist}>
                  <label>
                    Refine a playlist with words
                    <select
                      value={refinePlaylistId}
                      onChange={(event) => setRefinePlaylistId(event.target.value)}
                      required
                    >
                      <option value="">Choose playlist</option>
                      {playlists.map((playlist) => (
                        <option key={playlist.id} value={playlist.id}>{playlist.name}</option>
                      ))}
                    </select>
                  </label>
                  <input
                    value={refineInstruction}
                    onChange={(event) => setRefineInstruction(event.target.value)}
                    maxLength={200}
                    placeholder="Try “add peaceful music”, “remove last song”, or “move Believer to the top”"
                    aria-label="Playlist refinement instruction"
                  />
                  <button type="submit" disabled={!refinePlaylistId || refineInstruction.trim().length < 3}>
                    Refine playlist
                  </button>
                </form>
              </section>
            )}

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
            {sessionTracks.length > 0 && (
              <div className="assistant-session-player" aria-label="Adaptive listening session">
                <div>
                  <strong>Adaptive session · {sessionTracks.length} tracks</strong>
                  <span>
                    {sessionIndex >= 0
                      ? `Now on ${sessionIndex + 1} of ${sessionTracks.length}: ${sessionTracks[sessionIndex].title}`
                      : "Your queue is ready. Start the first track when you want."}
                  </span>
                  <ol className="assistant-session-track-list">
                    {sessionTracks.map((track, index) => (
                      <li key={track.id}>
                        <span>{index + 1}. {track.title}</span>
                        <span>{track.artist || "Unknown artist"}</span>
                      </li>
                    ))}
                  </ol>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => playSessionTrack(0)}>Start session</button>
                  <button
                    type="button"
                    onClick={() => playSessionTrack(sessionIndex - 1)}
                    disabled={sessionIndex <= 0}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={() => playSessionTrack(sessionIndex + 1)}
                    disabled={sessionIndex < 0 || sessionIndex >= sessionTracks.length - 1}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}

            <div className="assistant-messages" aria-live="polite">
              {messages.map((entry, index) => (
                <article className={`assistant-message assistant-message-${entry.role}`} key={`${entry.role}-${index}`}>
                  <p>{entry.text}</p>
                  {entry.role === "assistant" && (
                    <button
                      type="button"
                      className="assistant-read-aloud"
                      onClick={() => speakMessage(entry.text)}
                    >
                      Read aloud
                    </button>
                  )}
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
                            {song.explanation && (
                              <small className="assistant-track-explanation">
                                Why this fits: {song.explanation}
                              </small>
                            )}
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
                            <button type="button" onClick={() => sendFeedback(song, "like")}>Like</button>
                            <button type="button" onClick={() => sendFeedback(song, "skip")}>Not for me</button>
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
                <button
                  type="button"
                  onClick={startVoiceInput}
                  disabled={loading || isListening}
                  aria-label="Use voice input"
                >
                  {isListening ? "Listening…" : "🎙 Voice"}
                </button>
                <button type="submit" disabled={loading || !message.trim()}>
                  {loading ? "Thinking…" : "Send"}
                </button>
              </div>
              <div className="assistant-voice-controls">
                <label htmlFor="assistant-voice-language">Voice language</label>
                <select
                  id="assistant-voice-language"
                  value={voiceLanguage}
                  onChange={(event) => setVoiceLanguage(event.target.value)}
                >
                  <option value="en-IN">English (India)</option>
                  <option value="hi-IN">Hindi</option>
                </select>
                {voiceError && <p className="assistant-error" role="alert">{voiceError}</p>}
                {isSpeaking && (
                  <button type="button" onClick={stopSpeaking}>Stop spoken response</button>
                )}
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
