import { useEffect, useRef, useState } from "react";
import Brand from "./Brand.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

function ProfileAvatar({ user }) {
  const initials = user.name
    ?.trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "M";

  return (
    <span className="profile-avatar-small" aria-hidden="true">
      {user.profile_image ? <img src={user.profile_image} alt="" /> : initials}
    </span>
  );
}

function Header({ theme, onToggleTheme, user, onSignOut }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [signOutError, setSignOutError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const profileRef = useRef(null);
  const profileButtonRef = useRef(null);
  const menuButtonRef = useRef(null);
  const navigationRef = useRef(null);
  const [currentHash, setCurrentHash] = useState(window.location.hash);

  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const isHome = path === "/";
  const homeHref = user ? "/dashboard" : "/";
  const assistantHref = user ? "/assistant" : "/signin?next=%2Fassistant";
  useEffect(() => {
    function updateHash() {
      setCurrentHash(window.location.hash);
    }

    window.addEventListener("hashchange", updateHash);
    return () => window.removeEventListener("hashchange", updateHash);
  }, []);

  const navigation = user
    ? [
        { label: "Home", href: "/dashboard", active: path === "/dashboard" },
        { label: "Discover", href: "/app", active: path === "/app" || path === "/mood-check" },
        {
          label: "Playlists",
          href: "/assistant#assistant-playlists",
          active: path === "/assistant" && currentHash === "#assistant-playlists",
        },
        { label: "Music Assistant", href: "/assistant", active: path === "/assistant" && !currentHash },
      ]
    : [
        { label: "Home", href: "/", active: isHome && !currentHash },
        { label: "Discover Music", href: "/signup", active: path === "/signup" },
        { label: "Features", href: "/#features", active: isHome && currentHash === "#features" },
        { label: "About", href: "/#about-us", active: isHome && currentHash === "#about-us" },
      ];

  function closeMenus() {
    setMenuOpen(false);
    setProfileOpen(false);
  }

  useEffect(() => {
    if (!menuOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    navigationRef.current?.querySelector("a")?.focus();

    function closeOnResize() {
      if (window.innerWidth > 900) setMenuOpen(false);
    }

    window.addEventListener("resize", closeOnResize);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("resize", closeOnResize);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (!profileOpen && !menuOpen) return undefined;

    function handlePointerDown(event) {
      if (profileOpen && !profileRef.current?.contains(event.target)) {
        setProfileOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key !== "Escape") return;
      if (profileOpen) {
        setProfileOpen(false);
        profileButtonRef.current?.focus();
      }
      if (menuOpen) setMenuOpen(false);
      if (menuOpen) menuButtonRef.current?.focus();
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen, profileOpen]);

  async function handleSignOut() {
    setSignOutError("");
    setSigningOut(true);
    try {
      if (onSignOut) {
        await onSignOut();
      } else {
        const response = await fetch("/api/auth/logout", { method: "POST" });
        if (!response.ok) throw new Error("Could not sign out. Please try again.");
        window.location.assign("/");
      }
    } catch (error) {
      setSignOutError(error.message || "Could not sign out. Please try again.");
      setSigningOut(false);
    }
  }

  return (
    <>
      {menuOpen && (
        <button
          className="mobile-nav-backdrop"
          type="button"
          aria-label="Close navigation menu"
          onClick={closeMenus}
        />
      )}
      <header className="site-header">
        <Brand href={homeHref} />
        <nav
          id="primary-navigation"
          ref={navigationRef}
          className={`header-nav ${menuOpen ? "header-nav-open" : ""}`}
          aria-label="Main navigation"
        >
          {navigation.map(({ label, href, active }) => (
            <a
              key={label}
              href={href}
              aria-current={active ? "page" : undefined}
              onClick={closeMenus}
            >
              {label}
            </a>
          ))}
          {user && (
            <a className="mobile-profile-nav-link" href="/profile" onClick={closeMenus}>
              My Profile
            </a>
          )}
          {!user && (
            <a className="mobile-login-link" href="/signin" onClick={closeMenus}>
              Log in
            </a>
          )}
          <div className="mobile-nav-utilities">
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            {user && (
              <button
                className="header-signout"
                type="button"
                onClick={handleSignOut}
                disabled={signingOut}
              >
                {signingOut ? "Signing out…" : "Log out"}
              </button>
            )}
          </div>
          {!user && (
            <a className="nav-cta mobile-nav-cta" href="/signup" onClick={closeMenus}>
              Get started <span aria-hidden="true">→</span>
            </a>
          )}
        </nav>

        <div className="header-actions">
          <a
            className="header-search"
            href={assistantHref}
            aria-label={user ? "Search music with the Music Assistant" : "Sign in to search music"}
            title={user ? "Search music with the Music Assistant" : "Sign in to search music"}
          >
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="10.8" cy="10.8" r="6.8" stroke="currentColor" strokeWidth="1.8" />
              <path d="m16 16 4.2 4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </a>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          {user ? (
            <>
              <div className="profile-menu" ref={profileRef}>
                <button
                  ref={profileButtonRef}
                  className="profile-menu-trigger"
                  type="button"
                  aria-expanded={profileOpen}
                  aria-label={`Open profile menu for ${user.name}`}
                  onClick={() => setProfileOpen((open) => !open)}
                >
                  <ProfileAvatar user={user} />
                  <span className="profile-trigger-name">{user.name?.split(/\s+/)[0]}</span>
                  <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                {profileOpen && (
                  <nav className="profile-dropdown" id="profile-dropdown" aria-label="Profile actions">
                    <div className="profile-dropdown-heading">
                      <strong>{user.name}</strong>
                      <span>{user.email}</span>
                    </div>
                    <a href="/profile" onClick={closeMenus}>My Profile</a>
                    <a href="/profile#account-settings" onClick={closeMenus}>Account Settings</a>
                    <button
                      type="button"
                      onClick={handleSignOut}
                      disabled={signingOut}
                    >
                      {signingOut ? "Signing out…" : "Log out"}
                    </button>
                  </nav>
                )}
              </div>
              <a className="mobile-profile-link" href="/profile" aria-label="My profile">
                <ProfileAvatar user={user} />
              </a>
            </>
          ) : (
            <>
              <a className="header-login" href="/signin">Log in</a>
              <a className="nav-cta header-cta" href="/signup">
                Get started <span aria-hidden="true">→</span>
              </a>
            </>
          )}
          <button
            ref={menuButtonRef}
            className={`mobile-menu-toggle ${menuOpen ? "mobile-menu-toggle-open" : ""}`}
            type="button"
            aria-expanded={menuOpen}
            aria-controls="primary-navigation"
            aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
        {signOutError && <p className="header-error" role="alert">{signOutError}</p>}
      </header>
    </>
  );
}

export default Header;
