import { useEffect, useState } from "react";

function getInitialTheme() {
  try {
    const savedTheme =
      window.localStorage.getItem("mannkidhun-theme") ||
      window.localStorage.getItem("moodwave-theme");
    if (savedTheme === "light" || savedTheme === "dark") return savedTheme;
  } catch (error) {
    console.warn("Could not read the saved theme preference:", error);
  }

  return "dark";
}

export function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    try {
      window.localStorage.setItem("mannkidhun-theme", theme);
    } catch (error) {
      console.warn("Could not save the theme preference:", error);
    }
  }, [theme]);

  function toggleTheme() {
    setTheme((currentTheme) => (currentTheme === "light" ? "dark" : "light"));
  }

  return { theme, toggleTheme };
}
