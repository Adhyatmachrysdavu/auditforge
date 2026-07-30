"use client";

import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n/LocaleProvider";

export default function ReportsPage() {
  const { t } = useI18n();
  return (
    <AppShell title={t("nav.reports")}>
      <section className="card">
        <p className="muted">{t("placeholder.soon")}</p>
      </section>
    </AppShell>
  );
}
