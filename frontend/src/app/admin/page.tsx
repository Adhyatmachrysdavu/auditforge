"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import { useAuth } from "@/lib/auth";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

const FORMATS = ["openai", "anthropic"];

export default function AdminPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [cfg, setCfg] = useState<api.LlmConfig | null>(null);
  const [format, setFormat] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [testResult, setTestResult] = useState<api.LlmTestResult | null>(null);
  // --- D15: branding laporan ---
  const [brand, setBrand] = useState<api.Branding>({
    org_name: "",
    report_title: "",
    accent: "#1E5F9F",
  });
  const [brandBusy, setBrandBusy] = useState(false);
  const [brandSaved, setBrandSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const c = await api.getLlmConfig();
      setCfg(c);
      setFormat(c.format);
      setBaseUrl(c.base_url);
      setModel(c.model);
      setBrand(await api.getBranding());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  async function saveBranding(e: React.FormEvent) {
    e.preventDefault();
    setBrandBusy(true);
    setError(null);
    setBrandSaved(false);
    try {
      setBrand(await api.updateBranding(brand));
      setBrandSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBrandBusy(false);
    }
  }

  // --- D17: transparansi masking + jejak audit ---
  const [maskInput, setMaskInput] = useState(
    "Server 10.1.2.3 (db.internal.local) password=Rahasia123 kontak admin@corp.local"
  );
  const [maskOutput, setMaskOutput] = useState<string | null>(null);
  const [maskBusy, setMaskBusy] = useState(false);
  const [audit, setAudit] = useState<api.AuditLogRow[]>([]);

  async function runMasking() {
    setMaskBusy(true);
    setError(null);
    try {
      const r = await api.previewMasking(maskInput);
      setMaskOutput(r.masked);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setMaskBusy(false);
    }
  }

  async function loadAudit() {
    setError(null);
    try {
      setAudit(await api.getAuditLogs(50));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin, load]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const payload: Record<string, string> = { format, base_url: baseUrl, model };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      const c = await api.updateLlmConfig(payload);
      setCfg(c);
      setApiKey("");
      setSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    setTestResult(null);
    setError(null);
    try {
      setTestResult(await api.testLlmConnection());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!isAdmin) {
    return (
      <AppShell title={t("nav.admin")}>
        <section className="card">
          <p className="muted">{t("admin.onlyAdmin")}</p>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell title={t("nav.admin")}>
      <section className="card">
        <h2 style={{ marginTop: 0 }}>{t("admin.llmTitle")}</h2>
        <p className="muted">{t("admin.llmDesc")}</p>

        {error && <div className="alert err">{error}</div>}
        {saved && <div className="alert ok">{t("admin.saved")}</div>}

        <form onSubmit={save}>
          <div className="form-row">
            <label className="field">
              <span>{t("admin.format")}</span>
              <select value={format} onChange={(e) => setFormat(e.target.value)}>
                {FORMATS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>
            <label className="field" style={{ flex: "2 1 260px" }}>
              <span>{t("admin.baseUrl")}</span>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://openrouter.ai/api/v1"
              />
            </label>
          </div>
          <div className="form-row">
            <label className="field" style={{ flex: "2 1 260px" }}>
              <span>{t("admin.model")}</span>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="openrouter/free"
              />
            </label>
            <label className="field" style={{ flex: "2 1 260px" }}>
              <span>{t("admin.apiKey")}</span>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  cfg?.api_key_set
                    ? `${cfg.api_key_masked} — ${t("admin.keyKeep")}`
                    : t("admin.keyEmpty")
                }
                autoComplete="off"
              />
            </label>
          </div>
          <div className="chip-row" style={{ marginTop: 14 }}>
            <button className="btn" type="submit" disabled={busy}>
              {busy ? t("common.loading") : t("admin.save")}
            </button>
            <button className="btn secondary" type="button" onClick={test} disabled={busy}>
              {t("admin.test")}
            </button>
          </div>
        </form>

        {testResult && (
          <div
            className={`alert ${testResult.status === "ok" ? "ok" : "err"}`}
            style={{ marginTop: 14 }}
          >
            <strong>{testResult.status.toUpperCase()}</strong> — {testResult.provider} /{" "}
            {testResult.model}
            {testResult.detail ? ` · ${testResult.detail}` : ""}
          </div>
        )}
      </section>

      <section className="card">
        <h2 style={{ marginTop: 0 }}>{t("brand.title")}</h2>
        <p className="muted">{t("brand.desc")}</p>
        {brandSaved && <div className="alert ok">{t("brand.saved")}</div>}
        <form onSubmit={saveBranding}>
          <div className="form-row">
            <label className="field" style={{ flex: "2 1 260px" }}>
              <span>{t("brand.org")}</span>
              <input
                value={brand.org_name}
                onChange={(e) => setBrand({ ...brand, org_name: e.target.value })}
              />
            </label>
            <label className="field" style={{ flex: "2 1 260px" }}>
              <span>{t("brand.reportTitle")}</span>
              <input
                value={brand.report_title}
                onChange={(e) => setBrand({ ...brand, report_title: e.target.value })}
              />
            </label>
            <label className="field">
              <span>{t("brand.accent")}</span>
              <input
                value={brand.accent}
                onChange={(e) => setBrand({ ...brand, accent: e.target.value })}
                placeholder="#1E5F9F"
              />
            </label>
          </div>
          <div className="chip-row" style={{ marginTop: 14 }}>
            <button className="btn" type="submit" disabled={brandBusy}>
              {brandBusy ? t("common.loading") : t("brand.save")}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2 style={{ marginTop: 0 }}>{t("mask.title")}</h2>
        <p className="muted">{t("mask.desc")}</p>
        <label className="field">
          <span>{t("mask.input")}</span>
          <textarea
            rows={3}
            value={maskInput}
            onChange={(e) => setMaskInput(e.target.value)}
          />
        </label>
        <div className="chip-row" style={{ marginTop: 12 }}>
          <button className="btn" type="button" onClick={runMasking} disabled={maskBusy}>
            {maskBusy ? t("common.loading") : t("mask.run")}
          </button>
        </div>
        {maskOutput !== null && (
          <div style={{ marginTop: 12 }}>
            <div className="muted" style={{ fontSize: "0.8rem", marginBottom: 4 }}>
              {t("mask.output")}
            </div>
            <pre
              className="mono"
              style={{
                whiteSpace: "pre-wrap",
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 10,
                margin: 0,
              }}
            >
              {maskOutput}
            </pre>
          </div>
        )}
      </section>

      <section className="card">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <div>
            <h2 style={{ margin: 0 }}>{t("audit.title")}</h2>
            <p className="muted" style={{ margin: "4px 0 0" }}>
              {t("audit.desc")}
            </p>
          </div>
          <button className="btn secondary" type="button" onClick={loadAudit}>
            {t("audit.refresh")}
          </button>
        </div>
        {audit.length === 0 ? (
          <p className="muted" style={{ marginTop: 12 }}>
            {t("audit.empty")}
          </p>
        ) : (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t("login.email")}</th>
                  <th>Method</th>
                  <th>Path</th>
                  <th>Status</th>
                  <th>{t("find.status")}</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((r) => (
                  <tr key={r.id}>
                    <td className="mono">{r.id}</td>
                    <td className="mono">{r.user_id ?? "—"}</td>
                    <td className="mono">{r.method}</td>
                    <td className="mono" style={{ maxWidth: 320, overflow: "hidden" }}>
                      {r.path}
                    </td>
                    <td className="mono">{r.status_code ?? "—"}</td>
                    <td className="mono muted">
                      {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
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
