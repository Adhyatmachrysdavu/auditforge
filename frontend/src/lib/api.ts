// Klien API AuditForge — satu tempat untuk semua panggilan ke backend.
// Token JWT disimpan di localStorage; setiap permintaan menyertakan Authorization.

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const TOKEN_KEY = "af-token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* localStorage tak tersedia — abaikan */
  }
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) {
    setToken(null);
    throw new ApiError(401, "Sesi berakhir, silakan masuk lagi");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* body bukan JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

// ---------- Tipe ----------
export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}
export interface Engagement {
  id: number;
  name: string;
  client_name: string;
  description: string | null;
  status: string;
  created_by: number | null;
}
export interface ExecSummary {
  overview?: string;
  key_risks?: string;
  recommendations?: string;
  posture?: string;
}
export interface EngagementDetail extends Engagement {
  exec_summary_generated: boolean;
  exec_summary_model: string | null;
  exec_summary_prompt_version: string | null;
  exec_summary: ExecSummary | null;
  baseline_hours: number | null;
  baseline_note: string | null;
  // --- Modul 2: kelengkapan penugasan ---
  scope: string | null;
  period_start: string | null;
  period_end: string | null;
  kb_shareable: boolean;
}
export interface ScanUpload {
  id: number;
  engagement_id: number;
  filename: string;
  tool: string;
  status: string;
  error: string | null;
  /** Diputuskan server; jangan menurunkan ulang aturannya di antarmuka. */
  can_reparse: boolean;
}
export interface Finding {
  id: number;
  engagement_id: number;
  source_upload_id: number | null;
  title: string;
  severity: string;
  status: string;
  cwe: string | null;
  cvss_score: number | null;
  owasp: string | null;
  cve: string[];
  occurrences: number;
  tools: string[];
  ai_generated: boolean;
  priority: number | null;
  priority_score: number | null;
}
export interface Narrative {
  description?: string;
  impact?: string;
  recommendation?: string;
}
export interface FindingDetail extends Finding {
  description: string | null;
  cvss_vector: string | null;
  ai_model: string | null;
  ai_prompt_version: string | null;
  ai_draft: Narrative | null;
  final_narrative: Narrative | null;
  narrative_edited: boolean;
  reviewed_by: number | null;
  reviewed_at: string | null;
}
export interface FindingRevision {
  id: number;
  action: string;
  status: string;
  narrative: Narrative | null;
  note: string | null;
  author_id: number | null;
  created_at: string | null;
}
export interface Attachment {
  id: number;
  finding_id: number;
  filename: string;
  content_type: string;
  size: number;
  uploaded_by: number | null;
  created_at: string | null;
}
export interface Stats {
  engagements: number;
  uploads: number;
  findings: number;
  by_severity: Record<string, number>;
}

// ---------- Panggilan ----------
export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    let detail = "Login gagal";
    try {
      const b = await res.json();
      if (b?.detail) detail = b.detail;
    } catch {
      /* abaikan */
    }
    throw new ApiError(res.status, detail);
  }
  const data = (await res.json()) as { access_token: string };
  setToken(data.access_token);
}

