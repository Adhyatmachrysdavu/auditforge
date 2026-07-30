"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { messages, type Locale, type MessageKey } from "./messages";

type I18nContext = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  toggleLocale: () => void;
  t: (key: MessageKey) => string;
};

const Ctx = createContext<I18nContext | null>(null);

const STORAGE_KEY = "af-locale";
const DEFAULT_LOCALE: Locale = "id"; // perusahaan Indonesia → ID sebagai bawaan

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  // Server & render klien pertama sama-sama pakai DEFAULT_LOCALE → tak ada
  // ketidakcocokan hidrasi. Preferensi tersimpan diterapkan setelah mount.
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(STORAGE_KEY);
    } catch {
      /* localStorage tak tersedia — abaikan */
    }
    if (stored === "id" || stored === "en") {
      setLocaleState(stored);
    } else if (
      typeof navigator !== "undefined" &&
      navigator.language.toLowerCase().startsWith("en")
    ) {
      setLocaleState("en");
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* abaikan */
    }
  }, []);

  const toggleLocale = useCallback(() => {
    setLocale(locale === "id" ? "en" : "id");
  }, [locale, setLocale]);

  const t = useCallback(
    (key: MessageKey) => messages[locale][key] ?? key,
    [locale],
  );

  return (
    <Ctx.Provider value={{ locale, setLocale, toggleLocale, t }}>
      {children}
    </Ctx.Provider>
  );
}

export function useI18n(): I18nContext {
  const ctx = useContext(Ctx);
  if (!ctx) {
    throw new Error("useI18n harus dipakai di dalam <LocaleProvider>");
  }
  return ctx;
}
