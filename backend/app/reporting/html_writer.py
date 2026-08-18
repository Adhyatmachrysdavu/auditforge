"""Render laporan ke HTML (D16) via Jinja2 — untuk pratinjau & sumber PDF.

Menyematkan grafik SVG (distribusi severity + matriks risiko) dan lampiran bukti
gambar (data URI). HTML ini dipakai apa adanya untuk pratinjau di browser dan
sebagai masukan WeasyPrint untuk PDF (lihat `pdf_writer`).
"""
from __future__ import annotations

from jinja2 import Environment, select_autoescape

from app.reporting.charts import matrix_from, risk_matrix_svg, severity_bar_svg
from app.reporting.report_data import ReportData

_LABELS = {
    "id": {
        "client": "Klien", "prepared_by": "Disiapkan oleh", "generated": "Dibuat",
        "period": "Periode", "scope": "Cakupan",
        "posture": "Postur Keamanan", "exec_summary": "Ringkasan Eksekutif",
        "overview": "Gambaran Umum", "key_risks": "Risiko Utama",
        "recommendations": "Rekomendasi", "findings": "Temuan",
        "sev_dist": "Distribusi Keparahan", "risk_matrix": "Matriks Risiko",
        "description": "Deskripsi", "impact": "Dampak", "recommendation": "Rekomendasi",
        "evidence": "Bukti", "edited": "disunting auditor",
        "empty": "Tidak ada temuan disetujui untuk dilaporkan.",
        "confidential": "RAHASIA — hanya untuk penerima yang berwenang.",
        "rem_fixed": "Tertutup", "rem_open": "Masih terbuka",
        "rem_recurring": "Kambuh", "rem_not_tested": "Belum diuji",
        "remediation_summary": (
            "{fixed} dari {total} temuan telah tertutup dan diverifikasi "
            "(Putaran {round})."
        ),
    },
    "en": {
        "client": "Client", "prepared_by": "Prepared by", "generated": "Generated",
        "period": "Period", "scope": "Scope",
        "posture": "Security Posture", "exec_summary": "Executive Summary",
        "overview": "Overview", "key_risks": "Key Risks",
        "recommendations": "Recommendations", "findings": "Findings",
        "sev_dist": "Severity Distribution", "risk_matrix": "Risk Matrix",
        "description": "Description", "impact": "Impact", "recommendation": "Recommendation",
        "evidence": "Evidence", "edited": "edited by auditor",
        "empty": "No approved findings to report.",
        "confidential": "CONFIDENTIAL — for authorized recipients only.",
        "rem_fixed": "Closed", "rem_open": "Still open",
        "rem_recurring": "Recurring", "rem_not_tested": "Not tested",
        "remediation_summary": (
            "{fixed} of {total} findings have been closed and verified "
            "(Round {round})."
        ),
    },
}
_POSTURE = {
    "id": {"critical": "Kritis", "elevated": "Tinggi", "moderate": "Sedang",
           "low": "Rendah", "clean": "Bersih"},
    "en": {"critical": "Critical", "elevated": "Elevated", "moderate": "Moderate",
           "low": "Low", "clean": "Clean"},
}

