import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AssistantPage from "./AssistantPage.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function jsonResponse(body, ok = true) {
  return {
    ok,
    json: async () => body,
  };
}

describe("AssistantPage", () => {
  it("prefills Match mode from a confirmed mood check-in", async () => {
    window.history.pushState({}, "", "/assistant?mood=happy");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ playlists: [] })));

    render(
      <AssistantPage
        user={{ name: "Listener", email: "listener@example.com" }}
        theme="dark"
        toggleTheme={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Current mood (optional)").value).toBe("happy");
    expect(screen.getByText(/Starting from your happy check-in/)).toBeTruthy();
    window.history.replaceState({}, "", "/");
  });

  it("shows catalogue recommendations, saves a song, and clears chat", async () => {
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (url === "/api/v1/playlists/3/invites" && options.method === "POST") {
        return jsonResponse({
          invite_url: "http://localhost/assistant?invite_playlist=3&invite_token=long-secure-token",
          expires_at: "2026-11-29 12:00:00",
        });
      }
      if (url === "/api/v1/playlists" && options.method === "POST") {
        return jsonResponse({ playlist: { id: 3, name: "Evening Mix" } });
      }
      if (url === "/api/v1/playlists") {
        return jsonResponse({ playlists: [] });
      }
      if (url === "/api/v1/users/me/adaptive-session" && options.method === "POST") {
        return jsonResponse({
          message: "Adaptive session ready.",
          recommendations: [{
            id: 12,
            title: "Session track",
            artist: "Catalogue Artist",
            provider: "youtube",
            provider_track_id: "AbcdEF12345",
            provider_url: "https://music.example/session-track",
          }],
          state: { queue: [12] },
        });
      }
      if (url === "/api/v1/assistant/chat") {
        return jsonResponse({
          response: "Here is an available track.",
          intent: { mood: "relaxed" },
          recommendations: [
            {
              id: 12,
              title: "Catalogue Track",
              artist: "Catalogue Artist",
              provider: "youtube",
              provider_track_id: "AbcdEF12345",
              provider_url: "https://music.example/track-12",
              explanation: "It matches your selected relaxed vibe.",
            },
          ],
        });
      }
      if (url === "/api/v1/users/me/listening-history" && options.method === "POST") {
        const payload = JSON.parse(options.body);
        return jsonResponse({ status: "ok", interaction: payload.event_type, song_id: payload.song_id });
      }
      if (url === "/api/v1/users/me/saved-songs") return jsonResponse({ saved: true });
      if (url === "/api/v1/users/me/playback-state") {
        return jsonResponse({ state: { queue: [], current_song_id: null } });
      }
      if (url === "/api/v1/playlists/3/tracks") return jsonResponse({ playlist: {} });
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AssistantPage
        user={{ name: "Listener", email: "listener@example.com" }}
        theme="dark"
        toggleTheme={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Create a playlist"), {
      target: { value: "Evening Mix" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("created"));
    fireEvent.change(screen.getByRole("combobox", { name: "New collaborator role" }), {
      target: { value: "editor" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Invite editor" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("invite_token=long-secure-token"));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/playlists/3/invites",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ role: "editor" }),
      }),
    );

    fireEvent.change(screen.getByLabelText("Listening context (optional)"), {
      target: { value: "studying" },
    });
    fireEvent.change(screen.getByLabelText("Your music request"), {
      target: { value: "peaceful music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Catalogue Track")).toBeTruthy();
    const chatCall = fetchMock.mock.calls.find(([url]) => url === "/api/v1/assistant/chat");
    expect(JSON.parse(chatCall[1].body)).toMatchObject({ context: "studying" });
    fireEvent.change(screen.getByRole("combobox", { name: "Discovery mode" }), { target: { value: "change" } });
    fireEvent.change(screen.getByLabelText("Mood you want to move toward"), { target: { value: "happy" } });
    fireEvent.click(screen.getByRole("button", { name: "Build adaptive session" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/users/me/adaptive-session",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          mode: "change",
          mood: "happy",
          use_preferences: false,
          use_history: false,
          context: "studying",
          limit: 8,
        }),
      }),
    ));
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));
    await waitFor(() => {
      const saveCall = fetchMock.mock.calls.find(
        ([url, options]) => url === "/api/v1/users/me/playback-state" && options?.method === "POST",
      );
      expect(saveCall).toBeTruthy();
      expect(JSON.parse(saveCall[1].body)).toMatchObject({
        current_song_id: 12,
        position_ms: 0,
        queue: [12],
      });
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Play" })[0]);
    expect(screen.getByTitle("Play Catalogue Track by Catalogue Artist")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/users/me/listening-history",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ song_id: 12, event_type: "play", source: "assistant" }),
      }),
    ));
    expect(screen.getByText("Why this fits: It matches your selected relaxed vibe.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Like" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("positive feedback"));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/users/me/listening-history",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ song_id: 12, event_type: "like", source: "assistant" }),
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Not for me" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("ranked lower"));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/users/me/listening-history",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ song_id: 12, event_type: "skip", source: "assistant" }),
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("saved"));

    fireEvent.click(screen.getByRole("button", { name: "Add to queue" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("queue"));
    fireEvent.change(screen.getByLabelText("Playlist for Catalogue Track"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add to playlist" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("playlist"));

    fireEvent.click(screen.getByRole("button", { name: "Clear conversation" }));
    expect(screen.queryByText("Catalogue Track")).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/users/me/saved-songs",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/playlists/3/tracks",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/playlists",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
