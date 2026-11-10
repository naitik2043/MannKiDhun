import { useState } from "react";
import Brand from "./Brand.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

function AuthPage({ mode, theme, onToggleTheme }) {
  const isSignup = mode === "signup";
  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const payload = isSignup
        ? {
            full_name: fullName,
            username,
            email,
            password,
            confirm_password: confirmPassword,
            accepted_terms: acceptedTerms,
            remember_me: rememberMe,
          }
        : {
            email_or_username: email,
            password,
            remember_me: rememberMe,
          };

      const response = await fetch(
        isSignup ? "/api/auth/register" : "/api/auth/login",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(result?.error || "We couldn’t complete that request.");
      }
      const requestedPath = new URLSearchParams(window.location.search).get("next");
      const returnPath =
        requestedPath?.startsWith("/") &&
        !requestedPath.startsWith("//") &&
        !requestedPath.includes("\\")
          ? requestedPath
          : "/dashboard";
      window.location.assign(returnPath);
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "We couldn’t reach MannKiDhun. Check your connection and try again."
          : requestError.message,
      );
      setIsSubmitting(false);
    }
  }

  return (
    <div className="app-shell auth-shell flex min-h-screen flex-col px-[clamp(20px,7vw,90px)] max-[480px]:px-[17px]">
      <div className="auth-topbar flex min-h-[82px] items-center justify-between border-b border-[rgb(44_37_71_/_8%)] max-[480px]:min-h-[70px]">
        <Brand />
        <div className="auth-topbar-actions flex items-center gap-5 max-[480px]:gap-[11px]">
          <a href="/">Back to home</a>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
      <main className="auth-main grid flex-1 place-items-center py-[42px]">
        <section
          className="auth-card w-[min(100%,450px)] p-[clamp(26px,5vw,42px)]"
          aria-labelledby="auth-title"
        >
          <div className="auth-card-mark" aria-hidden="true">♫</div>
          <p className="section-eyebrow">
            {isSignup ? "YOUR OWN LITTLE SPACE" : "WELCOME BACK"}
          </p>
          <h1 id="auth-title">
            {isSignup ? "Create your account" : "Sign in to MannKiDhun"}
          </h1>
          <p className="auth-description">
            {isSignup
              ? "Create an account to explore music and save your playlists."
              : "Sign in to continue to your music, playlists, and account."}
          </p>
          <form className="auth-form" onSubmit={handleSubmit}>
            {isSignup && (
              <>
                <label>
                  Full name
                  <input
                    type="text"
                    name="full_name"
                    autoComplete="name"
                    maxLength={64}
                    value={fullName}
                    onChange={(event) => setFullName(event.target.value)}
                    placeholder="What should we call you?"
                    required
                  />
                </label>
                <label>
                  Username
                  <input
                    type="text"
                    name="username"
                    autoComplete="username"
                    minLength={3}
                    maxLength={32}
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="your_name_123"
                    required
                  />
                </label>
              </>
            )}
            <label>
              {isSignup ? "Email address" : "Email or username"}
              <input
                type="text"
                name="email_or_username"
                autoComplete={isSignup ? "email" : "username"}
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder={isSignup ? "you@example.com" : "yourname or you@example.com"}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                name="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                minLength={isSignup ? 8 : undefined}
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={isSignup ? "At least 8 characters" : "Your password"}
                required
              />
            </label>
            {isSignup && (
              <label>
                Confirm password
                <input
                  type="password"
                  name="confirm_password"
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={128}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Re-enter your password"
                  required
                />
              </label>
            )}
            {isSignup && (
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={acceptedTerms}
                  onChange={(event) => setAcceptedTerms(event.target.checked)}
                />
                <span>I agree to the terms and privacy policy.</span>
              </label>
            )}
            {!isSignup && (
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                />
                <span>Remember me</span>
              </label>
            )}
            {error && (
              <p className="auth-error" role="alert">
                {error}
              </p>
            )}
            <button className="auth-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? "Please wait…"
                : isSignup
                  ? "Create account"
                  : "Sign in"}
              {!isSubmitting && <span aria-hidden="true">→</span>}
            </button>
          </form>
          <p className="auth-switch">
            {isSignup ? "Already have an account?" : "New to MannKiDhun?"}{" "}
            <a href={isSignup ? "/signin" : "/signup"}>
              {isSignup ? "Sign in" : "Create an account"}
            </a>
          </p>
          <p className="auth-privacy">
            Your password is securely hashed before it’s stored. We never store your
            camera frames.
          </p>
        </section>
      </main>
      <footer className="auth-footer">
        © {new Date().getFullYear()} MannKiDhun · Every Feeling Has a Tune.
      </footer>
    </div>
  );
}

export default AuthPage;
