import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PublicPlaylistPage from "./PublicPlaylistPage.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PublicPlaylistPage", () => {
  it("renders a shared playlist from the public read-only endpoint", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        playlist: {
          id: 4,
          name: "Sunday Hindi Mix",
          owner_name: "Asha",
          description: "Soft Hindi favourites",
          tracks: [{
            id: 10,
            title: "Aankhon Mein Teri",
            artist: "KK",
            language: "Hindi",
            provider_url: "https://music.example/song",
          }],
        },
      }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <PublicPlaylistPage
        playlistId={4}
        theme="dark"
        toggleTheme={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Sunday Hindi Mix" })).toBeTruthy();
    expect(screen.getByText("Curated by Asha")).toBeTruthy();
    expect(screen.getByText("Aankhon Mein Teri")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Open track/ }).getAttribute("href"))
      .toBe("https://music.example/song");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/public/playlists/4");
  });
});
