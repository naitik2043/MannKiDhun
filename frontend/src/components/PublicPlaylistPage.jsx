import { useEffect, useState } from "react";
import Header from "./Header.jsx";
import SiteFooter from "./SiteFooter.jsx";

function PublicPlaylistPage({ playlistId, theme, toggleTheme }) {
  const [playlist, setPlaylist] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`/api/v1/public/playlists/${playlistId}`)
      .then(async (response) => {
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(result?.error || "This shared playlist is unavailable.");
        if (active) setPlaylist(result.playlist);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || "This shared playlist is unavailable.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [playlistId]);

  return (
    <div className="app-shell">
      <div className="page-shell mx-auto min-h-screen w-[min(1120px,calc(100%-40px))]">
        <Header theme={theme} onToggleTheme={toggleTheme} />
        <main className="dashboard-main grid gap-6 pt-[38px] pb-[14px]">
          <section className="dashboard-welcome">
            <p className="section-eyebrow">SHARED PLAYLIST</p>
            <h1>{playlist?.name || "Discover a playlist"}</h1>
            {playlist && <p>Curated by {playlist.owner_name || "a MannKiDhun listener"}</p>}
          </section>
          {loading ? (
            <p role="status">Loading shared playlist…</p>
          ) : error ? (
            <p className="assistant-error" role="alert">{error}</p>
          ) : (
            <section className="dashboard-section" aria-label="Shared playlist tracks">
              <p>{playlist.description || "A collection shared with the MannKiDhun community."}</p>
              {playlist.tracks?.length ? (
                <div className="grid gap-3">
                  {playlist.tracks.map((track) => (
                    <article className="dashboard-empty flex items-center gap-4" key={track.id}>
                      <img
                        src={track.thumbnail_url || "/mannkidhun.svg"}
                        alt=""
                        width="64"
                        height="64"
                        loading="lazy"
                      />
                      <div className="min-w-0">
                        <h3 className="truncate">{track.title}</h3>
                        <p>{track.artist || "Unknown artist"}{track.language ? " · " + track.language : ""}</p>
                      </div>
                      {track.provider_url && (
                        <a className="dashboard-text-link ml-auto shrink-0" href={track.provider_url} target="_blank" rel="noopener noreferrer">
                          Open track ↗
                        </a>
                      )}
                    </article>
                  ))}
                </div>
              ) : (
                <div className="dashboard-empty">
                  <h3>This playlist is waiting for its first track.</h3>
                </div>
              )}
              <p className="text-xs text-subtle">
                This is a read-only public playlist. Only its owner can edit the tracks or sharing settings.
              </p>
            </section>
          )}
          <section className="dashboard-empty">
            <h2>Make your own music collection</h2>
            <p>Sign in to create playlists, save tracks, and discover music by mood.</p>
            <a className="nav-cta" href="/signup">Join MannKiDhun →</a>
          </section>
        </main>
        <SiteFooter />
      </div>
    </div>
  );
}

export default PublicPlaylistPage;
