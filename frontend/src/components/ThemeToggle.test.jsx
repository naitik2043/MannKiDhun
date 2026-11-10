import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ThemeToggle from "./ThemeToggle.jsx";

describe("ThemeToggle", () => {
  it("announces and requests the opposite theme", () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <ThemeToggle theme="dark" onToggle={onToggle} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(onToggle).toHaveBeenCalledOnce();

    rerender(<ThemeToggle theme="light" onToggle={onToggle} />);
    expect(screen.getByRole("button", { name: "Switch to dark mode" })).toBeTruthy();
  });
});
