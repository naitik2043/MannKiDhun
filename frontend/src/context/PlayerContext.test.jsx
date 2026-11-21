import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlayerProvider, usePlayer } from "./PlayerContext.jsx";

const trackOne = {
  id: 1, title: "First song", artist: "Artist One",
  provider: "youtube", provider_track_id: "AbcdEF12345",
};
const trackTwo = {
  id: 2, title: "Second song", artist: "Artist Two",
  provider: "youtube", provider_track_id: "BcdeFG23456",
};
const trackThree = {
  id: 3, title: "Third song", artist: "Artist Three",
  provider: "youtube", provider_track_id: "CdefGH34567",
};

class MockYouTubePlayer {
  constructor(_container, options) {
    this.options = options;
    this.lastLoaded = null;
    window.__mockYouTubePlayer = this;
    queueMicrotask(() => options.events.onReady());
  }
  loadVideoById(value) { this.lastLoaded = { type: "load", ...value }; }
  cueVideoById(value) { this.lastLoaded = { type: "cue", ...value }; }
  playVideo() { this.options.events.onStateChange({ data: 1 }); }
  pauseVideo() { this.options.events.onStateChange({ data: 2 }); }
  seekTo(seconds) { this.lastSeek = seconds; }
  getCurrentTime() { return 12; }
  destroy() {}
}

function PlayerProbe() {
  const player = usePlayer();
  return (
    <div>
      <p role="status">
        {player.currentSong?.title || "No active track"} · {player.queue.length} queued · {player.currentIndex}
      </p>
      <button onClick={() => player.playQueue([trackOne, trackTwo], 0)}>Start queue</button>
      <button onClick={() => player.nextTrack()}>Advance test queue</button>
      <button onClick={() => player.addToQueue(trackThree)}>Add third track</button>
      <button onClick={() => player.updateUpcomingTracks([trackThree])}>Refresh upcoming</button>
      <button onClick={() => player.setRepeatMode("all")}>Repeat all</button>
      <button onClick={() => player.playSong(trackTwo)}>Play second song</button>
    </div>
  );
}

beforeEach(() => {
  window.localStorage.clear();
  window.YT = {
    Player: MockYouTubePlayer,
    PlayerState: { PLAYING: 1, PAUSED: 2, CUED: 5, ENDED: 0 },
  };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ state: {} }),
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete window.YT;
  delete window.__mockYouTubePlayer;
  window.localStorage.clear();
});

describe("PlayerProvider", () => {
  it("keeps a single player, advances tracks and refreshes upcoming tracks", async () => {
    render(<PlayerProvider><PlayerProbe /></PlayerProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Start queue" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("First song"));
    await waitFor(() => {
      expect(window.__mockYouTubePlayer?.lastLoaded?.videoId).toBe(trackOne.provider_track_id);
    });
    fireEvent.click(screen.getByRole("button", { name: "Next track" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Second song"));
    await waitFor(() => {
      expect(window.__mockYouTubePlayer?.lastLoaded?.videoId).toBe(trackTwo.provider_track_id);
    });
    fireEvent.click(screen.getByRole("button", { name: "Add third track" }));
    expect(screen.getByRole("status").textContent).toContain("3 queued");
    fireEvent.click(screen.getByRole("button", { name: "Refresh upcoming" }));
    expect(screen.getByRole("status").textContent).toContain("2 queued");
    fireEvent.click(screen.getByRole("button", { name: "Repeat all" }));
    expect(screen.getByLabelText("Repeat mode").value).toBe("all");
  });

  it("restores the selected track from local queue state", () => {
    window.localStorage.setItem("mannkidhun_player_v1", JSON.stringify({
      queue: [trackOne, trackTwo],
      currentIndex: 1,
      positionMs: 12500,
      repeatMode: "one",
    }));
    render(<PlayerProvider><PlayerProbe /></PlayerProvider>);
    expect(screen.getByRole("status").textContent).toContain("Second song");
    expect(screen.getByRole("status").textContent).toContain("2 queued");
    expect(screen.getByLabelText("Repeat mode").value).toBe("one");
  });

  it("keeps upcoming tracks when a listener plays a different song", async () => {
    render(<PlayerProvider><PlayerProbe /></PlayerProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Start queue" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("First song"));
    fireEvent.click(screen.getByRole("button", { name: "Play second song" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Second song"));
    expect(screen.getByRole("status").textContent).toContain("2 queued");
  });

  it("retries loading the YouTube API after a script failure", async () => {
    delete window.YT;
    const firstRender = render(<PlayerProvider><PlayerProbe /></PlayerProvider>);
    const firstScript = await waitFor(() => {
      const script = document.querySelector('script[data-mannkidhun-youtube-api="true"]');
      expect(script).not.toBeNull();
      return script;
    });

    fireEvent.error(firstScript);
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("could not load");
    });
    expect(firstScript.isConnected).toBe(false);
    firstRender.unmount();

    render(<PlayerProvider><PlayerProbe /></PlayerProvider>);
    const retryScript = await waitFor(() => {
      const script = document.querySelector('script[data-mannkidhun-youtube-api="true"]');
      expect(script).not.toBeNull();
      return script;
    });
    expect(retryScript).not.toBe(firstScript);

    window.YT = {
      Player: MockYouTubePlayer,
      PlayerState: { PLAYING: 1, PAUSED: 2, CUED: 5, ENDED: 0 },
    };
    await act(async () => {
      window.onYouTubeIframeAPIReady();
    });

    await waitFor(() => {
      expect(window.__mockYouTubePlayer).toBeDefined();
    });
  });
});
