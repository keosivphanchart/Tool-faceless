/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Values come from CSS custom properties (see index.css's
        // :root / [data-theme="retro"] blocks) instead of fixed hex, so
        // switching the `data-theme` attribute at runtime re-themes
        // every `bg-neu-*` / `text-neu-*` / `shadow-neu-*` class already
        // used throughout the app — no component changes needed per
        // theme. The "rgb(var(...) / <alpha-value>)" form (space-
        // separated R G B channels, not a hex string) is what makes
        // Tailwind's opacity modifiers (e.g. `text-neu-danger/60`) work
        // against a CSS-variable color.
        neu: {
          bg: "rgb(var(--neu-bg) / <alpha-value>)",
          surface: "rgb(var(--neu-surface) / <alpha-value>)",
          raised: "rgb(var(--neu-raised) / <alpha-value>)",
          shadowDark: "rgb(var(--neu-shadow-dark) / <alpha-value>)",
          shadowLight: "rgb(var(--neu-shadow-light) / <alpha-value>)",
          text: "rgb(var(--neu-text) / <alpha-value>)",
          muted: "rgb(var(--neu-muted) / <alpha-value>)",
          accent: "rgb(var(--neu-accent) / <alpha-value>)",
          accentMuted: "rgb(var(--neu-accent-muted) / <alpha-value>)",
          success: "rgb(var(--neu-success) / <alpha-value>)",
          danger: "rgb(var(--neu-danger) / <alpha-value>)",
          warn: "rgb(var(--neu-warn) / <alpha-value>)",
        },
      },
      boxShadow: {
        "neu-raised": "8px 8px 16px rgb(var(--neu-shadow-dark)), -8px -8px 16px rgb(var(--neu-shadow-light))",
        "neu-raised-sm": "4px 4px 8px rgb(var(--neu-shadow-dark)), -4px -4px 8px rgb(var(--neu-shadow-light))",
        "neu-raised-xs": "2px 2px 5px rgb(var(--neu-shadow-dark)), -2px -2px 5px rgb(var(--neu-shadow-light))",
        "neu-pressed": "inset 4px 4px 8px rgb(var(--neu-shadow-dark)), inset -4px -4px 8px rgb(var(--neu-shadow-light))",
        "neu-pressed-sm": "inset 3px 3px 6px rgb(var(--neu-shadow-dark)), inset -3px -3px 6px rgb(var(--neu-shadow-light))",
        "neu-glow": "0 0 12px rgb(var(--neu-accent) / 0.55), 0 0 2px rgb(var(--neu-accent) / 0.8)",
      },
      borderRadius: {
        neu: "1.25rem",
        "neu-sm": "0.85rem",
      },
      fontFamily: {
        display: ["var(--neu-font-display)"],
        body: ["var(--neu-font-body)"],
      },
    },
  },
  plugins: [],
};
