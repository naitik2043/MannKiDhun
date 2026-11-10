import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "./DashboardPage.jsx";

describe("DashboardPage", () => {
  it("uses the listener's first name and links to available music features", () => {
    render(
      <DashboardPage
        user={{ name: "Asha Listener", email: "asha@example.com" }}
        theme="dark"
        toggleTheme={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Welcome, Asha." })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Explore by vibe/ }).getAttribute("href"))
      .toBe("/app");
    expect(screen.getByRole("link", { name: /Create a playlist/ }).getAttribute("href"))
      .toBe("/assistant#assistant-playlists");
    expect(screen.getByText("Tracks played from the assistant aren’t added to listening history yet."))
      .toBeTruthy();
    expect(screen.queryByText("Featured playlists")).toBeNull();
    expect(screen.queryByText("COMING SOON")).toBeNull();
  });
});
