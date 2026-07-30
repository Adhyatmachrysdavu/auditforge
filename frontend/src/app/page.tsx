"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FolderOpen } from "@phosphor-icons/react";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import * as api from "@/lib/api";

const SEV_CLASS: Record<string, string> = {
  critical: "err",
  high: "err",
  medium: "wait",
  low: "wait",
  info: "ok",
};
const SEV_ORDER = ["critical", "high", "medium", "low", "info"];

export default function DashboardPage() {
  const { t } = useI18n();
  const [stats, setStats] = useState<api.Stats | null>(null);

  useEffect(() => {
    api.getStats().then(setStats).catch(() => {});
  }, []);

  return (
    <AppShell title={t("nav.dashboard")}>
      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-num mono">{stats ? stats.engagements : "–"}</div>
          <div className="stat-label">{t("nav.engagements")}</div>
        </div>
        <div className="stat-card">
          <div className="stat-num mono">{stats ? stats.uploads : "–"}</div>
          <div className="stat-label">{t("dash.uploads")}</div>
        </div>
        <div className="stat-card">
          <div className="stat-num mono">{stats ? stats.findings : "–"}</div>
          <div className="stat-label">{t("nav.findings")}</div>
        </div>
      </div>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>{t("dash.bySeverity")}</h3>
        {stats ? (
          <div className="chip-row">
            {SEV_ORDER.map((s) => (
              <span key={s} className={`badge ${SEV_CLASS[s]}`}>
                {s}: <b className="mono">{stats.by_severity[s] ?? 0}</b>
              </span>
            ))}
          </div>
        ) : (
          <p className="muted">{t("common.loading")}</p>
        )}
      </section>

      <section className="card">
        <h2 style={{ marginTop: 0 }}>{t("dash.welcome")}</h2>
        <p className="muted">{t("dash.desc")}</p>
        <Link className="btn" href="/engagements">
          <FolderOpen size={16} /> {t("dash.goEngagements")}
        </Link>
      </section>
    </AppShell>
  );
}
