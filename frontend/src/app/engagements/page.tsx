"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, ArrowRight } from "@phosphor-icons/react";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

export default function EngagementsPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<api.Engagement[]>([]);
  const [name, setName] = useState("");
  const [client, setClient] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.listEngagements().then(setItems).catch(() => {});
  }
  useEffect(load, []);

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createEngagement({ name, client_name: client });
      setName("");
      setClient("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title={t("nav.engagements")}>
      <section className="card">
        <h3 style={{ marginTop: 0 }}>{t("eng.newTitle")}</h3>
        <form className="form-row" onSubmit={create}>
          <label className="field">
            <span>{t("eng.name")}</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="field">
            <span>{t("eng.client")}</span>
            <input value={client} onChange={(e) => setClient(e.target.value)} required />
          </label>
          <button className="btn" disabled={busy}>
            <Plus size={16} /> {t("eng.create")}
          </button>
        </form>
        {error && <div className="alert err">{error}</div>}
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>{t("eng.listTitle")}</h3>
        {items.length === 0 ? (
          <p className="muted">{t("eng.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t("eng.name")}</th>
                  <th>{t("eng.client")}</th>
                  <th>{t("eng.status")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((e) => (
                  <tr key={e.id}>
                    <td className="mono">{e.id}</td>
                    <td>{e.name}</td>
                    <td>{e.client_name}</td>
                    <td>
                      <span className="badge wait">{e.status}</span>
                    </td>
                    <td>
                      <Link className="link" href={`/engagements/${e.id}`}>
                        {t("eng.open")} <ArrowRight size={14} />
                      </Link>
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
