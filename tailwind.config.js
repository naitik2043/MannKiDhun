/** @type {import('tailwindcss').Config} */
export default {
  content: ["./frontend/index.html", "./frontend/src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Manrope", "sans-serif"],
        sans: ["Inter", "sans-serif"],
      },
      colors: {
        ink: "var(--text-primary)",
        muted: "var(--text-secondary)",
        subtle: "var(--text-subtle)",
        accent: "var(--accent-color)",
      },
    },
  },
  plugins: [],
};