export const getMe = () => req<User>("/auth/me");
export const listEngagements = () => req<Engagement[]>("/engagements");
export const createEngagement = (payload: {
  name: string;
  client_name: string;
  description?: string;
}) =>
  req<Engagement>("/engagements", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const listUploads = (id: number) => req<ScanUpload[]>(`/engagements/${id}/uploads`);
export const listFindings = (id: number) => req<Finding[]>(`/engagements/${id}/findings`);
export const getFinding = (id: number, fid: number) =>
  req<FindingDetail>(`/engagements/${id}/findings/${fid}`);
export const editNarrative = (
  id: number,
  fid: number,
  body: { description: string; impact: string; recommendation: string; note?: string }
) =>
  req<FindingDetail>(`/engagements/${id}/findings/${fid}/narrative`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const changeFindingStatus = (
  id: number,
  fid: number,
  body: { status: string; note?: string }
) =>
  req<FindingDetail>(`/engagements/${id}/findings/${fid}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const getRevisions = (id: number, fid: number) =>
  req<FindingRevision[]>(`/engagements/${id}/findings/${fid}/revisions`);

// ---------- D14: lampiran bukti ----------
export const listAttachments = (id: number, fid: number) =>
  req<Attachment[]>(`/engagements/${id}/findings/${fid}/attachments`);
export function uploadAttachment(id: number, fid: number, file: File): Promise<Attachment> {
  const fd = new FormData();
  fd.append("file", file);
  return req<Attachment>(`/engagements/${id}/findings/${fid}/attachments`, {
    method: "POST",
    body: fd,
  });
}
export const deleteAttachment = (id: number, fid: number, aid: number) =>
  req<null>(`/engagements/${id}/findings/${fid}/attachments/${aid}`, { method: "DELETE" });
export async function downloadAttachment(
  id: number,
  fid: number,
  aid: number,
  filename: string
): Promise<void> {
  const token = getToken();
  const res = await fetch(
    `${BASE}/engagements/${id}/findings/${fid}/attachments/${aid}/download`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  );
  if (!res.ok) throw new ApiError(res.status, "Gagal mengunduh lampiran");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
export const generateNarratives = (id: number, lang = "id") =>
  req<{ queued: number; skipped: number }>(
    `/engagements/${id}/generate-narratives?lang=${encodeURIComponent(lang)}`,
    { method: "POST" }
  );
export const getEngagement = (id: number) =>
  req<EngagementDetail>(`/engagements/${id}`);
export const generateExecSummary = (id: number, lang = "id") =>
  req<{ queued: boolean; findings: number }>(
    `/engagements/${id}/exec-summary?lang=${encodeURIComponent(lang)}`,
    { method: "POST" }
  );
export const recomputeTriage = (id: number) =>
  req<{ triaged: number }>(`/engagements/${id}/triage`, { method: "POST" });
export const getStats = () => req<Stats>("/stats");

// ---------- D15: laporan DOCX ----------
export async function downloadReportDocx(
  id: number,
  include: "approved" | "all" = "approved",
  lang = "id"
): Promise<void> {
  const token = getToken();
  const res = await fetch(
    `${BASE}/engagements/${id}/report.docx?include=${include}&lang=${encodeURIComponent(lang)}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  );
  if (!res.ok) throw new ApiError(res.status, "Gagal mengunduh laporan");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `AuditForge_report_${id}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function _fetchReport(id: number, ext: "pdf" | "html", include: string, lang: string) {
  const token = getToken();
  const res = await fetch(
    `${BASE}/engagements/${id}/report.${ext}?include=${include}&lang=${encodeURIComponent(lang)}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  );
  if (!res.ok) throw new ApiError(res.status, "Gagal membuat laporan");
  return res.blob();
}

