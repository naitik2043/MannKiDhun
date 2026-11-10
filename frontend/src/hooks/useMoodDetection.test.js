import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useMoodDetection } from "./useMoodDetection.js";

const scores = {
  happy: 0.72,
  neutral: 0.18,
  surprise: 0.04,
  rock: 0.02,
  angry: 0.02,
  sad: 0.02,
};

function setupCanvas() {
  const context = {
    drawImage: vi.fn(),
    clearRect: vi.fn(),
  };
  const canvas = {
    width: 0,
    height: 0,
    getContext: vi.fn(() => context),
    toDataURL: vi.fn(() => "data:image/jpeg;base64,frame"),
  };
  return { canvas, context };
}

function setupVideo() {
  return {
    readyState: HTMLMediaElement.HAVE_CURRENT_DATA,
    videoWidth: 640,
    videoHeight: 480,
  };
}

function mockCaptureDelay() {
  const setTimeout = window.setTimeout.bind(window);
  vi.spyOn(window, "setTimeout").mockImplementation((callback, delay) => {
    if (delay === 180) {
      callback();
      return 0;
    }
    return setTimeout(callback, delay);
  });
}

function successResponse() {
  return {
    ok: true,
    json: async () => ({
      status: "success",
      expression_estimate: "happy",
      prediction_scores: scores,
      valid_frames: 5,
      total_frames: 5,
      consistency: 1,
      consistency_label: "high",
      quality_status: "good",
    }),
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("useMoodDetection", () => {
  it("sends five frames, displays the model result, then clears temporary pixels", async () => {
    const { canvas, context } = setupCanvas();
    const videoRef = { current: setupVideo() };
    const canvasRef = { current: canvas };
    mockCaptureDelay();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(successResponse()));

    const { result } = renderHook(() =>
      useMoodDetection(videoRef, canvasRef),
    );
    await act(async () => {
      await result.current.detectMood();
    });

    expect(result.current.mood).toBe("happy");
    expect(result.current.moodSource).toBe("estimate");
    expect(result.current.predictionScores).toEqual(scores);
    expect(result.current.validFrames).toBe(5);
    expect(result.current.qualityStatus).toBe("good");
    const request = JSON.parse(fetch.mock.calls[0][1].body);
    expect(request.images).toHaveLength(5);
    expect(context.drawImage).toHaveBeenCalledTimes(5);
    expect(context.clearRect).toHaveBeenCalledOnce();
    expect(canvas.width).toBe(0);
    expect(canvas.height).toBe(0);
    expect(result.current.isDetecting).toBe(false);
  });

  it("offers a manual vibe without making an API request", () => {
    const { canvas } = setupCanvas();
    vi.stubGlobal("fetch", vi.fn());
    const { result } = renderHook(() =>
      useMoodDetection({ current: null }, { current: canvas }),
    );

    act(() => result.current.chooseManualMood("sad"));
    expect(result.current.mood).toBe("sad");
    expect(result.current.moodSource).toBe("manual");
    expect(result.current.consistency).toBeNull();
    expect(result.current.predictionScores).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("reports backend failures and still clears the capture canvas", async () => {
    const { canvas, context } = setupCanvas();
    mockCaptureDelay();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network error")));
    const { result } = renderHook(() =>
      useMoodDetection({ current: setupVideo() }, { current: canvas }),
    );

    await act(async () => {
      await result.current.detectMood();
    });
    expect(result.current.error).toContain("Could not reach the analysis service");
    expect(context.clearRect).toHaveBeenCalledOnce();
    expect(canvas.width).toBe(0);
    expect(canvas.height).toBe(0);
  });

  it("rejects an invalid score distribution instead of displaying it", async () => {
    const { canvas } = setupCanvas();
    mockCaptureDelay();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ...successResponse(),
        json: async () => ({
          ...(await successResponse().json()),
          prediction_scores: { ...scores, happy: 5 },
        }),
      }),
    );
    const { result } = renderHook(() =>
      useMoodDetection({ current: setupVideo() }, { current: canvas }),
    );

    await act(async () => {
      await result.current.detectMood();
    });
    expect(result.current.mood).toBe("");
    expect(result.current.error).toContain("invalid prediction score distribution");
  });

  it("reports an analysis timeout and clears the canvas", async () => {
    const { canvas, context } = setupCanvas();
    mockCaptureDelay();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("Aborted", "AbortError")),
    );
    const { result } = renderHook(() =>
      useMoodDetection({ current: setupVideo() }, { current: canvas }),
    );

    await act(async () => {
      await result.current.detectMood();
    });
    expect(result.current.error).toContain("took too long");
    expect(context.clearRect).toHaveBeenCalledOnce();
    expect(canvas.width).toBe(0);
    expect(canvas.height).toBe(0);
  });
});
