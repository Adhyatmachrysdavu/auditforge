"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import { useAuth } from "@/lib/auth";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

const SEVERITIES = ["critical", "high", "medium", "low", "info"];
const STATUSES = ["draft", "in_review", "approved", "rejected", "false_positive"];

function sevClass(sev: string): string {
  if (sev === "critical" || sev === "high") return "badge err";
  if (sev === "medium" || sev === "low") return "badge wait";
  return "badge ok";
}

export default function FindingsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  // Basis Pengetahuan memuat data klien lain; hanya auditor/admin yang boleh.
  const canKb = user?.role === "auditor" || user?.role === "admin";

  const [tab, setTab] = useState<"findings" | "knowledge">("findings");
  const [error, setError] = useState<string | null>(null);

  // --- tab Temuan ---
  const [items, setItems] = useState<api.FindingSearchItem[]>([]);
  const [q, setQ] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  // --- tab Basis Pengetahuan ---
  const [entries, setEntries] = useState<api.KnowledgeEntry[]>([]);
  const [kbQ, setKbQ] = useState("");
  const [kbLoading, setKbLoading] = useState(false);
  const [kbFailed, setKbFailed] = useState(false);

  const loadFindings = useCallback(() => {
    setLoading(true);
    setError(null);
    return api
      .searchFindings({ q, severity, status })
      .then((d) => {
        setItems(d.items);
        setLoadFailed(false);
      })
      .catch((err) => {
        setLoadFailed(true);
        setError(err instanceof ApiError ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }, [q, severity, status]);

  const loadKnowledge = useCallback(() => {
    setKbLoading(true);
    setError(null);
    return api
      .listKnowledge(kbQ)
      .then((d) => {
        setEntries(d.items);
        setKbFailed(false);
      })
      .catch((err) => {
        setKbFailed(true);
        setError(err instanceof ApiError ? err.message : String(err));
      })
      .finally(() => setKbLoading(false));
  }, [kbQ]);

  useEffect(() => {
    void loadFindings();
  }, [loadFindings]);

  useEffect(() => {
    if (tab === "knowledge" && canKb) void loadKnowledge();
  }, [tab, canKb, loadKnowledge]);

  return (
    <AppShell title={t("nav.findings")}>
      <section className="card">
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <button
            className={tab === "findings" ? "btn" : "btn secondary"}
            onClick={() => setTab("findings")}
          >
            {t("fsearch.tabFindings")}
          </button>
          {canKb && (
            <button
              className={tab === "knowledge" ? "btn" : "btn secondary"}
              onClick={() => setTab("knowledge")}
            >
              {t("fsearch.tabKnowledge")}
            </button>
          )}
        </div>

        {tab === "findings" ? (
          <>
            <p className="muted" style={{ marginTop: 0 }}>{t("fsearch.subtitle")}</p>
            <div className="form-row">
              <label className="field">
                <span>{t("fsearch.search")}</span>
                <input value={q} onChange={(e) => setQ(e.target.value)} />
              </label>
              <label className="field">
                <span>{t("find.severity")}</span>
                <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  <option value="">{t("fsearch.all")}</option>
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>{t("find.status")}</span>
                <select value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="">{t("fsearch.all")}</option>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </label>
            </div>
            <button
              className="btn secondary"
              onClick={() => {
                setQ("");
                setSeverity("");
                setStatus("");
              }}
            >
              {t("fsearch.reset")}
            </button>
          </>
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>{t("kb.subtitle")}</p>
            <div className="alert ok">{t("kb.warning")}</div>
            <label className="field">
              <span>{t("fsearch.search")}</span>
              <input value={kbQ} onChange={(e) => setKbQ(e.target.value)} />
            </label>
          </>
        )}

        {error && <div className="alert err">{error}</div>}
      </section>

      {tab === "findings" ? (
        <section className="card">
          {loading ? (
            <p className="muted">…</p>
          ) : loadFailed ? (
            <p className="muted">{t("fsearch.loadError")}</p>
          ) : items.length === 0 ? (
            <p className="muted">{t("fsearch.empty")}</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("find.severity")}</th>
                    <th>{t("find.titleCol")}</th>
                    <th>{t("fsearch.colEngagement")}</th>
                    <th>{t("find.priority")}</th>
                    <th>{t("fsearch.colCwe")}</th>
                    <th>{t("find.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((f) => (
                    <tr key={f.id}>
                      <td><span className={sevClass(f.severity)}>{f.severity}</span></td>
                      <td>{f.title}</td>
                      <td>
                        <Link className="link" href={`/engagements/${f.engagement_id}`}>
                          #{f.engagement_id} {f.engagement_name}
                        </Link>
                        <div className="muted mono">{f.client_name}</div>
                      </td>
                      <td className="mono">{f.priority ? `P${f.priority}` : "—"}</td>
                      <td className="mono">{f.cwe ?? "—"}</td>
                      <td className="mono">{f.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : !canKb ? (
        <section className="card">
          <p className="muted">{t("kb.forbidden")}</p>
        </section>
      ) : (
        <section className="card">
          {kbLoading ? (
            <p className="muted">…</p>
          ) : kbFailed ? (
            <p className="muted">{t("kb.loadError")}</p>
          ) : entries.length === 0 ? (
            <p className="muted">{t("kb.empty")}</p>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {entries.map((e) => (
                <div
                  key={e.id}
                  className="card"
                  style={{ background: "var(--surface-2)", marginBottom: 0 }}
                >
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span className={sevClass(e.severity)}>{e.severity}</span>
                    <strong>{e.title}</strong>
                    <span className="mono">{e.cwe ?? "—"}</span>
                    <span className="badge ok">
                      {e.auditor_edited ? t("kb.byAuditor") : t("kb.byAi")}
                    </span>
                  </div>
                  <p className="muted mono" style={{ marginBottom: 4 }}>
                    {t("kb.from")}: #{e.source_engagement_id} {e.source_engagement_name}
                    {" · "}{e.source_client_name}
                    {" · "}{t("kb.used")} {e.usage_count} {t("kb.times")}
                  </p>
                  {e.narrative.description && <p>{e.narrative.description}</p>}
                  {e.narrative.recommendation && (
                    <p className="muted">{e.narrative.recommendation}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </AppShell>
  );
}
