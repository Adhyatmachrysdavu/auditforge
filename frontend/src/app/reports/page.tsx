"use client";

import { useEffect, useState } from "react";
import { FileDoc, FilePdf, Eye } from "@phosphor-icons/react";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

function pct(v: number | null): string {
  return v === null ? "—" : `${Math.round(v * 100)}%`;
}

export default function ReportsPage() {
  const { t, locale } = useI18n();
  const [data, setData] = useState<api.TimingOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getTimingOverview()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : String(err))
      )
      .finally(() => setLoading(false));
  }, []);

  // Galat aksi tombol laporan ditampilkan terpisah dari galat pemuatan tabel,
  // agar kegagalan unduh tidak terbaca sebagai kegagalan memuat data.
  const [actionError, setActionError] = useState<string | null>(null);
  const onActionError = (err: unknown) =>
    setActionError(err instanceof ApiError ? err.message : String(err));

  const items = data?.items ?? [];
  // `data === null` berarti fetch gagal — itu bukan hal yang sama dengan
  // "memang belum ada penugasan", jadi keduanya tidak boleh tampil sama.
  const loadFailed = !loading && data === null;

  return (
    <AppShell title={t("nav.reports")}>
      <section className="card">
        <p className="muted" style={{ marginTop: 0 }}>{t("reports.subtitle")}</p>
        <div className="form-row">
          <div className="field">
            <span>{t("reports.avgSaved")}</span>
            <strong className="mono">{pct(data?.avg_saved_ratio ?? null)}</strong>
          </div>
          <div className="field">
            <span>{t("reports.measured")}</span>
            <strong className="mono">{data?.engagements_measured ?? 0}</strong>
          </div>
          <div className="field">
            <span>{t("reports.totalEngagements")}</span>
            <strong className="mono">{items.length}</strong>
          </div>
        </div>
        <p className="muted" style={{ fontSize: "0.78rem", marginBottom: 0 }}>
          {t("reports.measuredHint")}
        </p>
        {error && <div className="alert err">{error}</div>}
        {actionError && <div className="alert err">{actionError}</div>}
      </section>

      <section className="card">
        {loading ? (
          <p className="muted">{t("reports.loading")}</p>
        ) : loadFailed ? (
          <p className="muted">{t("reports.loadFailed")}</p>
        ) : items.length === 0 ? (
          <p className="muted">{t("reports.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t("reports.colEngagement")}</th>
                  <th>{t("reports.colClient")}</th>
                  <th>{t("reports.colActive")}</th>
                  <th>{t("reports.colBaseline")}</th>
                  <th>{t("reports.colSaved")}</th>
                  <th>{t("reports.colActions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.engagement_id}>
                    <td className="mono">{r.engagement_id}</td>
                    <td>{r.name}</td>
                    <td>{r.client_name}</td>
                    <td className="mono">
                      {r.active_hours} {t("reports.hours")}
                    </td>
                    <td className="mono">
                      {r.baseline_hours === null ? (
                        <span className="muted">{t("reports.noBaseline")}</span>
                      ) : (
                        `${r.baseline_hours} ${t("reports.hours")}`
                      )}
                    </td>
                    <td className="mono">
                      {r.measurable ? (
                        pct(r.saved_ratio)
                      ) : (
                        <span className="muted">{t("reports.notMeasurable")}</span>
                      )}
                    </td>
                    <td>
                      <button
                        className="btn secondary"
                        onClick={() =>
                          api
                            .previewReport(r.engagement_id, "approved", locale)
                            .catch(onActionError)
                        }
                      >
                        <Eye size={14} /> {t("report.preview")}
                      </button>{" "}
                      <button
                        className="btn secondary"
                        onClick={() =>
                          api
                            .downloadReportDocx(r.engagement_id, "approved", locale)
                            .catch(onActionError)
                        }
                      >
                        <FileDoc size={14} /> DOCX
                      </button>{" "}
                      <button
                        className="btn secondary"
                        onClick={() =>
                          api
                            .downloadReportPdf(r.engagement_id, "approved", locale)
                            .catch(onActionError)
                        }
                      >
                        <FilePdf size={14} /> PDF
                      </button>
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
