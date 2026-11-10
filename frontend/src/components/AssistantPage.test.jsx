import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AssistantPage from "./AssistantPage.jsx";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body, ok = true) {
  return {
    ok,
    json: async () => body,
  };
}

describe("AssistantPage", () => {
  it("shows catalogue recommendations, saves a song, and clears chat", async () => {
    const fetchMock = vi.fn(async (url, options = {}) => {
      if (url === "/api/v1/playlists" && options.method === "POST") {
        return jsonResponse({ playlist: { id: 3, name: "Evening Mix" } });
      }
      if (url === "/api/v1/playlists") {
        return jsonResponse({ playlists: [] });
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
            },
          ],
        });
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

    fireEvent.change(screen.getByLabelText("Your music request"), {
      target: { value: "peaceful music" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Catalogue Track")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(screen.getByTitle("Play Catalogue Track by Catalogue Artist")).toBeTruthy();
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
