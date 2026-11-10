import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProfilePage from "./ProfilePage.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("ProfilePage", () => {
  it("only enables saving when profile details have changed and restores them on cancel", async () => {
    const user = { name: "Mira Listener", email: "mira@example.com" };
    const updatedUser = { ...user, name: "Mira Music" };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ user: updatedUser }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ProfilePage user={user} theme="light" toggleTheme={vi.fn()} />);

    const saveButton = screen.getByRole("button", { name: "Nothing to save" });
    expect(saveButton.disabled).toBe(true);

    const nameInput = screen.getByLabelText("Full name");
    fireEvent.change(nameInput, { target: { value: "Mira Music" } });
    expect(screen.getByRole("button", { name: "Save changes" }).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(nameInput.value).toBe(user.name);
    expect(screen.getByRole("button", { name: "Nothing to save" }).disabled).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.change(nameInput, { target: { value: "Mira Music" } });
    fireEvent.change(screen.getByLabelText("Current password"), {
      target: { value: "current-pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(screen.getByRole("status").textContent)
        .toBe("Your profile has been updated.");
    });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      name: "Mira Music",
      email: user.email,
      current_password: "current-pass",
      new_password: "",
    });
    expect(screen.getByLabelText("Current password").value).toBe("");
    expect(screen.getByRole("button", { name: "Nothing to save" }).disabled).toBe(true);
  });

  it("clears a failed save message when the user edits the form", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ error: "Your current password is incorrect." }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ProfilePage
        user={{ name: "Mira Listener", email: "mira@example.com" }}
        theme="light"
        toggleTheme={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Full name"), {
      target: { value: "Mira Music" },
    });
    fireEvent.change(screen.getByLabelText("Current password"), {
      target: { value: "wrong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect((await screen.findByRole("alert")).textContent)
      .toBe("Your current password is incorrect.");

    fireEvent.change(screen.getByLabelText("Full name"), {
      target: { value: "Mira Listener" },
    });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("uploads a selected photo and supports removing it", async () => {
    const updatedUser = {
      name: "Mira Listener",
      email: "mira@example.com",
      profile_image: "/api/profile/avatar/1234567890abcdef1234567890abcdef.jpg",
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ user: updatedUser }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          user: { name: updatedUser.name, email: updatedUser.email },
        }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ProfilePage
        user={updatedUser}
        theme="light"
        toggleTheme={vi.fn()}
      />,
    );

    const image = new File(["photo"], "portrait.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Choose a profile photo"), {
      target: { files: [image] },
    });

    await waitFor(() => {
      expect(screen.getByAltText("Mira Listener profile").getAttribute("src"))
        .toBe(updatedUser.profile_image);
    });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/profile/avatar");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(fetchMock.mock.calls[0][1].body.get("avatar")).toBe(image);
    expect(screen.getByRole("status").textContent)
      .toBe("Your profile photo has been updated.");

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => {
      expect(screen.queryByAltText("Mira Listener profile")).toBeNull();
    });
    expect(fetchMock.mock.calls[1]).toEqual([
      "/api/profile/avatar",
      { method: "DELETE" },
    ]);
  });

  it("rejects unsupported image types before sending a request", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ProfilePage
        user={{ name: "Mira Listener", email: "mira@example.com" }}
        theme="light"
        toggleTheme={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Choose a profile photo"), {
      target: { files: [new File(["text"], "notes.txt", { type: "text/plain" })] },
    });

    expect(screen.getByRole("alert").textContent)
      .toBe("Choose a JPEG, PNG, or WebP image.");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
