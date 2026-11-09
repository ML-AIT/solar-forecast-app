// Light/dark theme choice. "system" follows the OS setting; the choice is kept in localStorage.

export type ThemePreference = "system" | "light" | "dark";

export const THEME_STORAGE_KEY = "solar-theme";
const CHANGE_EVENT = "solar-theme-change";

/**
 * Runs in <head> before the page paints, so a saved theme never flashes the other one first.
 * Kept as a string because it must run before React loads.
 */
export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

function isPreference(value: string | null): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

// Fallback when storage is blocked, so the toggle still cycles within this page view.
let pageChoice: ThemePreference = "system";

export function readThemePreference(): ThemePreference {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(saved) ? saved : "system";
  } catch {
    return pageChoice;
  }
}

function applyTheme(pref: ThemePreference): void {
  const root = document.documentElement;
  if (pref === "system") delete root.dataset.theme;
  else root.dataset.theme = pref;
}

export function setThemePreference(pref: ThemePreference): void {
  pageChoice = pref;
  applyTheme(pref);
  try {
    if (pref === "system") localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, pref);
  } catch {
    // Storage blocked (private window): the theme applies for this page view only.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/** For useSyncExternalStore: re-read when this tab or another tab changes the theme. */
export function subscribeTheme(onChange: () => void): () => void {
  // Another tab changed the theme: apply it here too, not only the toggle label.
  const onStorage = (e: StorageEvent) => {
    if (e.key !== THEME_STORAGE_KEY && e.key !== null) return;
    applyTheme(readThemePreference());
    onChange();
  };
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onStorage);
  };
}

export const NEXT_THEME: Record<ThemePreference, ThemePreference> = {
  system: "light",
  light: "dark",
  dark: "system",
};