export async function downloadReportPdf(
  id: number,
  include: "approved" | "all" = "approved",
  lang = "id"
): Promise<void> {
  const blob = await _fetchReport(id, "pdf", include, lang);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `AuditForge_report_${id}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function previewReport(
  id: number,
  include: "approved" | "all" = "approved",
  lang = "id"
): Promise<void> {
  const blob = await _fetchReport(id, "html", include, lang);
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  // Biarkan tab memuat sebelum dicabut.
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

// ---------- D15: branding laporan (admin) ----------
export interface Branding {
  org_name: string;
  report_title: string;
  accent: string;
}
export const getBranding = () => req<Branding>("/admin/branding");
export const updateBranding = (payload: Partial<Branding>) =>
  req<Branding>("/admin/branding", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

// ---------- D17: evaluasi terukur ----------
export interface Evaluation {
  total_findings: number;
  raw_findings: number;
  duplicates_merged: number;
  dedup_reduction: number;
  ai_drafts: number;
  ai_coverage: number;
  edited_by_auditor: number;
  edited_ratio: number;
  decided: number;
  approved: number;
  review_progress: number;
  tools_used: string[];
  severity_distribution: Record<string, number>;
  priority_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
}
export const getEvaluation = (id: number) =>
  req<Evaluation>(`/engagements/${id}/evaluation`);

// ---------- Modul 1: metrik waktu penyusunan ----------
export interface Timing {
  event_count: number;
  /** Revisi yang ditulis auditor (author_id terisi). */
  human_event_count: number;
  /** Revisi yang ditulis worker AI (author_id null) — draf naratif. */
  ai_event_count: number;
  first_at: string | null;
  last_at: string | null;
  calendar_seconds: number;
  /** Waktu aktif seluruh jejak, termasuk latensi worker AI. Untuk transparansi. */
  active_seconds: number;
  active_hours: number;
  /** Waktu aktif manusia saja — inilah dasar klaim penghematan. */
  active_seconds_human: number;
  active_hours_human: number;
  events_by_action: Record<string, number>;
  /** false bila kerja manusia kurang dari dua stempel waktu — tak ada klaim yang sah. */
  measurable: boolean;
  baseline_hours: number | null;
  saved_hours: number | null;
  saved_ratio: number | null;
}
export interface TimingRow extends Timing {
  engagement_id: number;
  name: string;
  client_name: string;
  status: string;
}
export interface TimingOverview {
  items: TimingRow[];
  engagements_measured: number;
  avg_saved_ratio: number | null;
}
export const getTiming = (id: number) => req<Timing>(`/engagements/${id}/timing`);
export const getTimingOverview = () => req<TimingOverview>("/stats/timing");
export const setBaseline = (
  id: number,
  baseline_hours: number | null,
  baseline_note: string | null
) =>
  req<{ baseline_hours: number | null; baseline_note: string | null }>(
    `/engagements/${id}/baseline`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ baseline_hours, baseline_note }),
    }
  );

// ---------- Modul 2: anggota tim & kelengkapan penugasan ----------
export interface Member {
  user_id: number;
  email: string;
  full_name: string;
  /** Peran RBAC aplikasi: admin | auditor | analyst. */
  role: string;
  /** Peran di dalam tim: lead | member. */
  role_in_team: string;
}
export interface EngagementDetails {
  scope: string | null;
  period_start: string | null;
  period_end: string | null;
  kb_shareable: boolean;
}
export const listMembers = (id: number) =>
  req<Member[]>(`/engagements/${id}/members`);
export const addMember = (id: number, user_id: number, role_in_team = "member") =>
  req<Member>(`/engagements/${id}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id, role_in_team }),
  });
export const removeMember = (id: number, userId: number) =>
  req<null>(`/engagements/${id}/members/${userId}`, { method: "DELETE" });
export const saveEngagementDetails = (id: number, d: EngagementDetails) =>
  req<EngagementDetails>(`/engagements/${id}/details`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(d),
  });
// Belum ada fungsi apa pun untuk /users di klien ini — dropdown anggota
// membutuhkannya, jadi ditambahkan di sini.
export const listUsers = () => req<User[]>("/users");

export interface DiffSection {
  before: string;
  after: string;
  added: string[];
  removed: string[];
  changed_ratio: number;
}
export interface NarrativeDiff {
  sections: Record<string, DiffSection>;
  /** Porsi kata yang diubah auditor, ditimbang panjang tiap bagian. */
  overall_changed_ratio: number;
  /** Ada draf AI untuk dibandingkan. */
  ai_drafted: boolean;
  /** Auditor menyimpan naratif final; bila false, draf AI diterima apa adanya. */
  edited: boolean;
}
export const getFindingDiff = (id: number, findingId: number) =>
  req<NarrativeDiff>(`/engagements/${id}/findings/${findingId}/diff`);

// ---------- Modul 3: pencarian temuan & Basis Pengetahuan ----------
export interface FindingSearchItem {
  id: number;
  engagement_id: number;
  engagement_name: string;
  client_name: string;
  title: string;
  severity: string;
  status: string;
  priority: number | null;
  cwe: string | null;
  owasp: string | null;
  cvss_score: number | null;
}
export interface FindingSearchFilters {
  q?: string;
  severity?: string;
  status?: string;
  cwe?: string;
}
export const searchFindings = (f: FindingSearchFilters = {}) => {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.severity) p.set("severity", f.severity);
  if (f.status) p.set("status", f.status);
  if (f.cwe) p.set("cwe", f.cwe);
  const qs = p.toString();
  return req<{ items: FindingSearchItem[] }>(`/findings${qs ? `?${qs}` : ""}`);
};

