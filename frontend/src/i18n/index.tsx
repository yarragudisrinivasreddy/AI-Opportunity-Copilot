import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { I18N as I18N_RAW } from "./packs.js";

export type Lang = "en" | "hi" | "te";
const LANGS: Lang[] = ["en", "hi", "te"];

type Pack = {
  name: string;
  u: Record<string, string>;
  s: {
    text: string;
    steps: string[];
    qs?: { q: string; a: string[] }[];
    opps: {
      v?: string; name: string; problem: string; improvement: string; value: string; effort: string;
      humans: string; assume: string; flow: string[][];
    }[];
    providers: { name: string; verdict: string; price: string; weeks: string; text: string; quote?: string }[];
    brief: [string, string | null, string[] | null][];
    brief_title: string;
    brief_note: string;
    ev_obs?: string;
    ev_asm?: string[];
  };
};
type U = Pack["u"];
const I18N = I18N_RAW as unknown as Record<Lang, Pack>;

function detect(): Lang {
  try {
    const saved = localStorage.getItem("copilot-lang");
    if (saved && LANGS.includes(saved as Lang)) return saved as Lang;
  } catch { /* storage blocked */ }
  const nav = (typeof navigator !== "undefined" ? navigator.language : "en").toLowerCase();
  if (nav.startsWith("hi")) return "hi";
  if (nav.startsWith("te")) return "te";
  return "en";
}

function interpolate(s: string, vars?: Record<string, string>) {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? `{${k}}`);
}

type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: keyof U, vars?: Record<string, string>) => string;
  sample: Pack["s"];
  langs: Lang[];
  name: (l: Lang) => string;
};

const LanguageContext = createContext<Ctx | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detect);

  const setLang = (l: Lang) => {
    setLangState(l);
    try { localStorage.setItem("copilot-lang", l); } catch { /* ignore */ }
  };

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo<Ctx>(() => {
    const pack = I18N[lang] ?? I18N.en;
    return {
      lang,
      setLang,
      t: (key, vars) => interpolate((pack.u as U)[key] ?? (I18N.en.u as U)[key] ?? String(key), vars),
      sample: pack.s,
      langs: LANGS,
      name: (l) => I18N[l].name,
    };
  }, [lang]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useI18n outside LanguageProvider");
  return ctx;
}
