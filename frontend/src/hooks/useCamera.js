import { useCallback, useEffect, useState } from "react";

const cameraMessages = {
  NotAllowedError:
    "Camera permission was denied. Allow camera access in this site's browser settings, then reload.",
  NotFoundError: "No camera was found. Connect a camera and reload the page.",
  NotReadableError:
    "The camera is being used by another app. Close it and reload the page.",
};

export function useCamera(videoRef, enabled = true) {
  const [cameraState, setCameraState] = useState(enabled ? "starting" : "idle");
  const [cameraError, setCameraError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let active = true;
    let stream;
    function stopStream() {
      if (!stream) return;
      stream.getTracks().forEach((track) => track.stop());
      if (videoRef.current?.srcObject === stream) {
        videoRef.current.srcObject = null;
      }
      stream = undefined;
    }

    if (!enabled) {
      setCameraState("idle");
      setCameraError("");
      return () => {
        active = false;
      };
    }

    async function startCamera() {
      setCameraState("starting");
      setCameraError("");
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraState("unavailable");
        setCameraError("Camera access is not available in this browser.");
        return;
      }

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: "user",
            width: { ideal: 640 },
            height: { ideal: 480 },
          },
          audio: false,
        });

        if (!active) {
          stopStream();
          return;
        }

        if (!videoRef.current) {
          throw new Error("The camera preview could not be initialized.");
        }

        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraState("ready");
      } catch (error) {
        if (!active) return;
        stopStream();
        console.error("Camera access failed:", error);
        setCameraState("unavailable");
        setCameraError(
          cameraMessages[error.name] ||
            "Camera access failed. Check your camera and reload the page.",
        );
      }
    }

    startCamera();
    return () => {
      active = false;
      stopStream();
    };
  }, [enabled, retryCount, videoRef]);

  const retryCamera = useCallback(() => {
    setRetryCount((count) => count + 1);
  }, []);

  return { cameraState, cameraError, retryCamera };
}
