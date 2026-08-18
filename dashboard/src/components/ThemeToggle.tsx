import { useEffect, useState } from "react";
import { Zap } from "lucide-react";
import { NeuButton } from "./Neu";

type Theme = "capybara" | "retro";

const STORAGE_KEY = "faceless-pipeline-theme";

function applyTheme(theme: Theme) {
  if (theme === "retro") {
    document.documentElement.setAttribute("data-theme", "retro");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

/** Every `bg-neu-*` / `shadow-neu-*` class in the app resolves through
 * CSS custom properties (see index.css), so flipping `data-theme` on
 * <html> re-themes the whole dashboard with no per-page changes needed.
 * Persisted to localStorage so a reload keeps whichever mode was picked. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "retro" ? "retro" : "capybara";
  });

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return (
    <NeuButton
      className="w-full justify-center text-xs"
      onClick={() => setTheme((t) => (t === "capybara" ? "retro" : "capybara"))}
      title={theme === "capybara" ? "Switch to Retro Futuristic mode" : "Switch to Capybara mode"}
    >
      <Zap size={14} aria-hidden="true" />
      {theme === "capybara" ? "Retro mode" : "Capybara mode"}
    </NeuButton>
  );
}
