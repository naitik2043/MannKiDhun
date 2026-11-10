import { useState } from "react";
import { recommendations } from "../data/recommendations.js";

function MoodDetectionCard({
  videoRef,
  canvasRef,
  cameraState,
  cameraError,
  onEnableCamera,
  onRetryCamera,
  onDisableCamera,
  onChooseMood,
  mood,
  consistency,
  predictionScores,
  validFrames,
  qualityStatus,
  moodSource,
  status,
  error,
  isDetecting,
  onDetectMood,
}) {
  const cameraReady = cameraState === "ready";
  const [manualMood, setManualMood] = useState("");

  return (
    <article id="mood-check" className="experience-card">
      <div className="card-heading">
        <span className="step-number">01</span>
        <div>
          <p className="card-kicker">FIRST, THE FEELING</p>
          <h2 className="mt-1 font-display text-[17px] font-bold tracking-tight">
            Check in with yourself
          </h2>
        </div>
      </div>

      <div className={`camera-window ${cameraReady ? "camera-ready" : ""}`}>
        <video
          ref={videoRef}
          className="camera-video"
          autoPlay
          playsInline
          muted
          aria-label="Live camera preview"
        />
        {!cameraReady && (
          <div className="camera-placeholder">
            <span className="camera-placeholder-icon" aria-hidden="true">
              ◎
            </span>
            <p role={cameraError ? "alert" : undefined}>
              {cameraError ||
                (cameraState === "idle"
                  ? "Your camera is off until you choose to enable it."
                  : "Connecting to your camera…")}
            </p>
          </div>
        )}
        <span className={`camera-badge ${!cameraReady ? "camera-badge-off" : ""}`}>
          <span />
          {cameraReady ? "CAMERA READY" : "CAMERA OFF"}
        </span>
        <p className="camera-caption">Just you, for a moment.</p>
      </div>
      <canvas ref={canvasRef} className="hidden" />

      <p className="camera-permission-copy">
        Your camera starts only after you enable it and choose Find my
        expression. Five temporary frames are sent to MannKiDhun’s server for
        analysis and aren’t saved. You can turn the camera off or choose a vibe
        without running an expression check.
      </p>
      {cameraState === "idle" && (
        <button className="camera-action-button" type="button" onClick={onEnableCamera}>
          Enable camera
        </button>
      )}
      {cameraState === "unavailable" && (
        <button className="camera-action-button" type="button" onClick={onRetryCamera}>
          Try camera again
        </button>
      )}
      {cameraReady && (
        <button className="camera-action-button" type="button" onClick={onDisableCamera}>
          Turn off camera
        </button>
      )}

      <div className="mt-4 flex items-center justify-between gap-3">
        <button
          className="detect-button"
          type="button"
          disabled={!cameraReady || isDetecting}
          onClick={onDetectMood}
        >
          {isDetecting ? (
            <span className="loading-spinner" aria-hidden="true" />
          ) : (
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path
                d="M10 2.5v3M10 14.5v3M2.5 10h3m9 0h3M4.7 4.7l2.1 2.1m6.4 6.4 2.1 2.1m0-10.6-2.1 2.1m-6.4 6.4-2.1 2.1"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
              <circle
                cx="10"
                cy="10"
                r="3.1"
                stroke="currentColor"
                strokeWidth="1.6"
              />
            </svg>
          )}
          <span>{isDetecting ? "Checking in…" : "Find my expression"}</span>
          {!isDetecting && (
            <span className="text-lg leading-none" aria-hidden="true">
              →
            </span>
          )}
        </button>
        <div className="min-w-[94px] text-right" aria-live="polite">
          <p className="result-label">
            {moodSource === "manual" ? "YOUR CHOICE" : "EXPRESSION ESTIMATE"}
          </p>
          <p className="mt-1 font-display text-lg font-extrabold uppercase tracking-tight">
            {mood || "—"}
          </p>
        </div>
      </div>
      {consistency !== null && (
        <p className="mt-1 text-right text-xs text-muted">
          Frame consistency: {Math.round(consistency * 100)}% ({validFrames}/5 valid)
        </p>
      )}
      {qualityStatus && (
        <p className="mt-1 text-right text-xs text-muted">
          Image quality: {qualityStatus === "good" ? "Good" : "Mixed — some frames were skipped"}
        </p>
      )}
      {predictionScores && (
        <div className="prediction-distribution" aria-label="Model score distribution">
          <p className="result-label">MODEL SCORE DISTRIBUTION · NOT CALIBRATED</p>
          {Object.entries(predictionScores)
            .sort(([, first], [, second]) => second - first)
            .map(([label, score]) => (
              <div className="prediction-score" key={label}>
                <span>{label}</span>
                <span>{Math.round(score * 100)}%</span>
                <span className="prediction-score-track" aria-hidden="true">
                  <span style={{ width: `${score * 100}%` }} />
                </span>
              </div>
            ))}
        </div>
      )}
      <p className="mood-estimate-note">
        This is an estimate of visible facial expressions, not a reliable
        determination of how you actually feel.
      </p>
      {error && (
        <button
          className="mood-retry-button"
          type="button"
          disabled={!cameraReady || isDetecting}
          onClick={onDetectMood}
        >
          Try the mood check again
        </button>
      )}
      <p
        className="status-message"
        role={error ? "alert" : "status"}
        aria-live={error ? "assertive" : "polite"}
      >
        {status}
      </p>
      <div className="manual-vibe-picker">
        <label htmlFor="manual-vibe">Prefer to choose your own vibe?</label>
        <div>
          <select
            id="manual-vibe"
            value={manualMood}
            onChange={(event) => setManualMood(event.target.value)}
          >
            <option value="">Choose a vibe</option>
            {Object.keys(recommendations).map((vibe) => (
              <option value={vibe} key={vibe}>
                {vibe.charAt(0).toUpperCase() + vibe.slice(1)}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!manualMood || isDetecting}
            onClick={() => onChooseMood(manualMood)}
          >
            Use my vibe
          </button>
        </div>
      </div>
    </article>
  );
}

export default MoodDetectionCard;
