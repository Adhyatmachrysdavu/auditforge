"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowClockwise } from "@phosphor-icons/react";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function IngestPage() {
  const { t } = useI18n();
  const [data, setData] = useState<api.IngestOverview | null>(null);
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return api
      .getIngest(onlyFailed ? "failed" : undefined)
      .then((d) => {
        setData(d);
        setLoadFailed(false);
      })
      .catch((err) => {
        setLoadFailed(true);
        setError(err instanceof ApiError ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }, [onlyFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  async function reparse(item: api.IngestItem) {
    setBusyId(item.upload_id);
    setError(null);
    try {
      await api.reparseUpload(item.engagement_id, item.upload_id);
      // Parsing berjalan asinkron di worker; beri jeda sebelum memuat ulang.
      // Tombol tetap terkunci sampai pemuatan ulang selesai — dilepas lebih awal,
      // klik kedua mengenai baris yang statusnya sudah `uploaded` dan hanya
      // menghasilkan 409 yang membingungkan.
      setTimeout(() => {
        void load().finally(() => setBusyId(null));
      }, 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setBusyId(null);
    }
  }

  const items = data?.items ?? [];

  return (
    <AppShell title={t("nav.ingest")}>
      <section className="card">
        <p className="muted" style={{ marginTop: 0 }}>{t("ingest.subtitle")}</p>
        <div className="form-row">
          <div className="field">
            <span>{t("ingest.today")}</span>
            <strong className="mono">{data?.summary.today ?? 0}</strong>
          </div>
          <div className="field">
            <span>{t("ingest.failed")}</span>
            <strong className="mono">{data?.summary.failed ?? 0}</strong>
          </div>
          <div className="field">
            <span>{t("ingest.total")}</span>
            <strong className="mono">{data?.summary.total ?? 0}</strong>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button
            className={onlyFailed ? "btn secondary" : "btn"}
            onClick={() => setOnlyFailed(false)}
          >
            {t("ingest.filterAll")}
          </button>
          <button
            className={onlyFailed ? "btn" : "btn secondary"}
            onClick={() => setOnlyFailed(true)}
          >
            {t("ingest.filterFailed")}
          </button>
        </div>
        {error && <div className="alert err">{error}</div>}
      </section>

      <section className="card">
        {loading ? (
          <p className="muted">…</p>
        ) : loadFailed ? (
          <p className="muted">{t("ingest.loadError")}</p>
        ) : items.length === 0 ? (
          <p className="muted">{t("ingest.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("ingest.colTime")}</th>
                  <th>{t("ingest.colEngagement")}</th>
                  <th>{t("ingest.colFile")}</th>
                  <th>{t("ingest.colTool")}</th>
                  <th>{t("ingest.colSource")}</th>
                  <th>{t("ingest.colStatus")}</th>
                  <th>{t("ingest.colAction")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.upload_id}>
                    <td className="mono">{fmtTime(it.created_at)}</td>
                    <td>
                      <Link className="link" href={`/engagements/${it.engagement_id}`}>
                        #{it.engagement_id} {it.engagement_name}
                      </Link>
                    </td>
                    <td>{it.filename}</td>
                    <td className="mono">{it.tool}</td>
                    <td className="mono">
                      {it.source === "manual"
                        ? t("ingest.sourceManual")
                        : t("ingest.sourceWatcher")}
                    </td>
                    <td>
                      <span
                        className={`badge ${it.status === "parsed" ? "ok" : it.status === "failed" ? "err" : "wait"}`}
                        title={it.error ?? ""}
                      >
                        {it.status}
                      </span>
                    </td>
                    <td>
                      {it.can_reparse && (
                        <button
                          className="btn secondary"
                          disabled={busyId === it.upload_id}
                          onClick={() => reparse(it)}
                        >
                          <ArrowClockwise size={14} />{" "}
                          {busyId === it.upload_id
                            ? t("ingest.reparsing")
                            : t("ingest.reparse")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppShell>
  );
}
