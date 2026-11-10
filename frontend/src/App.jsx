import { useEffect, useRef, useState } from "react";
import AboutSection from "./components/AboutSection.jsx";
import AssistantPage from "./components/AssistantPage.jsx";
import AuthPage from "./components/AuthPage.jsx";
import DashboardPage from "./components/DashboardPage.jsx";
import FaqSection from "./components/FaqSection.jsx";
import Header from "./components/Header.jsx";
import HomePage from "./components/HomePage.jsx";
import HowItWorks from "./components/HowItWorks.jsx";
import IntroSection from "./components/IntroSection.jsx";
import MoodDetectionCard from "./components/MoodDetectionCard.jsx";
import MusicRecommendationCard from "./components/MusicRecommendationCard.jsx";
import ProfilePage from "./components/ProfilePage.jsx";
import SiteFooter from "./components/SiteFooter.jsx";
import { useCamera } from "./hooks/useCamera.js";
import { useMoodDetection } from "./hooks/useMoodDetection.js";
import { useTheme } from "./hooks/useTheme.js";

function MoodExperience({ user, theme, toggleTheme }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const { cameraState, cameraError, retryCamera } = useCamera(videoRef, cameraEnabled);
  const {
    mood,
    consistency,
    predictionScores,
    validFrames,
    qualityStatus,
    moodSource,
    songId,
    status,
    error,
    isDetecting,
    detectMood,
    chooseManualMood,
  } = useMoodDetection(videoRef, canvasRef);

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
        <main>
          <IntroSection />
          <section
            className="grid items-stretch gap-5 lg:grid-cols-[1.06fr_0.94fr]"
            aria-label="Mood detection and music player"
          >
            <MoodDetectionCard
              videoRef={videoRef}
              canvasRef={canvasRef}
              cameraState={cameraState}
              cameraError={cameraError}
              onEnableCamera={() => setCameraEnabled(true)}
              onRetryCamera={retryCamera}
              onDisableCamera={() => setCameraEnabled(false)}
              onChooseMood={(selectedMood) => {
                chooseManualMood(selectedMood);
                setCameraEnabled(false);
              }}
              mood={mood}
              consistency={consistency}
              predictionScores={predictionScores}
              validFrames={validFrames}
              qualityStatus={qualityStatus}
              moodSource={moodSource}
              status={status}
              error={error}
              isDetecting={isDetecting}
              onDetectMood={detectMood}
            />
            <MusicRecommendationCard mood={mood} songId={songId} />
          </section>
          <HowItWorks />
          <AboutSection />
          <FaqSection />
        </main>
        <SiteFooter user={user} />
      </div>
    </div>
  );
}

function AuthenticatedPage({ theme, toggleTheme, Page }) {
  const [user, setUser] = useState(null);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    let active = true;
    fetch("/api/auth/session")
      .then((response) => {
        if (!response.ok) throw new Error("Could not verify your session.");
        return response.json();
      })
      .then(({ user: currentUser }) => {
        if (!active) return;
        if (!currentUser) {
          window.location.replace("/signin");
          return;
        }
        setUser(currentUser);
        setCheckingSession(false);
      })
      .catch((error) => {
        if (!active) return;
        console.error("Could not verify the MannKiDhun session:", error);
        window.location.replace("/signin");
      });

    return () => {
      active = false;
    };
  }, []);

  if (checkingSession || !user) {
    return (
      <div className="app-shell auth-loading" role="status">
        <span className="loading-spinner" aria-hidden="true" />
        <span>Getting your space ready…</span>
      </div>
    );
  }

  return <Page user={user} theme={theme} toggleTheme={toggleTheme} />;
}

function App() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const { theme, toggleTheme } = useTheme();

  if (path === "/signin" || path === "/signup") {
    return (
      <AuthPage
        mode={path === "/signup" ? "signup" : "signin"}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
    );
  }

  if (path === "/dashboard") {
    return (
      <AuthenticatedPage
        Page={DashboardPage}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );
  }

  if (path === "/assistant") {
    return (
      <AuthenticatedPage
        Page={AssistantPage}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );
  }

  if (path === "/app" || path === "/mood-check") {
    return (
      <AuthenticatedPage
        Page={MoodExperience}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );
  }
  if (path === "/profile") {
    return (
      <AuthenticatedPage
        Page={ProfilePage}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );
  }
  return <HomePage theme={theme} onToggleTheme={toggleTheme} />;
}

export default App;
