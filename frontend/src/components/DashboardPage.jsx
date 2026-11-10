import Header from "./Header.jsx";
import SiteFooter from "./SiteFooter.jsx";

function DashboardPage({ user, theme, toggleTheme }) {
  const firstName = user?.name?.trim().split(/\s+/)[0] || "there";

  async function signOut() {
    const response = await fetch("/api/auth/logout", { method: "POST" });
    if (!response.ok) throw new Error("Could not sign out. Please try again.");
    window.location.assign("/");
  }

  return (
    <div className="app-shell">
      <div className="page-shell mx-auto min-h-screen w-[min(1120px,calc(100%-40px))]">
        <Header
          theme={theme}
          onToggleTheme={toggleTheme}
          user={user}
          onSignOut={signOut}
        />
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
                Either way, the result is only a suggestion—you decide what
                feels right.
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
                <p className="section-eyebrow">YOUR LIBRARY</p>
                <h2 id="recent-title">Recently played</h2>
              </div>
            </div>
            <div className="dashboard-empty">
              <span className="dashboard-empty-icon" aria-hidden="true">♫</span>
              <div>
                <h3>Your listening history starts here</h3>
                <p>Tracks played from the assistant aren’t added to listening history yet.</p>
              </div>
              <a href="/assistant">Explore the catalogue <span aria-hidden="true">→</span></a>
            </div>
          </section>

          <section className="dashboard-section" aria-labelledby="playlists-title">
            <div className="dashboard-section-heading">
              <div>
                <p className="section-eyebrow">YOUR COLLECTIONS</p>
                <h2 id="playlists-title">Create a playlist</h2>
              </div>
            </div>
            <div className="dashboard-empty">
              <span className="dashboard-empty-icon" aria-hidden="true">♫</span>
              <div>
                <h3>Keep the songs you love together</h3>
                <p>Create a playlist and add tracks from the Music Assistant.</p>
              </div>
              <a href="/assistant#assistant-playlists">Create a playlist <span aria-hidden="true">→</span></a>
            </div>
          </section>
        </main>
        <SiteFooter user={user} />
      </div>
    </div>
  );
}

export default DashboardPage;
