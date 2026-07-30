"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Translate } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/i18n/LocaleProvider";
import { ApiError } from "@/lib/api";
import { LOCALE_LABEL } from "@/i18n/messages";

export default function LoginPage() {
  const { user, signIn } = useAuth();
  const { t, locale, toggleLocale } = useI18n();
  const router = useRouter();
  const [email, setEmail] = useState("admin@auditforge.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace("/");
  }, [user, router]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("login.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <ShieldCheck size={28} weight="fill" /> AuditForge
        </div>
        <p className="muted" style={{ marginTop: 0 }}>
          {t("login.subtitle")}
        </p>

        <label className="field">
          <span>{t("login.email")}</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="username"
          />
        </label>
        <label className="field">
          <span>{t("login.password")}</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>

        {error && <div className="alert err">{error}</div>}

        <button className="btn" type="submit" disabled={busy}>
          {busy ? t("login.loading") : t("login.submit")}
        </button>

        <button
          type="button"
          className="btn ghost auth-lang"
          onClick={toggleLocale}
          title="Bahasa / Language"
        >
          <Translate size={15} weight="fill" /> {LOCALE_LABEL[locale]}
        </button>
      </form>
    </div>
  );
}