export interface KnowledgeEntry {
  id: number;
  source_finding_id: number;
  source_engagement_id: number;
  source_engagement_name: string;
  source_client_name: string;
  title: string;
  cwe: string | null;
  owasp: string | null;
  severity: string;
  narrative: { description?: string; impact?: string; recommendation?: string };
  /** Naskah diketik auditor; false berarti draf AI yang disetujui apa adanya. */
  auditor_edited: boolean;
  usage_count: number;
  created_at: string;
}
export const listKnowledge = (q?: string, cwe?: string) => {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (cwe) p.set("cwe", cwe);
  const qs = p.toString();
  return req<{ items: KnowledgeEntry[] }>(`/knowledge${qs ? `?${qs}` : ""}`);
};

/** Hapus penugasan beserta seluruh isinya. Admin saja; tak dapat dibatalkan. */
export interface EngagementDeleted {
  engagement_id: number;
  name: string;
  findings: number;
  uploads: number;
  knowledge_entries: number;
  storage_objects: number;
}
export const deleteEngagement = (id: number, confirmName: string) =>
  req<EngagementDeleted>(`/engagements/${id}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_name: confirmName }),
  });

export interface KnowledgeSuggestion {
  entry: KnowledgeEntry;
  /** 0..1 — bobot besar pada kesamaan CWE, sisanya irisan token judul. */
  score: number;
}
export const suggestKnowledge = (findingId: number, limit = 5) =>
  req<{ items: KnowledgeSuggestion[] }>(
    `/knowledge/suggest?finding_id=${findingId}&limit=${limit}`,
  );

/** Pakai naratif entri KB sebagai naratif final; tercatat sebagai suntingan auditor. */
export const applyKnowledge = (id: number, findingId: number, entryId: number) =>
  req<FindingDetail>(
    `/engagements/${id}/findings/${findingId}/apply-knowledge/${entryId}`,
    { method: "POST" },
  );

// ---------- Pusat Ingest ----------
export interface IngestItem {
  upload_id: number;
  engagement_id: number;
  engagement_name: string;
  filename: string;
  tool: string;
  status: string;
  error: string | null;
  /** "manual" bila diunggah pengguna, "watcher" bila diserap otomatis (R3). */
  source: string;
  can_reparse: boolean;
  created_at: string | null;
}
export interface IngestOverview {
  items: IngestItem[];
  summary: { today: number; failed: number; total: number };
}
export const getIngest = (status?: string) =>
  req<IngestOverview>(`/ingest${status ? `?status=${encodeURIComponent(status)}` : ""}`);
export const reparseUpload = (engagementId: number, uploadId: number) =>
  req<ScanUpload>(`/engagements/${engagementId}/uploads/${uploadId}/reparse`, {
    method: "POST",
  });

// ---------- D17: transparansi masking + audit log (admin) ----------
export const previewMasking = (text: string) =>
  req<{ masked: string }>("/admin/masking-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
export interface AuditLogRow {
  id: number;
  user_id: number | null;
  action: string;
  method: string;
  path: string;
  status_code: number | null;
  created_at: string | null;
}
export const getAuditLogs = (limit = 50) =>
  req<AuditLogRow[]>(`/admin/audit?limit=${limit}`);

export function uploadScan(id: number, file: File, tool: string): Promise<ScanUpload> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("tool", tool);
  return req<ScanUpload>(`/engagements/${id}/uploads`, { method: "POST", body: fd });
}

// ---------- Admin: konfigurasi LLM ----------
export interface LlmConfig {
  format: string;
  base_url: string;
  model: string;
  api_key_set: boolean;
  api_key_masked: string;
}
export interface LlmTestResult {
  status: string;
  provider: string;
  model: string;
  detail: string | null;
}
export const getLlmConfig = () => req<LlmConfig>("/admin/llm");
export const updateLlmConfig = (payload: {
  format?: string;
  base_url?: string;
  api_key?: string;
  model?: string;
}) =>
  req<LlmConfig>("/admin/llm", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const testLlmConnection = () =>
  req<LlmTestResult>("/admin/llm/test", { method: "POST" });
