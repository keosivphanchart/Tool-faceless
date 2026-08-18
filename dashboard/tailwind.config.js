/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Capybara" palette: warm sandy tan base (fur), deep brown text,
        // mikan-orange primary accent (the onsen mandarin oranges), moss
        // green for success, and a golden amber for pending/in-progress —
        // swapped in for the original cold dark-slate/indigo scheme.
        neu: {
          bg: "#EFDFC0",
          surface: "#EFDFC0",
          raised: "#F7EDD6",
          shadowDark: "#CDA971",
          shadowLight: "#FFFCF2",
          text: "#4A2E1B",
          muted: "#8B6B47",
          accent: "#E8752C",
          accentMuted: "#F2A65A",
          success: "#5E8F2E",
          danger: "#C1440E",
          warn: "#D9A62E",
        },
      },
      boxShadow: {
        "neu-raised": "8px 8px 16px #CDA971, -8px -8px 16px #FFFCF2",
        "neu-raised-sm": "4px 4px 8px #CDA971, -4px -4px 8px #FFFCF2",
        "neu-raised-xs": "2px 2px 5px #CDA971, -2px -2px 5px #FFFCF2",
        "neu-pressed": "inset 4px 4px 8px #CDA971, inset -4px -4px 8px #FFFCF2",
        "neu-pressed-sm": "inset 3px 3px 6px #CDA971, inset -3px -3px 6px #FFFCF2",
      },
      borderRadius: {
        neu: "1.25rem",
        "neu-sm": "0.85rem",
      },
    },
  },
  plugins: [],
};
