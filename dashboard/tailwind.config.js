/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        neu: {
          bg: "#2b2f3d",
          surface: "#2b2f3d",
          raised: "#313648",
          shadowDark: "#1c1f29",
          shadowLight: "#3c4258",
          text: "#e8eaf0",
          muted: "#8790a8",
          accent: "#7c8cf8",
          accentMuted: "#5a63a8",
          success: "#5fce9e",
          danger: "#f2777a",
        },
      },
      boxShadow: {
        "neu-raised": "8px 8px 16px #1c1f29, -8px -8px 16px #3c4258",
        "neu-raised-sm": "4px 4px 8px #1c1f29, -4px -4px 8px #3c4258",
        "neu-raised-xs": "2px 2px 5px #1c1f29, -2px -2px 5px #3c4258",
        "neu-pressed": "inset 4px 4px 8px #1c1f29, inset -4px -4px 8px #3c4258",
        "neu-pressed-sm": "inset 3px 3px 6px #1c1f29, inset -3px -3px 6px #3c4258",
      },
      borderRadius: {
        neu: "1.25rem",
        "neu-sm": "0.85rem",
      },
    },
  },
  plugins: [],
};
