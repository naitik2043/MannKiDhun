import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useCamera } from "./useCamera.js";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  delete navigator.mediaDevices;
});

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("useCamera", () => {
  it("starts only when enabled and stops tracks when unmounted", async () => {
    const stop = vi.fn();
    const stream = { getTracks: () => [{ stop }] };
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });
    const video = { srcObject: null, play: vi.fn().mockResolvedValue(undefined) };
    const videoRef = { current: video };
    const { result, rerender, unmount } = renderHook(
      ({ enabled }) => useCamera(videoRef, enabled),
      { initialProps: { enabled: false } },
    );

    expect(result.current.cameraState).toBe("idle");
    expect(getUserMedia).not.toHaveBeenCalled();

    rerender({ enabled: true });
    await waitFor(() => expect(result.current.cameraState).toBe("ready"));
    expect(video.srcObject).toBe(stream);
    unmount();
    expect(stop).toHaveBeenCalledOnce();
    expect(video.srcObject).toBeNull();
  });

  it("shows a useful message when permission is denied", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockRejectedValue(
          Object.assign(new Error("denied"), { name: "NotAllowedError" }),
        ),
      },
    });
    const videoRef = { current: { srcObject: null, play: vi.fn() } };
    const { result } = renderHook(() => useCamera(videoRef, true));

    await waitFor(() => expect(result.current.cameraState).toBe("unavailable"));
    expect(result.current.cameraError).toContain("permission was denied");
  });

  it("releases a stream that resolves after camera shutdown", async () => {
    let resolveStream;
    const stop = vi.fn();
    const getUserMedia = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveStream = resolve;
        }),
    );
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });
    const videoRef = { current: { play: vi.fn() } };
    const { rerender } = renderHook(
      ({ enabled }) => useCamera(videoRef, enabled),
      { initialProps: { enabled: true } },
    );

    await waitFor(() => expect(getUserMedia).toHaveBeenCalledOnce());
    rerender({ enabled: false });
    await act(async () => {
      resolveStream({ getTracks: () => [{ stop }] });
    });
    expect(stop).toHaveBeenCalledOnce();
  });

  it("stops a stream when the preview cannot start", async () => {
    const stop = vi.fn();
    const stream = { getTracks: () => [{ stop }] };
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue(stream) },
    });
    const videoRef = {
      current: {
        srcObject: null,
        play: vi.fn().mockRejectedValue(new Error("preview failed")),
      },
    };
    const { result } = renderHook(() => useCamera(videoRef, true));

    await waitFor(() => expect(result.current.cameraState).toBe("unavailable"));
    expect(stop).toHaveBeenCalledOnce();
    expect(videoRef.current.srcObject).toBeNull();
  });
});
