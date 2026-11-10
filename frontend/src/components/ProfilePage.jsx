import { useRef, useState } from "react";
import Header from "./Header.jsx";
import SiteFooter from "./SiteFooter.jsx";

function ProfilePage({ user, theme, toggleTheme }) {
  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email);
  const [profileImage, setProfileImage] = useState(user.profile_image || "");
  const [savedProfile, setSavedProfile] = useState({
    name: user.name,
    email: user.email,
  });
  const [isAvatarBusy, setIsAvatarBusy] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const avatarInputRef = useRef(null);
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
  const isBusy = isAvatarBusy || isSaving;
  const hasUnsavedChanges =
    name.trim() !== savedProfile.name ||
    email.trim() !== savedProfile.email ||
    newPassword.length > 0;

  function updateField(setField, value) {
    setField(value);
    setError("");
    setNotice("");
  }

  async function saveProfile(event) {
    event.preventDefault();
    if (isBusy || !hasUnsavedChanges) return;
    setError("");
    setNotice("");
    setIsSaving(true);

    try {
      const response = await fetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          email,
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(result?.error || "We couldn’t save your profile.");
      }

      setName(result.user.name);
      setEmail(result.user.email);
      setProfileImage(result.user.profile_image || "");
      setSavedProfile({ name: result.user.name, email: result.user.email });
      setCurrentPassword("");
      setNewPassword("");
      setNotice("Your profile has been updated.");
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "We couldn’t reach MannKiDhun. Check your connection and try again."
          : requestError.message,
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function updateAvatar(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    setNotice("");

    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Choose a JPEG, PNG, or WebP image.");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError("Profile photos must be 2 MB or smaller.");
      return;
    }

    const formData = new FormData();
    formData.append("avatar", file);
    setIsAvatarBusy(true);
    try {
      const response = await fetch("/api/profile/avatar", {
        method: "POST",
        body: formData,
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(result?.error || "We couldn’t save your profile photo.");
      }
      setProfileImage(result.user.profile_image || "");
      setNotice("Your profile photo has been updated.");
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "We couldn’t reach MannKiDhun. Check your connection and try again."
          : requestError.message,
      );
    } finally {
      setIsAvatarBusy(false);
    }
  }

  async function removeAvatar() {
    setError("");
    setNotice("");
    setIsAvatarBusy(true);
    try {
      const response = await fetch("/api/profile/avatar", { method: "DELETE" });
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(result?.error || "We couldn’t remove your profile photo.");
      }
      setProfileImage("");
      setNotice("Your profile photo has been removed.");
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "We couldn’t reach MannKiDhun. Check your connection and try again."
          : requestError.message,
      );
    } finally {
      setIsAvatarBusy(false);
    }
  }

  function resetForm() {
    setName(savedProfile.name);
    setEmail(savedProfile.email);
    setCurrentPassword("");
    setNewPassword("");
    setError("");
    setNotice("");
  }

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
          user={{ ...user, name, email, profile_image: profileImage }}
          onSignOut={signOut}
        />
        <main className="profile-main min-h-[calc(100vh-190px)] pt-[clamp(35px,6vw,65px)] pb-[52px] max-[480px]:pt-[35px]">
          <div className="profile-page-heading">
            <p className="section-eyebrow">YOUR ACCOUNT</p>
            <h1 className="mb-0 mt-[10px] font-display text-[clamp(28px,4vw,36px)] font-extrabold tracking-[-1.5px]">
              Profile settings
            </h1>
            <p className="mb-0 mt-[9px] text-[13px] leading-[1.7] text-subtle">
              Manage your personal details and keep your account up to date.
            </p>
          </div>
          <div
            className="profile-layout mt-[30px] grid grid-cols-[minmax(230px,0.7fr)_minmax(0,1.6fr)] items-start gap-5 max-[760px]:grid-cols-1"
            aria-busy={isBusy}
          >
            <aside className="profile-summary flex min-h-[290px] flex-col items-start p-[25px] max-[760px]:min-h-0">
              <div className="profile-avatar">
                {profileImage ? (
                  <img src={profileImage} alt={`${name || "Your"} profile`} />
                ) : (
                  <span aria-hidden="true">{initials || "M"}</span>
                )}
              </div>
              <h2>{name}</h2>
              <p>{email}</p>
              <div className="profile-photo-actions">
                <input
                  ref={avatarInputRef}
                  className="profile-avatar-input"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  aria-label="Choose a profile photo"
                  tabIndex={-1}
                  onChange={updateAvatar}
                  disabled={isBusy}
                />
                <button
                  className="profile-photo-button"
                  type="button"
                  onClick={() => avatarInputRef.current?.click()}
                  disabled={isBusy}
                >
                  {isAvatarBusy ? "Updating photo…" : profileImage ? "Change photo" : "Add a photo"}
                </button>
                {profileImage && (
                  <button
                    className="profile-photo-remove"
                    type="button"
                    onClick={removeAvatar}
                    disabled={isBusy}
                  >
                    Remove
                  </button>
                )}
              </div>
              <p className="profile-photo-hint">JPEG, PNG, or WebP · up to 2 MB</p>
              <span className="profile-member-badge">
                <span aria-hidden="true">✦</span> MannKiDhun member
              </span>
              <div className="profile-summary-divider" />
              <p className="profile-summary-note">
                Your account details are private. Camera frames used for a
                mood check aren’t saved to your profile.
              </p>
              <a className="profile-back-link" href="/dashboard">
                <span aria-hidden="true">←</span> Back to your dashboard
              </a>
            </aside>

            <section
              className="profile-settings-card p-[clamp(22px,4vw,33px)]"
              aria-labelledby="profile-details-title"
            >
              <div className="profile-card-heading">
                <div>
                  <h2 id="profile-details-title">Personal information</h2>
                  <p>Update your name and the email address on your account.</p>
                </div>
                <span className="profile-edit-icon" aria-hidden="true">✎</span>
              </div>
              <form
                id="account-settings"
                className="profile-form"
                onSubmit={saveProfile}
                aria-busy={isSaving}
              >
                <div className="profile-form-row">
                  <label>
                    Full name
                    <input
                      type="text"
                      name="name"
                      autoComplete="name"
                      maxLength={64}
                      value={name}
                      onChange={(event) => updateField(setName, event.target.value)}
                      disabled={isBusy}
                      required
                    />
                  </label>
                  <label>
                    Email address
                    <input
                      type="email"
                      name="email"
                      autoComplete="email"
                      maxLength={254}
                      value={email}
                      onChange={(event) => updateField(setEmail, event.target.value)}
                      disabled={isBusy}
                      required
                    />
                  </label>
                </div>

                <div className="profile-password-section">
                  <div className="profile-password-heading">
                    <h3>Security</h3>
                    <p>Confirm your current password to save changes.</p>
                  </div>
                  <div className="profile-form-row">
                    <label>
                      Current password
                      <input
                        type="password"
                        name="current-password"
                        autoComplete="current-password"
                        maxLength={128}
                        value={currentPassword}
                        onChange={(event) =>
                          updateField(setCurrentPassword, event.target.value)
                        }
                        disabled={isBusy}
                        required
                      />
                    </label>
                    <label>
                      New password <span className="profile-optional">(optional)</span>
                      <input
                        type="password"
                        name="new-password"
                        autoComplete="new-password"
                        minLength={8}
                        maxLength={128}
                        value={newPassword}
                        onChange={(event) =>
                          updateField(setNewPassword, event.target.value)
                        }
                        disabled={isBusy}
                        placeholder="At least 8 characters"
                      />
                    </label>
                  </div>
                </div>

                {error && <p className="auth-error" role="alert">{error}</p>}
                {notice && <p className="profile-success" role="status">{notice}</p>}
                <div className="profile-form-actions">
                  <button
                    className="profile-cancel-button"
                    type="button"
                    onClick={resetForm}
                    disabled={isBusy}
                  >
                    Cancel
                  </button>
                  <button
                    className="auth-submit profile-save-button"
                    type="submit"
                    disabled={isBusy || !hasUnsavedChanges}
                  >
                    {isSaving
                      ? "Saving changes…"
                      : hasUnsavedChanges
                        ? "Save changes"
                        : "Nothing to save"}
                    {!isSaving && hasUnsavedChanges && (
                      <span aria-hidden="true">→</span>
                    )}
                  </button>
                </div>
              </form>
            </section>
          </div>
        </main>
        <SiteFooter user={user} />
      </div>
    </div>
  );
}

export default ProfilePage;
