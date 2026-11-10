import { useState } from "react";
import { recommendations, chooseSong } from "../data/recommendations.js";

export function useMoodDetection(videoRef, canvasRef) {
  const [isDetecting, setIsDetecting] = useState(false);
  const [status, setStatus] = useState("Enable your camera when you’re ready to begin.");
  const [mood, setMood] = useState("");
  const [consistency, setConsistency] = useState(null);
  const [predictionScores, setPredictionScores] = useState(null);
  const [validFrames, setValidFrames] = useState(0);
  const [qualityStatus, setQualityStatus] = useState("");
  const [moodSource, setMoodSource] = useState("");
  const [songId, setSongId] = useState("");
  const [error, setError] = useState("");

  async function detectMood() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      setStatus("The camera is still getting ready. Please try again in a moment.");
      return;
    }

    let images = [];
    let requestBody = "";
    let context = null;
    let requestTimeout;
    let requestController;
    setIsDetecting(true);
    setMood("");
    setConsistency(null);
    setPredictionScores(null);
    setValidFrames(0);
    setQualityStatus("");
    setMoodSource("");
    setSongId("");
    setError("");
    setStatus("Getting ready to capture five frames…");

    try {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      context = canvas.getContext("2d");
      if (!context || !canvas.width || !canvas.height) {
        throw new Error("The camera has not produced a usable frame yet.");
      }

      const frameCount = 5;
      for (let index = 0; index < frameCount; index += 1) {
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        images.push(canvas.toDataURL("image/jpeg", 0.85));
        if (index < frameCount - 1) {
          setStatus(`Capturing frames… (${index + 1}/${frameCount})`);
          await new Promise((resolve) => window.setTimeout(resolve, 180));
        }
      }

      setStatus("Analyzing the captured frames…");
      requestBody = JSON.stringify({ images });
      requestController = new AbortController();
      requestTimeout = window.setTimeout(() => requestController.abort(), 45000);
      const response = await fetch("/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: requestBody,
        signal: requestController.signal,
      });
      requestBody = "";
      let result;
      try {
        result = await response.json();
      } catch {
        throw new Error("The analysis service returned an unreadable response. Please try again.");
      }

      if (!response.ok) {
        throw new Error(result.error || "The analysis service could not process those frames.");
      }

      const expression = result.expression_estimate;
      if (!recommendations[expression]) {
        throw new Error("The model returned an expression without a music recommendation.");
      }
      if (
        typeof result.consistency !== "number" ||
        !Number.isFinite(result.consistency) ||
        result.consistency < 0 ||
        result.consistency > 1 ||
        !Number.isInteger(result.valid_frames) ||
        result.valid_frames < 3 ||
        result.valid_frames > frameCount ||
        result.total_frames !== frameCount ||
        !result.prediction_scores ||
        typeof result.prediction_scores !== "object"
      ) {
        throw new Error("The server returned an invalid expression analysis.");
      }

      const scoreEntries = Object.entries(result.prediction_scores);
      const scoreTotal = scoreEntries.reduce((total, [, score]) => total + score, 0);
      if (
        scoreEntries.length !== Object.keys(recommendations).length ||
        scoreEntries.some(
          ([label, score]) =>
            !recommendations[label] ||
            typeof score !== "number" ||
            !Number.isFinite(score) ||
            score < 0 ||
            score > 1,
        ) ||
        Math.abs(scoreTotal - 1) > 0.02
      ) {
        throw new Error("The server returned an invalid prediction score distribution.");
      }

      setMood(expression);
      setConsistency(result.consistency);
      setPredictionScores(result.prediction_scores);
      setValidFrames(result.valid_frames);
      setQualityStatus(result.quality_status);
      setMoodSource("estimate");
      setSongId(chooseSong(expression));
      setStatus("Expression estimate ready. It is only a suggestion.");
    } catch (error) {
      console.error("Mood detection failed:", error);
      const message =
        error.name === "AbortError"
          ? "Expression analysis took too long. Please try again."
          : error instanceof TypeError
          ? "Could not reach the analysis service. Check your connection and try again."
          : error.message || "Expression analysis failed. Please try again.";
      setError(message);
      setStatus(message);
    } finally {
      if (requestTimeout !== undefined) window.clearTimeout(requestTimeout);
      images.length = 0;
      requestBody = "";
      if (context && canvas) context.clearRect(0, 0, canvas.width, canvas.height);
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
      }
      setIsDetecting(false);
    }
  }

  function chooseManualMood(selectedMood) {
    if (!recommendations[selectedMood]) {
      throw new Error(`No music recommendations are configured for "${selectedMood}".`);
    }
    setMood(selectedMood);
    setConsistency(null);
    setPredictionScores(null);
    setValidFrames(0);
    setQualityStatus("");
    setMoodSource("manual");
    setSongId(chooseSong(selectedMood));
    setError("");
    setStatus("Your chosen vibe is ready. No expression estimate was used.");
  }

  return {
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
  };
}
