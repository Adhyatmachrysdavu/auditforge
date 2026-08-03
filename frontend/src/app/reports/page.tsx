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
  const { t } = useI18n();
  const [data, setData] = useState<api.TimingOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getTimingOverview()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, []);

  const items = data?.items ?? [];

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
        {error && <div className="alert err">{error}</div>}
      </section>

      <section className="card">
        {items.length === 0 ? (
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
                    <td className="mono">{pct(r.saved_ratio)}</td>
                    <td>
                      <button
                        className="btn ghost"
                        onClick={() => api.previewReport(r.engagement_id)}
                      >
                        <Eye size={14} /> {t("report.preview")}
                      </button>{" "}
                      <button
                        className="btn ghost"
                        onClick={() => api.downloadReportDocx(r.engagement_id)}
                      >
                        <FileDoc size={14} /> DOCX
                      </button>{" "}
                      <button
                        className="btn ghost"
                        onClick={() => api.downloadReportPdf(r.engagement_id)}
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
