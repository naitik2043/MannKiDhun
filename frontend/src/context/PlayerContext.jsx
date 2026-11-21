import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import "../styles/player.css";

const STORAGE_KEY = "mannkidhun_player_v1";
const PlayerContext = createContext({
  queue: [],
  currentIndex: -1,
  currentSong: null,
  isPlaying: false,
  positionMs: 0,
  repeatMode: "off",
  error: "",
  playSong: () => false,
  playQueue: () => false,
  addToQueue: () => false,
  updateUpcomingTracks: () => false,
  nextTrack: () => {},
  previousTrack: () => {},
  togglePlayback: () => {},
  pausePlayback: () => {},
  seekTo: () => {},
  setRepeatMode: () => {},
});

let youtubeApiPromise;

function isPlayableTrack(track) {
  return Boolean(
    track &&
    typeof track === "object" &&
    track.provider === "youtube" &&
    typeof track.provider_track_id === "string" &&
    /^[\w-]{11}$/.test(track.provider_track_id),
  );
}

function normalizeTrack(track) {
  return {
    id: track.id,
    title: String(track.title || "Untitled track"),
    artist: String(track.artist || "Unknown artist"),
    album: track.album ? String(track.album) : "",
    provider: "youtube",
    provider_track_id: track.provider_track_id,
    provider_url: track.provider_url || `https://www.youtube.com/watch?v=${track.provider_track_id}`,
    thumbnail_url: track.thumbnail_url || "",
    duration: Number.isFinite(Number(track.duration)) ? Number(track.duration) : null,
  };
}

function readSavedState() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    const queue = Array.isArray(saved.queue)
      ? saved.queue.filter(isPlayableTrack).slice(0, 100).map(normalizeTrack)
      : [];
    const rawIndex = Number.isInteger(saved.currentIndex) ? saved.currentIndex : 0;
    return {
      queue,
      currentIndex: queue.length ? Math.max(0, Math.min(rawIndex, queue.length - 1)) : -1,
      positionMs: Number.isFinite(saved.positionMs) ? Math.max(0, saved.positionMs) : 0,
      repeatMode: ["off", "one", "all"].includes(saved.repeatMode) ? saved.repeatMode : "off",
    };
  } catch {
    return { queue: [], currentIndex: -1, positionMs: 0, repeatMode: "off" };
  }
}

function loadYouTubeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (youtubeApiPromise) return youtubeApiPromise;

  const promise = new Promise((resolve, reject) => {
    let settled = false;
    let script;
    let timeoutId;
    const previousCallback = window.onYouTubeIframeAPIReady;

    const cleanup = (removeFailedScript = false) => {
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
      script?.removeEventListener("error", handleScriptError);
      if (window.onYouTubeIframeAPIReady === handleReady) {
        window.onYouTubeIframeAPIReady = previousCallback;
      }
      if (removeFailedScript && script?.dataset.mannkidhunYoutubeApi === "true") {
        script.remove();
      }
    };

    const fail = (message) => {
      if (settled) return;
      settled = true;
      cleanup(true);
      if (youtubeApiPromise === promise) youtubeApiPromise = null;
      reject(new Error(message));
    };

    const handleScriptError = () => {
      fail("The music player could not load. Check your connection and try again.");
    };

    const handleReady = () => {
      if (typeof previousCallback === "function") {
        try {
          previousCallback();
        } catch (error) {
          console.error("A previous YouTube API callback failed:", error);
        }
      }
      if (!window.YT?.Player) {
        fail("The music player could not be initialized.");
        return;
      }
      if (settled) return;
      settled = true;
      cleanup(false);
      resolve(window.YT);
    };

    window.onYouTubeIframeAPIReady = handleReady;
    script = document.querySelector('script[data-mannkidhun-youtube-api="true"]');
    if (!script) {
      script = document.createElement("script");
      script.src = "https://www.youtube.com/iframe_api";
      script.async = true;
      script.dataset.mannkidhunYoutubeApi = "true";
    }
    script.addEventListener("error", handleScriptError, { once: true });
    timeoutId = window.setTimeout(() => {
      fail("The music player took too long to load. Check your connection and try again.");
    }, 15000);

    if (!script.isConnected) document.head.appendChild(script);
  });

  youtubeApiPromise = promise;
  return promise;
}
function formatTime(milliseconds) {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function usePlayer() {
  return useContext(PlayerContext);
}

export function PlayerProvider({ children }) {
  const initial = useRef(readSavedState()).current;
  const [queue, setQueue] = useState(initial.queue);
  const [currentIndex, setCurrentIndex] = useState(initial.currentIndex);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [positionMs, setPositionMs] = useState(initial.positionMs);
  const [repeatMode, setRepeatModeState] = useState(initial.repeatMode);
  const [error, setError] = useState("");
  const containerRef = useRef(null);
  const playerRef = useRef(null);
  const queueRef = useRef(queue);
  const indexRef = useRef(currentIndex);
  const repeatRef = useRef(repeatMode);
  const positionRef = useRef(positionMs);
  const autoplayRef = useRef(false);
  const lastLoadedTrackRef = useRef(null);
  const lastRecordedTrackRef = useRef(null);

  const currentSong = currentIndex >= 0 ? queue[currentIndex] || null : null;

  useEffect(() => {
    document.body.classList.toggle("has-global-player", Boolean(currentSong));
    return () => document.body.classList.remove("has-global-player");
  }, [currentSong]);

  useEffect(() => { queueRef.current = queue; }, [queue]);
  useEffect(() => { indexRef.current = currentIndex; }, [currentIndex]);
  useEffect(() => { repeatRef.current = repeatMode; }, [repeatMode]);
  useEffect(() => { positionRef.current = positionMs; }, [positionMs]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        queue,
        currentIndex,
        positionMs,
        repeatMode,
      }));
    } catch {
      // Browser storage may be disabled or full; playback remains usable.
    }
  }, [queue, currentIndex, positionMs, repeatMode]);

  const advanceTrack = useCallback((automatic = false) => {
    const currentQueue = queueRef.current;
    const current = indexRef.current;
    if (!currentQueue.length || current < 0) return;
    if (automatic && repeatRef.current === "one") {
      playerRef.current?.seekTo(0, true);
      playerRef.current?.playVideo();
      return;
    }
    let next = current + 1;
    if (next >= currentQueue.length) {
      if (repeatRef.current === "all") next = 0;
      else {
        setIsPlaying(false);
        return;
      }
    }
    autoplayRef.current = true;
    setPositionMs(0);
    setCurrentIndex(next);
  }, []);

  useEffect(() => {
    let disposed = false;
    loadYouTubeApi()
      .then((YT) => {
        if (disposed || !containerRef.current || playerRef.current) return;
        playerRef.current = new YT.Player(containerRef.current, {
          width: "240",
          height: "135",
          host: "https://www.youtube-nocookie.com",
          playerVars: {
            autoplay: 0,
            controls: 1,
            enablejsapi: 1,
            playsinline: 1,
            rel: 0,
            origin: window.location.origin,
          },
          events: {
            onReady: () => {
              if (!disposed) {
                setIsReady(true);
                setError("");
              }
            },
            onStateChange: (event) => {
              if (event.data === YT.PlayerState.PLAYING) {
                setIsPlaying(true);
                const song = queueRef.current[indexRef.current];
                if (song && song.id !== lastRecordedTrackRef.current && Number.isInteger(Number(song.id))) {
                  lastRecordedTrackRef.current = song.id;
                  fetch("/api/v1/users/me/listening-history", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      song_id: Number(song.id),
                      event_type: "play",
                      source: "global-player",
                    }),
                  }).catch(() => {});
                }
                const active = queueRef.current[indexRef.current];
                if (active && Number.isInteger(Number(active.id))) {
                  fetch("/api/v1/users/me/playback-state", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      current_song_id: Number(active.id),
                      position_ms: 0,
                      queue: queueRef.current.map((item) => Number(item.id)).filter((id) => Number.isInteger(id) && id > 0),
                      repeat_mode: repeatRef.current,
                    }),
                  }).catch(() => {});
                }
              } else if (
                event.data === YT.PlayerState.PAUSED ||
                event.data === YT.PlayerState.CUED
              ) {
                setIsPlaying(false);
              } else if (event.data === YT.PlayerState.ENDED) {
                const completed = queueRef.current[indexRef.current];
                if (completed && Number.isInteger(Number(completed.id))) {
                  fetch("/api/v1/users/me/listening-history", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      song_id: Number(completed.id),
                      event_type: "complete",
                      source: "global-player",
                      position_ms: positionRef.current,
                      duration_ms: Number(completed.duration || 0) * 1000,
                    }),
                  }).catch(() => {});
                }
                advanceTrack(true);
              }
            },
            onError: () => {
              setError("This track cannot be embedded by its provider. Skipping to the next track.");
              advanceTrack(false);
            },
          },
        });
      })
      .catch((loadError) => {
        if (!disposed) setError(loadError.message || "The player could not load.");
      });
    return () => {
      disposed = true;
      playerRef.current?.destroy();
      playerRef.current = null;
    };
  }, [advanceTrack]);

  useEffect(() => {
    if (!isReady || !currentSong || !playerRef.current) return;
    const videoId = currentSong.provider_track_id;
    if (!videoId || videoId === lastLoadedTrackRef.current) return;
    lastLoadedTrackRef.current = videoId;
    const shouldAutoplay = autoplayRef.current;
    autoplayRef.current = false;
    if (shouldAutoplay) {
      playerRef.current.loadVideoById({ videoId, startSeconds: 0 });
    } else {
      playerRef.current.cueVideoById({ videoId, startSeconds: Math.max(0, positionMs) / 1000 });
    }
  }, [isReady, currentSong, positionMs]);

  useEffect(() => {
    if (!isPlaying || !playerRef.current) return undefined;
    const timer = window.setInterval(() => {
      const seconds = playerRef.current?.getCurrentTime?.();
      if (Number.isFinite(seconds)) setPositionMs(Math.max(0, Math.round(seconds * 1000)));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [isPlaying]);

  const playQueue = useCallback((tracks, startIndex = 0, autoplay = true) => {
    const normalized = Array.isArray(tracks)
      ? tracks.filter(isPlayableTrack).map(normalizeTrack).slice(0, 100)
      : [];
    if (!normalized.length) {
      setError("There are no playable YouTube tracks in this queue.");
      return false;
    }
    const index = Math.max(0, Math.min(Number(startIndex) || 0, normalized.length - 1));
    queueRef.current = normalized;
    indexRef.current = index;
    autoplayRef.current = Boolean(autoplay);
    lastRecordedTrackRef.current = null;
    lastLoadedTrackRef.current = null;
    setQueue(normalized);
    setCurrentIndex(index);
    setPositionMs(0);
    setError("");
    return true;
  }, []);

  const playSong = useCallback((track) => {
    if (!isPlayableTrack(track)) {
      try {
        const providerUrl = new URL(track?.provider_url || "");
        if (providerUrl.protocol === "https:") window.open(providerUrl.toString(), "_blank", "noopener,noreferrer");
        else setError("This track has no supported secure playback link.");
      } catch {
        setError("This track has no supported playback link.");
      }
      return false;
    }
    const upcoming = queueRef.current.filter(
      (item) => String(item.id) !== String(track.id),
    );
    return playQueue([track, ...upcoming], 0);
  }, [playQueue]);

  const addToQueue = useCallback((track) => {
    if (!isPlayableTrack(track)) return false;
    const normalized = normalizeTrack(track);
    const current = queueRef.current;
    if (current.some((item) => String(item.id) === String(normalized.id))) return true;
    const next = [...current, normalized].slice(0, 100);
    queueRef.current = next;
    setQueue(next);
    return true;
  }, []);

  const updateUpcomingTracks = useCallback((tracks) => {
    const current = queueRef.current[indexRef.current] || null;
    if (!current) return playQueue(tracks);
    const normalized = Array.isArray(tracks)
      ? tracks.filter(isPlayableTrack).map(normalizeTrack).slice(0, 99)
      : [];
    const next = [current, ...normalized];
    queueRef.current = next;
    indexRef.current = 0;
    lastLoadedTrackRef.current = current.provider_track_id;
    setQueue(next);
    setCurrentIndex(0);
    return true;
  }, [playQueue]);

  const nextTrack = useCallback(() => advanceTrack(false), [advanceTrack]);
  const previousTrack = useCallback(() => {
    if (positionRef.current > 3000) {
      playerRef.current?.seekTo(0, true);
      setPositionMs(0);
      return;
    }
    const previous = Math.max(0, indexRef.current - 1);
    if (previous === indexRef.current) {
      playerRef.current?.seekTo(0, true);
      setPositionMs(0);
      return;
    }
    autoplayRef.current = true;
    lastLoadedTrackRef.current = null;
    setPositionMs(0);
    setCurrentIndex(previous);
  }, []);
  const togglePlayback = useCallback(() => {
    if (!currentSong) return;
    if (isPlaying) playerRef.current?.pauseVideo();
    else playerRef.current?.playVideo();
  }, [currentSong, isPlaying]);
  const pausePlayback = useCallback(() => playerRef.current?.pauseVideo(), []);
  const seekTo = useCallback((milliseconds) => {
    const safe = Number.isFinite(Number(milliseconds)) ? Math.max(0, Number(milliseconds)) : 0;
    playerRef.current?.seekTo(safe / 1000, true);
    setPositionMs(safe);
  }, []);
  const setRepeatMode = useCallback((value) => {
    if (["off", "one", "all"].includes(value)) setRepeatModeState(value);
  }, []);

  useEffect(() => {
    if (!isPlaying) return undefined;
    const timer = window.setInterval(() => {
      const song = queueRef.current[indexRef.current];
      if (!song || !Number.isInteger(Number(song.id))) return;
      fetch("/api/v1/users/me/playback-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_song_id: Number(song.id),
          position_ms: positionRef.current,
          queue: queueRef.current.map((item) => Number(item.id)).filter((id) => Number.isInteger(id) && id > 0),
          repeat_mode: repeatRef.current,
        }),
      }).catch(() => {});
    }, 10000);
    return () => window.clearInterval(timer);
  }, [isPlaying]);

  useEffect(() => {
    if (!("mediaSession" in navigator) || typeof window.MediaMetadata !== "function") return undefined;
    if (currentSong) {
      navigator.mediaSession.metadata = new window.MediaMetadata({
        title: currentSong.title,
        artist: currentSong.artist,
        album: currentSong.album || "MannKiDhun",
        artwork: currentSong.thumbnail_url
          ? [{ src: currentSong.thumbnail_url, sizes: "512x512", type: "image/jpeg" }]
          : [],
      });
      navigator.mediaSession.setActionHandler("play", () => playerRef.current?.playVideo());
      navigator.mediaSession.setActionHandler("pause", () => playerRef.current?.pauseVideo());
      navigator.mediaSession.setActionHandler("previoustrack", () => previousTrack());
      navigator.mediaSession.setActionHandler("nexttrack", () => nextTrack());
      navigator.mediaSession.setActionHandler("seekto", (event) => {
        if (Number.isFinite(event.seekTime)) playerRef.current?.seekTo(event.seekTime, true);
      });
    } else {
      navigator.mediaSession.metadata = null;
    }
    return () => {
      for (const action of ["play", "pause", "previoustrack", "nexttrack", "seekto"]) {
        try { navigator.mediaSession.setActionHandler(action, null); } catch { /* Browser support varies. */ }
      }
    };
  }, [currentSong, previousTrack, nextTrack]);

  const value = useMemo(() => ({
    queue, currentIndex, currentSong, isPlaying, isReady, positionMs, repeatMode, error,
    playSong, playQueue, addToQueue, updateUpcomingTracks,
    nextTrack, previousTrack, togglePlayback, pausePlayback, seekTo, setRepeatMode,
  }), [
    queue, currentIndex, currentSong, isPlaying, isReady, positionMs, repeatMode, error,
    playSong, playQueue, addToQueue, updateUpcomingTracks,
    nextTrack, previousTrack, togglePlayback, pausePlayback, seekTo, setRepeatMode,
  ]);

  return (
    <PlayerContext.Provider value={value}>
      {children}
      <GlobalPlayerBar containerRef={containerRef} />
    </PlayerContext.Provider>
  );
}

