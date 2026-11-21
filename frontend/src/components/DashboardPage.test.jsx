import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "./DashboardPage.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function jsonResponse(body, ok = true) {
  return { ok, json: async () => body };
}

describe("DashboardPage", () => {
  it("loads and displays the listener's history and playlists", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (url === "/api/v1/users/me/listening-history") {
        return jsonResponse({
          history: [{
            id: 12,
            title: "Midnight City",
            artist: "M83",
            language: "English",
            interaction_type: "play",
            created_at: "2026-11-20 18:25:00",
          }],
        });
      }
      if (url === "/api/v1/playlists") {
        return jsonResponse({ playlists: [{ id: 7, name: "Late Night Mix", track_count: 4 }] });
      }
      throw new Error("Unexpected request: " + url);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DashboardPage
        user={{ name: "Asha Listener", email: "asha@example.com" }}
        theme="dark"
        toggleTheme={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Welcome, Asha." })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Explore by vibe/ }).getAttribute("href")).toBe("/app");
    expect(await screen.findByText("Midnight City")).toBeTruthy();
    expect(screen.getByText("M83 · English")).toBeTruthy();
    expect(screen.getByText("Played")).toBeTruthy();
    expect(screen.getByText("Late Night Mix")).toBeTruthy();
    expect(screen.getByText("4 tracks")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/users/me/listening-history");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/playlists");
  });

  it("shows helpful empty states when the listener has no activity yet", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (url === "/api/v1/users/me/listening-history") return jsonResponse({ history: [] });
      if (url === "/api/v1/playlists") return jsonResponse({ playlists: [] });
      throw new Error("Unexpected request: " + url);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DashboardPage
        user={{ name: "Asha Listener", email: "asha@example.com" }}
        theme="light"
        toggleTheme={vi.fn()}
      />,
    );

    expect(await screen.findByText("Your listening history starts here")).toBeTruthy();
    expect(screen.getByText("Keep the songs you love together")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Create a playlist/ }).getAttribute("href"))
      .toBe("/assistant#assistant-playlists");
  });
});
