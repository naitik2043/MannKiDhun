import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Header from "./Header.jsx";
import SiteFooter from "./SiteFooter.jsx";

afterEach(() => {
  cleanup();
  window.history.replaceState({}, "", "/");
  document.body.style.overflow = "";
});

describe("site navigation", () => {
  it("shows visitor links and routes search through sign-in to the assistant", () => {
    render(<Header theme="dark" onToggleTheme={vi.fn()} user={null} />);

    expect(screen.getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Discover Music" }).getAttribute("href")).toBe("/signup");
    expect(screen.getByRole("link", { name: "About" }).getAttribute("href")).toBe("/#about-us");
    expect(screen.getByRole("link", { name: "Sign in to search music" }).getAttribute("href"))
      .toBe("/signin?next=%2Fassistant");
    expect(screen.getAllByRole("link", { name: "Get started" }).some((link) => link.getAttribute("href") === "/signup"))
      .toBe(true);
  });

  it("opens and closes the mobile navigation with Escape and locks page scrolling", () => {
    render(<Header theme="dark" onToggleTheme={vi.fn()} user={null} />);
    const menuButton = screen.getByRole("button", { name: "Open navigation menu" });

    fireEvent.click(menuButton);
    expect(menuButton.getAttribute("aria-expanded")).toBe("true");
    expect(document.body.style.overflow).toBe("hidden");
    expect(screen.getByRole("navigation", { name: "Main navigation" }).className)
      .toContain("header-nav-open");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("button", { name: "Open navigation menu" }).getAttribute("aria-expanded"))
      .toBe("false");
    expect(document.body.style.overflow).toBe("");
  });

  it("shows authenticated destinations and supports profile-menu logout", async () => {
    const onSignOut = vi.fn();
    window.history.replaceState({}, "", "/assistant");
    render(
      <Header
        theme="dark"
        onToggleTheme={vi.fn()}
        user={{ name: "Test Listener", email: "listener@example.com" }}
        onSignOut={onSignOut}
      />,
    );

    expect(screen.getByRole("link", { name: "Music Assistant" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Playlists" }).getAttribute("href"))
      .toBe("/assistant#assistant-playlists");
    expect(screen.getByRole("link", { name: "Search music with the Music Assistant" }).getAttribute("href"))
      .toBe("/assistant");

    fireEvent.click(screen.getByRole("button", { name: "Open profile menu for Test Listener" }));
    const profileActions = screen.getByRole("navigation", { name: "Profile actions" });
    expect(within(profileActions).getByRole("link", { name: "Account Settings" }).getAttribute("href"))
      .toBe("/profile#account-settings");
    fireEvent.click(within(profileActions).getByRole("button", { name: "Log out" }));
    await waitFor(() => expect(onSignOut).toHaveBeenCalledOnce());
  });

  it("uses the saved profile photo in desktop and mobile avatar controls", () => {
    const { container } = render(
      <Header
        theme="dark"
        onToggleTheme={vi.fn()}
        user={{
          name: "Test Listener",
          email: "listener@example.com",
          profile_image: "/api/profile/avatar/1234567890abcdef1234567890abcdef.jpg",
        }}
      />,
    );

    expect(container.querySelectorAll(
      ".profile-avatar-small img[src='/api/profile/avatar/1234567890abcdef1234567890abcdef.jpg']",
    )).toHaveLength(2);
  });
});

describe("site footer", () => {
  it("uses the current year and only links to implemented support destinations", () => {
    render(<SiteFooter user={null} />);

    expect(screen.getByText(`© ${new Date().getFullYear()} MannKiDhun. All rights reserved.`)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Frequently Asked Questions" }).getAttribute("href"))
      .toBe("#faq");
    expect(screen.getByRole("link", { name: "Privacy Information" }).getAttribute("href"))
      .toBe("#privacy-note");
    expect(screen.getByRole("link", { name: /LinkedIn/ }).getAttribute("href"))
      .toBe("https://www.linkedin.com/in/naitik2043/");
    expect(screen.getByRole("link", { name: /GitHub/ }).getAttribute("href"))
      .toBe("https://github.com/naitik2043");
    expect(screen.queryByRole("link", { name: /Terms|Contact|Help Center/i })).toBeNull();
  });
});