function GlobalPlayerBar({ containerRef }) {
  const player = usePlayer();
  const { currentSong, isPlaying, positionMs, repeatMode, error } = player;
  const hidden = !currentSong;
  const durationMs = currentSong && Number.isFinite(currentSong.duration) ? currentSong.duration * 1000 : 0;
  const progressMax = durationMs || Math.max(positionMs, 60000);
  return (
    <aside
      className={`global-player ${hidden ? "global-player-empty" : ""}`}
      aria-label="MannKiDhun music player"
      aria-hidden={hidden}
    >
      <div className="global-player-video">
        <div ref={containerRef} />
      </div>
      <div className="global-player-details">
        <p className="global-player-kicker">NOW PLAYING</p>
        <strong>{currentSong?.title || "Choose a track"}</strong>
        <span>{currentSong?.artist || "Your player is ready"}</span>
        <div className="global-player-progress">
          <input
            aria-label="Seek through current track"
            type="range"
            min="0"
            max={progressMax}
            value={Math.min(positionMs, progressMax)}
            onChange={(event) => player.seekTo(Number(event.target.value))}
            disabled={!currentSong}
          />
          <span>{formatTime(positionMs)}{durationMs ? ` / ${formatTime(durationMs)}` : ""}</span>
        </div>
        {error && <p className="global-player-error" role="alert">{error}</p>}
      </div>
      <div className="global-player-actions">
        <button type="button" onClick={player.previousTrack} disabled={!currentSong} aria-label="Previous track">|◀</button>
        <button type="button" onClick={player.togglePlayback} disabled={!currentSong} aria-label={isPlaying ? "Pause playback" : "Resume playback"}>
          {isPlaying ? "Pause" : "Play"}
        </button>
        <button type="button" onClick={player.nextTrack} disabled={!currentSong} aria-label="Next track">▶|</button>
        <select aria-label="Repeat mode" value={repeatMode} onChange={(event) => player.setRepeatMode(event.target.value)}>
          <option value="off">Repeat off</option>
          <option value="one">Repeat one</option>
          <option value="all">Repeat queue</option>
        </select>
      </div>
    </aside>
  );
}