_TEMPLATE = """<!doctype html>
<html lang="{{ lang }}"><head><meta charset="utf-8">
<title>{{ data.report_title }} — {{ data.engagement_name }}</title>
<style>
  @page { size: A4; margin: 2cm; @bottom-center { content: "{{ L.confidential }}";
    font-size: 9px; color: #94a3b8; } }
  body { font-family: 'DejaVu Sans', sans-serif; color: #1e293b; font-size: 12px;
    line-height: 1.5; }
  .org { color: {{ accent }}; font-weight: bold; font-size: 12px; }
  h1 { color: {{ accent }}; font-size: 26px; margin: 4px 0 2px; }
  h2 { color: {{ accent }}; font-size: 17px; border-bottom: 2px solid {{ accent }};
    padding-bottom: 3px; margin-top: 22px; }
  h3 { font-size: 14px; margin: 16px 0 4px; }
  .meta { color: #475569; margin: 2px 0; }
  .badge { display: inline-block; padding: 1px 8px; border-radius: 10px; color: #fff;
    font-size: 11px; font-weight: bold; }
  .charts { display: flex; gap: 28px; flex-wrap: wrap; margin: 10px 0; }
  .chart-box h3 { margin-top: 0; }
  .fmeta { color: #475569; font-size: 11px; margin: 2px 0 6px; }
  .lbl { font-weight: bold; }
  .finding { margin-bottom: 14px; page-break-inside: avoid; }
  .evi { margin-top: 6px; }
  .evi img { max-width: 460px; max-height: 320px; border: 1px solid #cbd5e1;
    border-radius: 6px; margin: 4px 6px 0 0; }
  .muted { color: #94a3b8; }
  .rem { font-weight: bold; }
  .rem-fixed { color: #16a34a; }
  .rem-open { color: #d97706; }
  .rem-recurring { color: #dc2626; }
  /* Peringatan ringkasan basi: harus terlihat, tapi tidak menyaingi isi laporan. */
  .stale-note { background: #fef3c7; border-left: 3px solid #d97706;
                padding: 6px 10px; color: #92400e; font-size: 0.92em; }
</style></head><body>
  <div class="org">{{ data.org_name }}</div>
  <h1>{{ data.report_title }}</h1>
  <div class="meta"><strong>{{ data.engagement_name }}</strong></div>
  <div class="meta">{{ L.client }}: {{ data.client_name }}</div>
  {% if data.period %}<div class="meta">{{ L.period }}: {{ data.period }}</div>{% endif %}
  {% if data.scope %}<div class="meta">{{ L.scope }}: {{ data.scope }}</div>{% endif %}
  <div class="meta">{{ L.prepared_by }}: {{ data.org_name }}</div>
  <div class="meta">{{ L.generated }}: {{ data.generated_at }}</div>
  {% if data.posture %}<div class="meta">{{ L.posture }}:
    <span class="badge" style="background:{{ posture_color }}">{{ posture_label }}</span></div>{% endif %}

  <div class="charts">
    <div class="chart-box"><h3>{{ L.sev_dist }}</h3>{{ severity_svg | safe }}</div>
    <div class="chart-box"><h3>{{ L.risk_matrix }}</h3>{{ matrix_svg | safe }}</div>
  </div>

  {% if data.current_round > 1 %}
    <p>{{ L.remediation_summary.format(
      fixed=data.remediation_counts.get('fixed', 0),
      total=data.total, round=data.current_round) }}</p>
  {% endif %}

  {% if data.summary_overview or data.summary_key_risks or data.summary_recommendations %}
  <h2>{{ L.exec_summary }}</h2>
  {% if data.summary_stale_note %}<p class="stale-note">⚠ {{ data.summary_stale_note }}</p>{% endif %}
  {% if data.summary_overview %}<p><span class="lbl">{{ L.overview }}:</span> {{ data.summary_overview }}</p>{% endif %}
  {% if data.summary_key_risks %}<p><span class="lbl">{{ L.key_risks }}:</span> {{ data.summary_key_risks }}</p>{% endif %}
  {% if data.summary_recommendations %}<p><span class="lbl">{{ L.recommendations }}:</span> {{ data.summary_recommendations }}</p>{% endif %}
  {% endif %}

  <h2>{{ L.findings }} ({{ data.total }})</h2>
  {% if not data.findings %}<p class="muted">{{ L.empty }}</p>{% endif %}
  {% for f in data.findings %}
  <div class="finding">
    <h3>{{ loop.index }}. {{ f.title }}
      <span class="badge" style="background:{{ sev_color(f.severity) }}">{{ f.severity }}</span></h3>
    <div class="fmeta">
      {% if f.priority %}P{{ f.priority }} · {% endif %}
      {% if data.current_round > 1 and f.remediation %}
        · <span class="rem rem-{{ f.remediation }}">{{ L['rem_' + f.remediation] }}</span>
      {% endif %}
      {% if f.cvss_score is not none %}CVSS {{ f.cvss_score }} · {% endif %}
      {% if f.cwe %}{{ f.cwe }} · {% endif %}
      {% if f.owasp %}{{ f.owasp }} · {% endif %}
      {% if f.cve %}{{ f.cve | join(", ") }} · {% endif %}
      {{ f.status }}{% if f.edited %} ({{ L.edited }}){% endif %}
    </div>
    <p><span class="lbl">{{ L.description }}:</span> {{ f.description or "—" }}</p>
    <p><span class="lbl">{{ L.impact }}:</span> {{ f.impact or "—" }}</p>
    <p><span class="lbl">{{ L.recommendation }}:</span> {{ f.recommendation or "—" }}</p>
    {% if f.evidence %}
    <div class="evi"><span class="lbl">{{ L.evidence }}:</span><br>
      {% for uri in f.evidence %}<img src="{{ uri }}" alt="evidence">{% endfor %}
    </div>{% endif %}
  </div>
  {% endfor %}
</body></html>"""


def render_html(data: ReportData, *, accent: str = "#1E5F9F", lang: str = "id") -> str:
    lg = lang if lang in _LABELS else "id"
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    from app.reporting.charts import _SEV_COLOR

    tmpl = env.from_string(_TEMPLATE)
    severity_svg = severity_bar_svg(data.severity_counts)
    matrix_svg = risk_matrix_svg(
        matrix_from([(f.severity, f.priority) for f in data.findings])
    )
    posture_color = _SEV_COLOR.get(
        {"critical": "critical", "elevated": "high", "moderate": "medium",
         "low": "low", "clean": "info"}.get(data.posture or "", "info"),
        "#16a34a",
    )
    return tmpl.render(
        data=data,
        L=_LABELS[lg],
        lang=lg,
        accent=accent,
        severity_svg=severity_svg,
        matrix_svg=matrix_svg,
        sev_color=lambda s: _SEV_COLOR.get((s or "").lower(), "#64748b"),
        posture_color=posture_color,
        posture_label=_POSTURE[lg].get(data.posture or "", data.posture or ""),
    )
