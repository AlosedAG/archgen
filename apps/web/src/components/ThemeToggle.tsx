"use client";

/**
 * Light / dark theme. With nothing saved the app follows the OS; the toggle
 * pins a choice as data-theme on <html> and remembers it. THEME_SCRIPT runs
 * in <head> before paint so a saved dark theme never flashes light.
 */

import { useEffect, useState } from "react";

import { NavIcon } from "./NavIcons";

const KEY = "thz-theme";
type Theme = "light" | "dark";

export const THEME_SCRIPT = `try{var t=localStorage.getItem("${KEY}");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

function currentTheme(): Theme {
  const set = document.documentElement.getAttribute("data-theme");
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);
  useEffect(() => setTheme(currentTheme()), []);

  const toggle = () => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // Storage blocked: the choice still applies until reload.
    }
    setTheme(next);
  };

  const label = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
  return (
    <button type="button" className="topbtn" onClick={toggle} title={label} aria-label={label}>
      <NavIcon name={theme === "dark" ? "moon" : "sun"} size={18} />
    </button>
  );
}
