import { useEffect, useState } from "react";
import Header from "./Header.jsx";
import SiteFooter from "./SiteFooter.jsx";

function CommunityPage({ theme, toggleTheme }) {
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/v1/public/playlists")
      .then(async (response) => {
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(result?.error || "Could not load community playlists.");
        if (active) setPlaylists(Array.isArray(result?.playlists) ? result.playlists : []);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || "Could not load community playlists.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  return (
    <div className="app-shell">
      <div className="page-shell mx-auto min-h-screen w-[min(1120px,calc(100%-40px))]">
        <Header theme={theme} onToggleTheme={toggleTheme} />
        <main className="dashboard-main grid gap-7 pt-[38px] pb-[14px]">
          <section className="dashboard-welcome">
            <p className="section-eyebrow">MANNKIDHUN COMMUNITY</p>
            <h1>Playlists shared by listeners.</h1>
            <p>Discover public music collections. Shared playlists are read-only; their owners keep control of their tracks.</p>
          </section>
          {loading ? (
            <p role="status">Loading public playlists…</p>
          ) : error ? (
            <p className="assistant-error" role="alert">{error}</p>
          ) : playlists.length ? (
            <section className="grid gap-3" aria-label="Public playlists">
              {playlists.map((playlist) => (
                <article className="dashboard-empty flex items-center justify-between gap-4" key={playlist.id}>
                  <div className="min-w-0">
                    <h2 className="truncate">{playlist.name}</h2>
                    <p>Shared by {playlist.owner_name} · {playlist.track_count} tracks</p>
                    {playlist.description && <p>{playlist.description}</p>}
                  </div>
                  <a className="dashboard-text-link shrink-0" href={`/playlists/${playlist.id}`}>
                    Open playlist →
                  </a>
                </article>
              ))}
            </section>
          ) : (
            <div className="dashboard-empty">
              <span className="dashboard-empty-icon" aria-hidden="true">♫</span>
              <div>
                <h2>No public playlists yet</h2>
                <p>When listeners share a playlist, it will appear here.</p>
              </div>
              <a className="dashboard-text-link" href="/signup">Create your own →</a>
            </div>
          )}
        </main>
        <SiteFooter />
      </div>
    </div>
  );
}

export default CommunityPage;
