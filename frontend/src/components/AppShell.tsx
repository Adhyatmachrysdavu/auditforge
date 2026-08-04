"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Gauge,
  FolderOpen,
  Bug,
  FileText,
  Path,
  ShieldCheck,
  Sun,
  Moon,
  Translate,
  SignOut,
} from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/i18n/LocaleProvider";
import { LOCALE_LABEL, type MessageKey } from "@/i18n/messages";

type Theme = "light" | "dark";

const NAV: { href: string; icon: React.ReactNode; key: MessageKey }[] = [
  { href: "/", icon: <Gauge size={18} weight="bold" />, key: "nav.dashboard" },
  { href: "/engagements", icon: <FolderOpen size={18} />, key: "nav.engagements" },
  { href: "/findings", icon: <Bug size={18} />, key: "nav.findings" },
  { href: "/reports", icon: <FileText size={18} />, key: "nav.reports" },
  { href: "/ingest", icon: <Path size={18} />, key: "nav.ingest" },
  { href: "/admin", icon: <ShieldCheck size={18} />, key: "nav.admin" },
];

export function AppShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const { user, loading, signOut } = useAuth();
  const { t, locale, toggleLocale } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(
      (document.documentElement.getAttribute("data-theme") as Theme) || "light",
    );
  }, []);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("af-theme", next);
    } catch {
      /* abaikan */
    }
  }

  if (loading || !user) {
    return <div className="fullscreen-msg">{t("common.loading")}</div>;
  }

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">AuditForge</div>
        <nav className="nav">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`navitem${isActive(item.href) ? " active" : ""}`}
            >
              {item.icon} {t(item.key)}
            </Link>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <strong>{title}</strong>
          <div className="topbar-actions">
            <span className="topbar-user mono">
              {user.full_name} · {user.role}
            </span>
            <button className="btn ghost" onClick={toggleLocale} title="Bahasa / Language">
              <Translate size={16} weight="fill" /> {LOCALE_LABEL[locale]}
            </button>
            <button className="btn ghost" onClick={toggleTheme}>
              {theme === "dark" ? (
                <>
                  <Moon size={16} weight="fill" /> {t("theme.dark")}
                </>
              ) : (
                <>
                  <Sun size={16} weight="fill" /> {t("theme.light")}
                </>
              )}
            </button>
            <button
              className="btn ghost"
              onClick={() => {
                signOut();
                router.replace("/login");
              }}
            >
              <SignOut size={16} weight="fill" /> {t("common.logout")}
            </button>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
