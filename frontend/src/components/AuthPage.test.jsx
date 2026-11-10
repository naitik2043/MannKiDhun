import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AuthPage from "./AuthPage.jsx";

afterEach(() => {
  cleanup();
});

describe("AuthPage", () => {
  it("places the remember-me checkbox before its text and keeps it interactive", () => {
    render(<AuthPage mode="signin" theme="light" onToggleTheme={vi.fn()} />);
    const label = screen.getByText("Remember me").parentElement;
    const checkbox = label.querySelector('input[type="checkbox"]');

    expect(checkbox.nextElementSibling).toBe(screen.getByText("Remember me"));
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);
  });
});
