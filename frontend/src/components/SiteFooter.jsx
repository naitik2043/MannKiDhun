import Brand from "./Brand.jsx";

function SiteFooter({ user = null }) {
  const isHome = window.location.pathname === "/";
  const homeHref = (section) => `${isHome ? "" : "/"}#${section}`;
  const discoverHref = user ? "/app" : "/signup";
  const assistantHref = user ? "/assistant" : "/signin?next=%2Fassistant";

  return (
    <footer className={`site-footer ${user ? "footer-authenticated" : "footer-public"}`}>
      <div className="footer-main">
        <section className="footer-brand-column" aria-label="About MannKiDhun">
          <Brand footer href={user ? "/dashboard" : "/"} />
          <p className="footer-tagline">Every Feeling Has a Tune.</p>
          <p className="footer-description">
            Choose a vibe, explore a music suggestion, and decide what feels
            right to play. Expression check-ins are always optional.
          </p>
        </section>

        <nav className="footer-link-column" aria-label="Explore">
          <h2>Explore</h2>
          <a href={user ? "/dashboard" : "/"}>Home</a>
          <a href={discoverHref}>Discover Music</a>
          <a href={homeHref("features")}>Features</a>
          <a href={assistantHref}>Music Assistant</a>
          <a href={homeHref("about-us")}>About Us</a>
        </nav>

        {user && (
          <nav className="footer-link-column" aria-label="Your music">
            <h2>Your Music</h2>
            <a href="/dashboard">Your Dashboard</a>
            <a href="/assistant#assistant-playlists">Playlists</a>
            <a href="/profile">My Profile</a>
          </nav>
        )}

        <nav className="footer-link-column" aria-label="Support">
          <h2>Support</h2>
          <a href={homeHref("faq")}>Frequently Asked Questions</a>
          <a href={homeHref("privacy-note")}>Privacy Information</a>
        </nav>

        <nav className="footer-link-column" aria-label="Connect">
          <h2>Connect</h2>
          <a href="https://www.linkedin.com/in/naitik2043/" target="_blank" rel="noopener noreferrer">
            LinkedIn <span aria-hidden="true">↗</span>
          </a>
          <a href="https://github.com/naitik2043" target="_blank" rel="noopener noreferrer">
            GitHub <span aria-hidden="true">↗</span>
          </a>
        </nav>
      </div>

      <div className="footer-bottom">
        <p>© {new Date().getFullYear()} MannKiDhun. All rights reserved.</p>
        <a href={homeHref("privacy-note")}>Privacy</a>
        <a href={homeHref("faq")}>FAQs</a>
        <button
          type="button"
          className="footer-back-to-top"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          Back to top <span aria-hidden="true">↑</span>
        </button>
      </div>
    </footer>
  );
}

export default SiteFooter;
