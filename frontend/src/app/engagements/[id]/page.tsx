"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowClockwise,
  ClockCounterClockwise,
  Eye,
  FileArrowDown,
  FilePdf,
  Lightbulb,
  ListChecks,
  PencilSimple,
  Sliders,
  Sparkle,
  Trash,
  UploadSimple,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/i18n/LocaleProvider";
import type { MessageKey } from "@/i18n/messages";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

const TOOLS = ["nuclei", "zap", "nmap", "burp", "sarif", "unknown"];
const SEV_ORDER = ["critical", "high", "medium", "low", "info"];
const SEV_RANK: Record<string, number> = Object.fromEntries(
  SEV_ORDER.map((s, i) => [s, i])
);

const SEV_CLASS: Record<string, string> = {
  critical: "err",
  high: "err",
  medium: "wait",
  low: "wait",
  info: "ok",
};
const STATUS_CLASS: Record<string, string> = {
  parsed: "ok",
  uploaded: "wait",
  parsing: "wait",
  failed: "err",
};
const PRIO_CLASS: Record<number, string> = { 1: "err", 2: "err", 3: "wait", 4: "ok" };
const POSTURE_CLASS: Record<string, string> = {
  critical: "err",
  elevated: "err",
  moderate: "wait",
  low: "ok",
  clean: "ok",
};
// Kelas badge per status temuan (alur review D13).
const FSTATUS_CLASS: Record<string, string> = {
  draft: "wait",
  in_review: "wait",
  approved: "ok",
  rejected: "err",
  false_positive: "err",
};
const APPROVER_ROLES = ["auditor", "admin"];

// Kolom tabel temuan yang bisa disembunyikan (judul & keparahan selalu tampil).
const OPTIONAL_COLS = [
  "priority",
  "cwe",
  "owasp",
  "cvss",
  "cve",
  "sources",
  "count",
  "narrative",
  "status",
] as const;
type ColKey = (typeof OPTIONAL_COLS)[number];

export default function EngagementDetailPage() {
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const params = useParams();
  const router = useRouter();
  const id = Number(Array.isArray(params.id) ? params.id[0] : params.id);
  const canApprove = !!user && APPROVER_ROLES.includes(user.role);
  // Saran rujukan memuat naratif penugasan klien lain — batasnya sama dengan
  // Basis Pengetahuan: hanya auditor dan admin.
  const canUseKb = user?.role === "auditor" || user?.role === "admin";

  const [eng, setEng] = useState<api.EngagementDetail | null>(null);
  const [uploads, setUploads] = useState<api.ScanUpload[]>([]);
  const [reparsingId, setReparsingId] = useState<number | null>(null);
  const [findings, setFindings] = useState<api.Finding[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [tool, setTool] = useState("nuclei");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // --- Modul 2: tab Tim ---
  const [members, setMembers] = useState<api.Member[]>([]);
  const [allUsers, setAllUsers] = useState<api.User[]>([]);
  const [pickUser, setPickUser] = useState("");
  const [scope, setScope] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [kbShareable, setKbShareable] = useState(true);
  // Pesan tersendiri: `baseMsg` khusus baseline di tab Ringkasan, memakainya
  // di sini membuat pesan muncul di tab yang salah.
  const [teamMsg, setTeamMsg] = useState<string | null>(null);
  // --- Penghapusan penugasan (admin) ---
  const [delConfirm, setDelConfirm] = useState("");
  const [delBusy, setDelBusy] = useState(false);
  const [genBusy, setGenBusy] = useState(false);
  const [triBusy, setTriBusy] = useState(false);
  const [narrMsg, setNarrMsg] = useState<string | null>(null);
  const [pollNarr, setPollNarr] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<api.FindingDetail | null>(null);
  const [sevFilter, setSevFilter] = useState<string>("all");
  const [sumBusy, setSumBusy] = useState(false);
  const [sumMsg, setSumMsg] = useState<string | null>(null);
  const [pollSum, setPollSum] = useState(false);
  const [cols, setCols] = useState<Set<ColKey>>(new Set(OPTIONAL_COLS));
  // --- D13: review ---
  const [editing, setEditing] = useState(false);
  const [editVals, setEditVals] = useState({ description: "", impact: "", recommendation: "" });
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewMsg, setReviewMsg] = useState<string | null>(null);
  const [showHist, setShowHist] = useState(false);
  const [revs, setRevs] = useState<api.FindingRevision[]>([]);
  // --- Modul 2: perbandingan draf AI vs naratif final ---
  const [diff, setDiff] = useState<api.NarrativeDiff | null>(null);
  // --- Modul 3: saran rujukan dari Basis Pengetahuan ---
  const [sugg, setSugg] = useState<api.KnowledgeSuggestion[] | null>(null);
  const [suggBusy, setSuggBusy] = useState(false);
  // --- D14: tab, mode tampilan, kanban, lampiran ---
  const [tab, setTab] = useState<"files" | "findings" | "summary" | "team">("findings");
  const [viewMode, setViewMode] = useState<"list" | "kanban">("list");
  const [dragId, setDragId] = useState<number | null>(null);
  const [atts, setAtts] = useState<api.Attachment[]>([]);
  const [attBusy, setAttBusy] = useState(false);
  const [evalM, setEvalM] = useState<api.Evaluation | null>(null);
  // --- Modul 1: baseline + metrik waktu penyusunan ---
  const [timing, setTiming] = useState<api.Timing | null>(null);
  const [baseHours, setBaseHours] = useState("");
  const [baseNote, setBaseNote] = useState("");
  const [baseBusy, setBaseBusy] = useState(false);
  const [baseMsg, setBaseMsg] = useState<string | null>(null);
  const [baseErr, setBaseErr] = useState<string | null>(null);
  // Deteksi macet polling naratif (mis. batas kuota LLM): tak ada progres → berhenti.
  const stallRef = useRef({ last: -1, stall: 0 });

  const colLabel: Record<ColKey, string> = {
    priority: t("find.priority"),
    cwe: "CWE",
    owasp: "OWASP",
    cvss: "CVSS",
    cve: "CVE",
    sources: t("find.sources"),
    count: t("find.count"),
    narrative: t("narr.col"),
    status: t("find.status"),
  };

  const refresh = useCallback(async () => {
    const [e, u, f, ev, tm] = await Promise.all([
      api.getEngagement(id),
      api.listUploads(id),
      api.listFindings(id),
      api.getEvaluation(id).catch(() => null),
      api.getTiming(id).catch(() => null),
    ]);
    setEng(e);
    setUploads(u);
    setFindings(f);
    if (ev) setEvalM(ev);
    if (tm) setTiming(tm);
  }, [id]);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  const loadTeam = useCallback(async () => {
    const [ms, us] = await Promise.all([
      api.listMembers(id),
      // Daftar pengguna hanya untuk dropdown; kegagalannya tak boleh
      // menghalangi daftar anggota tampil.
      api.listUsers().catch(() => [] as api.User[]),
    ]);
    setMembers(ms);
    setAllUsers(us);
  }, [id]);

  useEffect(() => {
    if (tab === "team") {
      loadTeam().catch((err) =>
        setError(err instanceof ApiError ? err.message : String(err))
      );
    }
  }, [tab, loadTeam]);

  // Isi formulir kelengkapan begitu data penugasan termuat, tetapi HANYA
  // sekali per penugasan. `refresh()` memanggil `setEng` dengan objek baru,
  // dan penyegaran itu berjalan tiap 1,5 detik selama berkas diurai serta tiap
  // 4 detik selama naratif/ringkasan dibuat. Bila efek ini ikut setiap objek
  // `eng`, penyegaran latar menimpa suntingan yang belum disimpan: centang
  // kb_shareable kembali ke nilai server, lalu tombol Simpan mengirim nilai
  // lama itu sambil tetap melaporkan "tersimpan". Cakupan yang sedang diketik
  // pun hilang di tengah kalimat.
  const seededRef = useRef<number | null>(null);
  useEffect(() => {
    if (!eng || seededRef.current === eng.id) return;
    seededRef.current = eng.id;
    setScope(eng.scope ?? "");
    setPeriodStart(eng.period_start ?? "");
    setPeriodEnd(eng.period_end ?? "");
    setKbShareable(eng.kb_shareable ?? true);
  }, [eng]);

  async function handleReparse(uploadId: number) {
    setReparsingId(uploadId);
    setError(null);
    try {
      await api.reparseUpload(id, uploadId);
      // Parsing asinkron di worker; beri jeda sebelum memuat ulang daftar berkas.
      setTimeout(() => void refresh(), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setReparsingId(null);
    }
  }

  // Isi formulir baseline sekali saat penugasan termuat; dikunci pada `eng?.id`
  // agar refresh berkala tidak menimpa yang sedang diketik auditor.
  useEffect(() => {
    if (!eng) return;
    setBaseHours(eng.baseline_hours === null ? "" : String(eng.baseline_hours));
    setBaseNote(eng.baseline_note ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eng?.id]);

  async function saveBaseline() {
    setBaseMsg(null);
    setBaseErr(null);
    const raw = baseHours.trim();
    let hours: number | null = null;
    if (raw !== "") {
      const n = Number(raw);
      if (!Number.isFinite(n) || n <= 0) {
        setBaseErr(t("base.invalid"));
        return;
      }
      hours = n;
    }
    setBaseBusy(true);
    try {
      await api.setBaseline(id, hours, baseNote.trim() || null);
      setBaseMsg(t("base.saved"));
      await refresh();
    } catch (err) {
      // Backend menolak peran non-auditor dengan 403; pesan generik tak menjelaskan apa pun.
      if (err instanceof ApiError && err.status === 403) setBaseErr(t("base.forbidden"));
      else setBaseErr(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBaseBusy(false);
    }
  }

  // Polling selama masih ada berkas yang diproses.
  useEffect(() => {
    if (!uploads.some((u) => u.status === "uploaded" || u.status === "parsing")) return;
    const iv = setInterval(() => {
      refresh().catch(() => {});
    }, 1500);
    return () => clearInterval(iv);
  }, [uploads, refresh]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!file) return;
    const form = e.currentTarget; // tangkap sebelum await (currentTarget jadi null setelahnya)
    setBusy(true);
    setError(null);
    try {
      await api.uploadScan(id, file, tool);
      setFile(null);
      form.reset();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function genNarratives() {
    setGenBusy(true);
    setNarrMsg(null);
    setError(null);
    try {
      const r = await api.generateNarratives(id, locale);
      setNarrMsg(t("narr.queued").replace("{n}", String(r.queued)));
      stallRef.current = { last: -1, stall: 0 };
      setPollNarr(true);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setGenBusy(false);
    }
  }

  async function runTriage() {
    setTriBusy(true);
    setError(null);
    try {
      const r = await api.recomputeTriage(id);
      await refresh();
      setNarrMsg(t("triage.done").replace("{n}", String(r.triaged)));
      setTimeout(() => setNarrMsg(null), 4000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setTriBusy(false);
    }
  }

  async function genSummary() {
    setSumBusy(true);
    setSumMsg(null);
    setError(null);
    try {
      await api.generateExecSummary(id, locale);
      setSumMsg(t("sum.queued"));
      // Optimistis: anggap belum jadi agar polling menunggu draf baru.
      setEng((prev) => (prev ? { ...prev, exec_summary_generated: false } : prev));
      setPollSum(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSumBusy(false);
    }
  }

  async function toggleDetail(fid: number) {
    if (openId === fid) {
      setOpenId(null);
      setDetail(null);
      setDiff(null);
      setSugg(null);
      return;
    }
    setOpenId(fid);
    setDetail(null);
    setEditing(false);
    setShowHist(false);
    setReviewMsg(null);
    setAtts([]);
    // Perbandingan dan saran rujukan milik temuan sebelumnya; membiarkannya
    // membuat angka satu temuan terbaca di bawah judul temuan lain.
    setDiff(null);
    setSugg(null);
    try {
      setDetail(await api.getFinding(id, fid));
      await loadAttachments(fid);
    } catch (err) {
      // Sebelumnya galat ini ditelan diam-diam: panel tak terbuka dan layar
      // tak memberi tanda apa pun, sehingga satu-satunya cara mengetahui
      // penyebabnya adalah membuka konsol peramban.
      setOpenId(null);
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  // Naratif yang berlaku: final (suntingan auditor) menang atas draf AI.
  function currentNarrative(d: api.FindingDetail): api.Narrative {
    return d.final_narrative || d.ai_draft || {};
  }

  function startEdit(d: api.FindingDetail) {
    const n = currentNarrative(d);
    setEditVals({
      description: n.description || "",
      impact: n.impact || "",
      recommendation: n.recommendation || "",
    });
    setReviewMsg(null);
    setEditing(true);
  }

  async function deleteEngagement() {
    if (!eng) return;
    setDelBusy(true);
    setError(null);
    try {
      await api.deleteEngagement(id, delConfirm.trim());
      // Penugasannya sudah tak ada; bertahan di halaman ini hanya menghasilkan
      // 404 beruntun.
      router.replace("/engagements");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setDelBusy(false);
    }
  }

  async function applySuggestion(fid: number, entryId: number) {
    setReviewBusy(true);
    setError(null);
    try {
      const updated = await api.applyKnowledge(id, fid, entryId);
      setDetail(updated);
      // Naratif berubah; saran dan perbandingan lama tak lagi menggambarkannya.
      setSugg(null);
      setDiff(null);
      setReviewMsg(t("kb.applied"));
      setTimeout(() => setReviewMsg(null), 4000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setReviewBusy(false);
    }
  }

  async function saveNarrative(fid: number) {
    setReviewBusy(true);
    setError(null);
    try {
      const updated = await api.editNarrative(id, fid, editVals);
      setDetail(updated);
      setEditing(false);
      // Naratif berubah, jadi perbandingan lama sudah basi.
      setDiff(null);
      setSugg(null);
      setReviewMsg(t("review.saved"));
      setTimeout(() => setReviewMsg(null), 4000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setReviewBusy(false);
    }
  }

  async function doStatus(fid: number, next: string, note?: string) {
    setReviewBusy(true);
    setError(null);
    try {
      const updated = await api.changeFindingStatus(id, fid, { status: next, note });
      setDetail(updated);
      await refresh();
      setReviewMsg(t("review.statusChanged"));
      setTimeout(() => setReviewMsg(null), 4000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setReviewBusy(false);
    }
  }

  // Keputusan final (tolak/false positive) → konfirmasi + alasan (terekam di riwayat).
  function confirmDecision(fid: number, next: string) {
    const note = window.prompt(t("review.reasonPrompt"));
    if (note === null) return; // batal
    doStatus(fid, next, note || undefined);
  }

  async function toggleHistory(fid: number) {
    if (showHist) {
      setShowHist(false);
      return;
    }
    try {
      setRevs(await api.getRevisions(id, fid));
      setShowHist(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  // --- D14: pindah status via drag di papan Kanban ---
  async function moveStatus(fid: number, next: string) {
    setError(null);
    try {
      await api.changeFindingStatus(id, fid, { status: next });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  // --- D14: lampiran bukti ---
  async function loadAttachments(fid: number) {
    try {
      setAtts(await api.listAttachments(id, fid));
    } catch {
      setAtts([]);
    }
  }

  async function uploadAtt(fid: number, file: File) {
    setAttBusy(true);
    setError(null);
    try {
      await api.uploadAttachment(id, fid, file);
      await loadAttachments(fid);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setAttBusy(false);
    }
  }

  async function deleteAtt(fid: number, aid: number) {
    setError(null);
    try {
      await api.deleteAttachment(id, fid, aid);
      await loadAttachments(fid);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  // Polling naratif: berhenti saat semua jadi ATAU saat macet (tak ada progres
  // beberapa siklus — mis. batas kuota LLM) agar pesan tak menggantung selamanya.
  useEffect(() => {
    if (!pollNarr) return;
    const aiCount = findings.filter((f) => f.ai_generated).length;
    if (findings.length > 0 && aiCount === findings.length) {
      setPollNarr(false);
      setNarrMsg(t("narr.done"));
      const to = setTimeout(() => setNarrMsg(null), 4000);
      return () => clearTimeout(to);
    }
    const s = stallRef.current;
    if (aiCount > s.last) {
      s.last = aiCount;
      s.stall = 0;
    } else {
      s.stall += 1;
    }
    if (s.stall >= 8) {
      // ~32 dtk tanpa progres → hentikan & beri tahu (mungkin gagal/rate limit).
      setPollNarr(false);
      setNarrMsg(t("narr.partial"));
      const to = setTimeout(() => setNarrMsg(null), 8000);
      return () => clearTimeout(to);
    }
    const iv = setInterval(() => refresh().catch(() => {}), 4000);
    return () => clearInterval(iv);
  }, [pollNarr, findings, refresh, t]);

  // Polling ringkasan eksekutif: berhenti saat draf baru tersimpan.
  useEffect(() => {
    if (!pollSum) return;
    if (eng?.exec_summary_generated) {
      setPollSum(false);
      setSumMsg(t("sum.done"));
      const to = setTimeout(() => setSumMsg(null), 4000);
      return () => clearTimeout(to);
    }
    const iv = setInterval(() => refresh().catch(() => {}), 4000);
    return () => clearInterval(iv);
  }, [pollSum, eng, refresh, t]);

  const sevCounts: Record<string, number> = {};
  findings.forEach((f) => {
    sevCounts[f.severity] = (sevCounts[f.severity] || 0) + 1;
  });
  const shown = useMemo(() => {
    const filtered =
      sevFilter === "all" ? findings : findings.filter((f) => f.severity === sevFilter);
    // Urut: prioritas naik (P1 dulu) → keparahan → skor prioritas turun.
    return [...filtered].sort((a, b) => {
      const pa = a.priority ?? 9;
      const pb = b.priority ?? 9;
      if (pa !== pb) return pa - pb;
      const sa = SEV_RANK[a.severity] ?? 99;
      const sb = SEV_RANK[b.severity] ?? 99;
      if (sa !== sb) return sa - sb;
      return (b.priority_score ?? 0) - (a.priority_score ?? 0);
    });
  }, [findings, sevFilter]);

  const show = (c: ColKey) => cols.has(c);
  const toggleCol = (c: ColKey) =>
    setCols((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  // 2 kolom tetap (keparahan, judul) + kolom opsional yang aktif → colSpan baris naratif.
  const colSpan = 2 + OPTIONAL_COLS.filter((c) => cols.has(c)).length;

  const summary = eng?.exec_summary;

  const TABS: {
    key: "files" | "findings" | "summary" | "team";
    label: string;
  }[] = [
    { key: "files", label: t("tab.files") },
    { key: "findings", label: `${t("tab.findings")} (${findings.length})` },
    { key: "summary", label: t("tab.summary") },
    { key: "team", label: t("tab.team") },
  ];

  return (
    <AppShell title={`${t("nav.engagements")} #${id}`}>
      <div className="tabbar">
        {TABS.map((tb) => (
          <button
            key={tb.key}
            className={`tabitem${tab === tb.key ? " active" : ""}`}
            onClick={() => setTab(tb.key)}
          >
            {tb.label}
          </button>
        ))}
      </div>
      {error && tab !== "files" && (
        <div className="alert err" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      {tab === "files" && (
        <>
          <section className="card">
            <h3 style={{ marginTop: 0 }}>{t("up.title")}</h3>
            <form className="form-row" onSubmit={submit}>
          <label className="field">
            <span>{t("up.file")}</span>
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>
          <label className="field">
            <span>{t("up.tool")}</span>
            <select value={tool} onChange={(e) => setTool(e.target.value)}>
              {TOOLS.map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </label>
          <button className="btn" disabled={busy || !file}>
            <UploadSimple size={16} /> {t("up.submit")}
          </button>
        </form>
        {error && <div className="alert err">{error}</div>}
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>{t("up.listTitle")}</h3>
        {uploads.length === 0 ? (
          <p className="muted">{t("up.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("up.file")}</th>
                  <th>{t("up.tool")}</th>
                  <th>{t("up.status")}</th>
                  <th>{t("up.error")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {uploads.map((u) => (
                  <tr key={u.id}>
                    <td>{u.filename}</td>
                    <td className="mono">{u.tool}</td>
                    <td>
                      <span className={`badge ${STATUS_CLASS[u.status] || "wait"}`}>
                        ● {u.status}
                      </span>
                    </td>
                    <td className="muted">{u.error || "—"}</td>
                    <td>
                      {u.can_reparse && (
                        <button
                          className="btn secondary"
                          disabled={reparsingId === u.id}
                          onClick={() => handleReparse(u.id)}
                        >
                          <ArrowClockwise size={14} />{" "}
                          {reparsingId === u.id
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
        </>
      )}

      {tab === "findings" && (
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
          <h3 style={{ margin: 0 }}>
            {t("find.title")} <span className="muted">({findings.length})</span>
          </h3>
          {findings.length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <div className="chip-row">
                <button
                  className={`chip ${viewMode === "list" ? "active" : ""}`}
                  onClick={() => setViewMode("list")}
                >
                  {t("view.list")}
                </button>
                <button
                  className={`chip ${viewMode === "kanban" ? "active" : ""}`}
                  onClick={() => setViewMode("kanban")}
                >
                  {t("view.kanban")}
                </button>
              </div>
              <button className="btn secondary" onClick={runTriage} disabled={triBusy}>
                <ListChecks size={16} /> {triBusy ? t("common.loading") : t("triage.run")}
              </button>
              {viewMode === "list" && (
                <details className="col-menu">
                  <summary className="btn secondary">
                    <Sliders size={16} /> {t("cols.menu")}
                  </summary>
                  <div className="col-menu-pop">
                    {OPTIONAL_COLS.map((c) => (
                      <label key={c} className="col-menu-item">
                        <input
                          type="checkbox"
                          checked={cols.has(c)}
                          onChange={() => toggleCol(c)}
                        />
                        <span>{colLabel[c]}</span>
                      </label>
                    ))}
                  </div>
                </details>
              )}
              <button className="btn" onClick={genNarratives} disabled={genBusy}>
                <Sparkle size={16} /> {genBusy ? t("common.loading") : t("narr.generate")}
              </button>
            </div>
          )}
        </div>
        {narrMsg && (
          <div className="alert ok" style={{ marginTop: 10 }}>
            {narrMsg}
          </div>
        )}
        {findings.length > 0 && (
          <div className="chip-row" style={{ marginTop: 12 }}>
            <button
              className={`chip ${sevFilter === "all" ? "active" : ""}`}
              onClick={() => setSevFilter("all")}
            >
              {t("filter.all")} ({findings.length})
            </button>
            {SEV_ORDER.filter((s) => sevCounts[s]).map((s) => (
              <button
                key={s}
                className={`chip ${sevFilter === s ? "active" : ""}`}
                onClick={() => setSevFilter(s)}
              >
                {s} ({sevCounts[s]})
              </button>
            ))}
          </div>
        )}
        {findings.length === 0 ? (
          <p className="muted">{t("find.empty")}</p>
        ) : viewMode === "kanban" ? (
          <div className="kanban" style={{ marginTop: 12 }}>
            {(["draft", "in_review", "approved", "rejected", "false_positive"] as const).map(
              (col) => {
                const cards = shown.filter((f) => f.status === col);
                return (
                  <div
                    key={col}
                    className="kan-col"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => {
                      if (dragId != null) moveStatus(dragId, col);
                      setDragId(null);
                    }}
                  >
                    <div className="kan-head">
                      <span className={`badge ${FSTATUS_CLASS[col] || "wait"}`}>
                        {t(`fstatus.${col}` as MessageKey)}
                      </span>
                      <span className="muted">{cards.length}</span>
                    </div>
                    {cards.map((f) => (
                      <div
                        key={f.id}
                        className="kan-card"
                        draggable
                        onDragStart={() => setDragId(f.id)}
                        onDragEnd={() => setDragId(null)}
                        onClick={() => {
                          setTab("findings");
                          toggleDetail(f.id);
                        }}
                        title={f.title}
                      >
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <span className={`badge ${SEV_CLASS[f.severity] || "wait"}`}>
                            {f.severity}
                          </span>
                          {f.priority && (
                            <span className={`badge ${PRIO_CLASS[f.priority] || "wait"}`}>
                              P{f.priority}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: "0.82rem", marginTop: 6 }}>{f.title}</div>
                      </div>
                    ))}
                  </div>
                );
              }
            )}
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("find.severity")}</th>
                  <th>{t("find.titleCol")}</th>
                  {show("priority") && <th>{t("find.priority")}</th>}
                  {show("cwe") && <th>CWE</th>}
                  {show("owasp") && <th>OWASP</th>}
                  {show("cvss") && <th>CVSS</th>}
                  {show("cve") && <th>CVE</th>}
                  {show("sources") && <th>{t("find.sources")}</th>}
                  {show("count") && <th>{t("find.count")}</th>}
                  {show("narrative") && <th>{t("narr.col")}</th>}
                  {show("status") && <th>{t("find.status")}</th>}
                </tr>
              </thead>
              <tbody>
                {shown.map((f) => (
                  <Fragment key={f.id}>
                    <tr>
                      <td>
                        <span className={`badge ${SEV_CLASS[f.severity] || "wait"}`}>
                          {f.severity}
                        </span>
                      </td>
                      <td>{f.title}</td>
                      {show("priority") && (
                        <td className="mono">
                          {f.priority ? (
                            <span
                              className={`badge ${PRIO_CLASS[f.priority] || "wait"}`}
                              title={
                                f.priority_score != null
                                  ? `skor ${f.priority_score}`
                                  : undefined
                              }
                            >
                              P{f.priority}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                      )}
                      {show("cwe") && <td className="mono">{f.cwe || "—"}</td>}
                      {show("owasp") && (
                        <td className="mono" title={f.owasp || undefined}>
                          {f.owasp ? f.owasp.split(" – ")[0] : "—"}
                        </td>
                      )}
                      {show("cvss") && <td className="mono">{f.cvss_score ?? "—"}</td>}
                      {show("cve") && (
                        <td className="mono">{f.cve.length ? f.cve.join(", ") : "—"}</td>
                      )}
                      {show("sources") && (
                        <td className="mono">
                          {f.tools.length ? f.tools.join(", ") : "—"}
                        </td>
                      )}
                      {show("count") && (
                        <td className="mono">
                          {f.occurrences > 1 ? (
                            <span className="badge ok">×{f.occurrences}</span>
                          ) : (
                            f.occurrences
                          )}
                        </td>
                      )}
                      {show("narrative") && (
                        <td>
                          {f.ai_generated ? (
                            <button
                              className="btn secondary"
                              style={{ padding: "3px 9px", fontSize: "0.78rem" }}
                              onClick={() => toggleDetail(f.id)}
                            >
                              ✨ {openId === f.id ? t("narr.hide") : t("narr.view")}
                            </button>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      )}
                      {show("status") && (
                        <td>
                          <button
                            className={`badge ${FSTATUS_CLASS[f.status] || "wait"}`}
                            style={{ border: "none", cursor: "pointer" }}
                            onClick={() => toggleDetail(f.id)}
                            title={t("review.history")}
                          >
                            {t(`fstatus.${f.status}` as MessageKey)}
                          </button>
                        </td>
                      )}
                    </tr>
                    {openId === f.id && (
                      <tr>
                        <td colSpan={colSpan} style={{ background: "var(--surface-2)" }}>
                          {detail && detail.id === f.id ? (
                            <div style={{ display: "grid", gap: 10, padding: "6px 2px" }}>
                              {/* Baris aksi review */}
                              <div
                                style={{
                                  display: "flex",
                                  gap: 8,
                                  flexWrap: "wrap",
                                  alignItems: "center",
                                }}
                              >
                                <span className={`badge ${FSTATUS_CLASS[detail.status] || "wait"}`}>
                                  {t(`fstatus.${detail.status}` as MessageKey)}
                                </span>
                                {detail.narrative_edited && (
                                  <span className="badge ok">✎ {t("review.edited")}</span>
                                )}
                                <span style={{ flex: 1 }} />
                                {!editing && (
                                  <button
                                    className="btn secondary"
                                    onClick={() => startEdit(detail)}
                                    disabled={reviewBusy}
                                  >
                                    <PencilSimple size={15} /> {t("review.edit")}
                                  </button>
                                )}
                                <button
                                  className="btn secondary"
                                  onClick={() => toggleHistory(detail.id)}
                                  disabled={reviewBusy}
                                >
                                  <ClockCounterClockwise size={15} />{" "}
                                  {showHist ? t("review.hideHistory") : t("review.history")}
                                </button>
                                <button
                                  className="btn secondary"
                                  onClick={() => {
                                    if (diff) {
                                      setDiff(null);
                                      return;
                                    }
                                    setError(null);
                                    api
                                      .getFindingDiff(id, detail.id)
                                      .then(setDiff)
                                      .catch((err) =>
                                        setError(
                                          err instanceof ApiError
                                            ? err.message
                                            : String(err)
                                        )
                                      );
                                  }}
                                  disabled={reviewBusy}
                                >
                                  <ListChecks size={15} />{" "}
                                  {diff ? t("diff.hide") : t("diff.tab")}
                                </button>
                                {/* Saran rujukan memuat naratif klien lain →
                                    hanya auditor/admin, sama seperti Basis
                                    Pengetahuan itu sendiri. */}
                                {canUseKb && (
                                  <button
                                    className="btn secondary"
                                    onClick={() => {
                                      if (sugg) {
                                        setSugg(null);
                                        return;
                                      }
                                      setError(null);
                                      setSuggBusy(true);
                                      api
                                        .suggestKnowledge(detail.id)
                                        .then((d) => setSugg(d.items))
                                        .catch((err) =>
                                          setError(
                                            err instanceof ApiError
                                              ? err.message
                                              : String(err)
                                          )
                                        )
                                        .finally(() => setSuggBusy(false));
                                    }}
                                    disabled={reviewBusy || suggBusy}
                                  >
                                    <Lightbulb size={15} />{" "}
                                    {sugg ? t("kb.suggestHide") : t("kb.suggest")}
                                  </button>
                                )}
                              </div>

                              {/* Saran rujukan lintas penugasan (Modul 3) */}
                              {sugg && (
                                <div
                                  className="card"
                                  style={{ marginTop: 12, background: "var(--surface-2)" }}
                                >
                                  <p className="muted" style={{ marginTop: 0 }}>
                                    {t("kb.suggestNote")}
                                  </p>
                                  {sugg.length === 0 ? (
                                    <p className="muted">{t("kb.suggestEmpty")}</p>
                                  ) : (
                                    sugg.map((s) => (
                                      <div
                                        key={s.entry.id}
                                        style={{
                                          borderTop: "1px solid var(--border)",
                                          paddingTop: 8,
                                          marginTop: 8,
                                        }}
                                      >
                                        <div
                                          style={{
                                            display: "flex",
                                            gap: 8,
                                            alignItems: "center",
                                            flexWrap: "wrap",
                                          }}
                                        >
                                          <span className="badge ok mono">
                                            {Math.round(s.score * 100)}%
                                          </span>
                                          <strong>{s.entry.title}</strong>
                                          <span className="mono">
                                            {s.entry.cwe ?? "—"}
                                          </span>
                                        </div>
                                        <p className="muted mono" style={{ margin: "4px 0" }}>
                                          {t("kb.from")}: #{s.entry.source_engagement_id}{" "}
                                          {s.entry.source_engagement_name} ·{" "}
                                          {s.entry.source_client_name} ·{" "}
                                          {s.entry.auditor_edited
                                            ? t("kb.byAuditor")
                                            : t("kb.byAi")}
                                        </p>
                                        <p style={{ margin: "4px 0" }}>
                                          {(s.entry.narrative.description || "").slice(0, 220)}
                                          {(s.entry.narrative.description || "").length > 220
                                            ? "…"
                                            : ""}
                                        </p>
                                        <button
                                          className="btn secondary"
                                          disabled={reviewBusy || suggBusy}
                                          onClick={() => applySuggestion(detail.id, s.entry.id)}
                                        >
                                          <Sparkle size={15} /> {t("kb.apply")}
                                        </button>
                                      </div>
                                    ))
                                  )}
                                </div>
                              )}

                              {reviewMsg && <div className="alert ok">{reviewMsg}</div>}

                              {/* Naratif: mode baca atau sunting */}
                              {editing ? (
                                <div style={{ display: "grid", gap: 8 }}>
                                  {(["description", "impact", "recommendation"] as const).map(
                                    (k) => (
                                      <label key={k} className="field">
                                        <span>
                                          {k === "description"
                                            ? t("narr.desc")
                                            : k === "impact"
                                              ? t("narr.impact")
                                              : t("narr.rec")}
                                        </span>
                                        <textarea
                                          rows={3}
                                          value={editVals[k]}
                                          onChange={(e) =>
                                            setEditVals((v) => ({ ...v, [k]: e.target.value }))
                                          }
                                        />
                                      </label>
                                    )
                                  )}
                                  <div style={{ display: "flex", gap: 8 }}>
                                    <button
                                      className="btn"
                                      onClick={() => saveNarrative(detail.id)}
                                      disabled={reviewBusy}
                                    >
                                      {t("review.save")}
                                    </button>
                                    <button
                                      className="btn secondary"
                                      onClick={() => setEditing(false)}
                                      disabled={reviewBusy}
                                    >
                                      {t("review.cancel")}
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                (() => {
                                  const n = detail.final_narrative || detail.ai_draft;
                                  if (!n) return <span className="muted">{t("narr.none")}</span>;
                                  return (
                                    <div style={{ display: "grid", gap: 6 }}>
                                      <div className="muted" style={{ fontSize: "0.78rem" }}>
                                        {detail.final_narrative
                                          ? t("review.final")
                                          : `${t("review.aiDraft")} · ${detail.ai_model} · ${detail.ai_prompt_version}`}
                                      </div>
                                      <div>
                                        <strong>{t("narr.desc")}:</strong> {n.description || "—"}
                                      </div>
                                      <div>
                                        <strong>{t("narr.impact")}:</strong> {n.impact || "—"}
                                      </div>
                                      <div>
                                        <strong>{t("narr.rec")}:</strong>{" "}
                                        {n.recommendation || "—"}
                                      </div>
                                    </div>
                                  );
                                })()
                              )}

                              {/* Tombol transisi status (mesin status + RBAC) */}
                              {!editing && (
                                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                  {detail.status === "draft" && (
                                    <button
                                      className="btn"
                                      onClick={() => doStatus(detail.id, "in_review")}
                                      disabled={reviewBusy}
                                    >
                                      {t("review.submit")}
                                    </button>
                                  )}
                                  {detail.status === "in_review" && canApprove && (
                                    <>
                                      <button
                                        className="btn"
                                        onClick={() => doStatus(detail.id, "approved")}
                                        disabled={reviewBusy}
                                      >
                                        ✓ {t("review.approve")}
                                      </button>
                                      <button
                                        className="btn secondary"
                                        onClick={() => confirmDecision(detail.id, "rejected")}
                                        disabled={reviewBusy}
                                      >
                                        {t("review.reject")}
                                      </button>
                                      <button
                                        className="btn secondary"
                                        onClick={() =>
                                          confirmDecision(detail.id, "false_positive")
                                        }
                                        disabled={reviewBusy}
                                      >
                                        {t("review.fp")}
                                      </button>
                                    </>
                                  )}
                                  {["approved", "rejected", "false_positive"].includes(
                                    detail.status
                                  ) && (
                                    <button
                                      className="btn secondary"
                                      onClick={() => doStatus(detail.id, "in_review")}
                                      disabled={reviewBusy}
                                    >
                                      {t("review.reopen")}
                                    </button>
                                  )}
                                </div>
                              )}

                              {/* Lampiran bukti (D14) */}
                              <div
                                style={{
                                  borderTop: "1px solid var(--border)",
                                  paddingTop: 8,
                                  display: "grid",
                                  gap: 6,
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 10,
                                    flexWrap: "wrap",
                                  }}
                                >
                                  <strong style={{ fontSize: "0.85rem" }}>
                                    {t("evi.title")}
                                  </strong>
                                  <label
                                    className="btn secondary"
                                    style={{ cursor: "pointer", padding: "3px 10px" }}
                                  >
                                    {attBusy ? t("evi.uploading") : `+ ${t("evi.add")}`}
                                    <input
                                      type="file"
                                      style={{ display: "none" }}
                                      disabled={attBusy}
                                      onChange={(e) => {
                                        const fl = e.target.files?.[0];
                                        if (fl) uploadAtt(detail.id, fl);
                                        e.target.value = "";
                                      }}
                                    />
                                  </label>
                                </div>
                                {atts.length === 0 ? (
                                  <span className="muted" style={{ fontSize: "0.82rem" }}>
                                    {t("evi.empty")}
                                  </span>
                                ) : (
                                  atts.map((a) => (
                                    <div
                                      key={a.id}
                                      style={{
                                        display: "flex",
                                        gap: 8,
                                        alignItems: "center",
                                        fontSize: "0.82rem",
                                      }}
                                    >
                                      <span style={{ flex: 1 }}>
                                        📎 {a.filename}{" "}
                                        <span className="muted">
                                          ({Math.ceil(a.size / 1024)} KB)
                                        </span>
                                      </span>
                                      <button
                                        className="btn secondary"
                                        style={{ padding: "2px 8px" }}
                                        onClick={() =>
                                          api
                                            .downloadAttachment(id, detail.id, a.id, a.filename)
                                            .catch((err) =>
                                              setError(
                                                err instanceof ApiError
                                                  ? err.message
                                                  : String(err)
                                              )
                                            )
                                        }
                                      >
                                        {t("evi.download")}
                                      </button>
                                      <button
                                        className="btn secondary"
                                        style={{ padding: "2px 8px" }}
                                        onClick={() => deleteAtt(detail.id, a.id)}
                                      >
                                        {t("evi.delete")}
                                      </button>
                                    </div>
                                  ))
                                )}
                              </div>

                              {/* Riwayat revisi */}
                              {diff && (
                                <div
                                  className="card"
                                  style={{ marginTop: 12, background: "var(--surface-2)" }}
                                >
                                  {/* Angka hanya bermakna bila ada draf AI yang
                                      benar-benar disunting; tiga keadaan lain
                                      dijelaskan agar tak terbaca terbalik. */}
                                  {!diff.ai_drafted && !diff.edited ? (
                                    <p className="muted" style={{ marginTop: 0 }}>
                                      {t("diff.empty")}
                                    </p>
                                  ) : (
                                    <>
                                      <p className="mono" style={{ marginTop: 0 }}>
                                        {t("diff.overall")}:{" "}
                                        {Math.round(diff.overall_changed_ratio * 100)}%
                                      </p>
                                      {!diff.edited && (
                                        <p className="muted">{t("diff.unedited")}</p>
                                      )}
                                      {!diff.ai_drafted && (
                                        <p className="muted">{t("diff.noDraft")}</p>
                                      )}
                                    </>
                                  )}
                                  {diff.edited &&
                                    Object.entries(diff.sections).map(([name, sec]) => (
                                    <div key={name} style={{ marginTop: 10 }}>
                                      <strong>
                                        {t(`narr.${
                                          name === "description"
                                            ? "desc"
                                            : name === "impact"
                                            ? "impact"
                                            : "rec"
                                        }` as MessageKey)}
                                      </strong>{" "}
                                      <span className="mono">
                                        ({Math.round(sec.changed_ratio * 100)}%)
                                      </span>
                                      {sec.added.length === 0 && sec.removed.length === 0 ? (
                                        <p className="muted">{t("diff.none")}</p>
                                      ) : (
                                        <>
                                          {sec.added.length > 0 && (
                                            <p>
                                              <span className="badge ok">
                                                {t("diff.added")}
                                              </span>{" "}
                                              {sec.added.join(" ")}
                                            </p>
                                          )}
                                          {sec.removed.length > 0 && (
                                            <p>
                                              <span className="badge err">
                                                {t("diff.removed")}
                                              </span>{" "}
                                              {sec.removed.join(" ")}
                                            </p>
                                          )}
                                        </>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}

                              {showHist && (
                                <div
                                  style={{
                                    borderTop: "1px solid var(--border)",
                                    paddingTop: 8,
                                    display: "grid",
                                    gap: 6,
                                  }}
                                >
                                  {revs.length === 0 ? (
                                    <span className="muted">{t("review.noHistory")}</span>
                                  ) : (
                                    revs.map((r) => (
                                      <div key={r.id} style={{ fontSize: "0.82rem" }}>
                                        <span
                                          className={`badge ${FSTATUS_CLASS[r.status] || "wait"}`}
                                          style={{ marginRight: 8 }}
                                        >
                                          {t(`rev.${r.action}` as MessageKey)}
                                        </span>
                                        <span className="muted">
                                          {t("review.by")}{" "}
                                          {r.author_id ? `#${r.author_id}` : t("review.aiAuthor")}
                                          {r.created_at
                                            ? ` · ${new Date(r.created_at).toLocaleString()}`
                                            : ""}
                                          {r.note ? ` · ${r.note}` : ""}
                                        </span>
                                      </div>
                                    ))
                                  )}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="muted">{t("common.loading")}</span>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      )}

      {tab === "summary" && (
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
          <h3 style={{ margin: 0 }}>
            {t("sum.title")}
            {summary?.posture && (
              <span
                className={`badge ${POSTURE_CLASS[summary.posture] || "wait"}`}
                style={{ marginLeft: 10 }}
              >
                {t("sum.posture")}: {t(`posture.${summary.posture}` as MessageKey)}
              </span>
            )}
          </h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              className="btn secondary"
              onClick={() =>
                api
                  .previewReport(id, "approved", locale)
                  .catch((err) =>
                    setError(err instanceof ApiError ? err.message : String(err))
                  )
              }
              title={t("report.hint")}
            >
              <Eye size={16} /> {t("report.preview")}
            </button>
            <button
              className="btn secondary"
              onClick={() =>
                api
                  .downloadReportDocx(id, "approved", locale)
                  .catch((err) =>
                    setError(err instanceof ApiError ? err.message : String(err))
                  )
              }
              title={t("report.hint")}
            >
              <FileArrowDown size={16} /> {t("report.download")}
            </button>
            <button
              className="btn secondary"
              onClick={() =>
                api
                  .downloadReportPdf(id, "approved", locale)
                  .catch((err) =>
                    setError(err instanceof ApiError ? err.message : String(err))
                  )
              }
              title={t("report.hint")}
            >
              <FilePdf size={16} /> {t("report.pdf")}
            </button>
            {findings.length > 0 && (
              <button className="btn" onClick={genSummary} disabled={sumBusy}>
                <Sparkle size={16} /> {sumBusy ? t("common.loading") : t("sum.generate")}
              </button>
            )}
          </div>
        </div>
        {sumMsg && (
          <div className="alert ok" style={{ marginTop: 10 }}>
            {sumMsg}
          </div>
        )}
        {evalM && (
          <div className="metric-row" style={{ marginTop: 14 }}>
            <div className="metric">
              <div className="metric-val">{Math.round(evalM.dedup_reduction * 100)}%</div>
              <div className="metric-lbl">{t("eval.dedup")}</div>
              <div className="metric-sub">
                {t("eval.dedupHint")
                  .replace("{merged}", String(evalM.duplicates_merged))
                  .replace("{raw}", String(evalM.raw_findings))}
              </div>
            </div>
            <div className="metric">
              <div className="metric-val">{Math.round(evalM.ai_coverage * 100)}%</div>
              <div className="metric-lbl">{t("eval.aiCoverage")}</div>
              <div className="metric-sub">
                {evalM.ai_drafts}/{evalM.total_findings}
              </div>
            </div>
            <div className="metric">
              <div className="metric-val">{Math.round(evalM.review_progress * 100)}%</div>
              <div className="metric-lbl">{t("eval.reviewProgress")}</div>
              <div className="metric-sub">
                {t("eval.approved")}: {evalM.approved}
              </div>
            </div>
            <div className="metric">
              <div className="metric-val">{Math.round(evalM.edited_ratio * 100)}%</div>
              <div className="metric-lbl">{t("eval.edited")}</div>
              <div className="metric-sub">
                {evalM.edited_by_auditor}/{evalM.total_findings}
              </div>
            </div>
          </div>
        )}
        <div className="card" style={{ marginTop: 14 }}>
          <h4 style={{ margin: "0 0 4px" }}>{t("base.title")}</h4>
          <p className="muted" style={{ marginTop: 0, fontSize: "0.8rem" }}>
            {t("base.desc")}
          </p>
          <div className="form-row">
            <label className="field">
              <span>{t("base.hours")}</span>
              <input
                type="number"
                min="0"
                step="0.25"
                value={baseHours}
                onChange={(e) => setBaseHours(e.target.value)}
                disabled={!canApprove || baseBusy}
              />
            </label>
            <label className="field" style={{ flex: 2 }}>
              <span>{t("base.note")}</span>
              <input
                type="text"
                value={baseNote}
                placeholder={t("base.notePlaceholder")}
                onChange={(e) => setBaseNote(e.target.value)}
                disabled={!canApprove || baseBusy}
              />
            </label>
            <button
              className="btn"
              onClick={saveBaseline}
              disabled={!canApprove || baseBusy}
              title={canApprove ? undefined : t("base.forbidden")}
            >
              {baseBusy ? t("common.loading") : t("base.save")}
            </button>
          </div>
          {!canApprove && <p className="muted">{t("base.forbidden")}</p>}
          {baseMsg && <div className="alert ok">{baseMsg}</div>}
          {baseErr && <div className="alert err">{baseErr}</div>}
          {timing && (
            <>
              <div className="form-row" style={{ marginTop: 8 }}>
                <div className="field">
                  <span>{t("base.activeTime")}</span>
                  <strong className="mono">
                    {timing.active_hours} {t("reports.hours")}
                  </strong>
                </div>
                <div className="field">
                  <span>{t("base.events")}</span>
                  <strong className="mono">{timing.event_count}</strong>
                </div>
                <div className="field">
                  <span>{t("base.saved_hours")}</span>
                  <strong className="mono">
                    {timing.saved_hours === null
                      ? "—"
                      : `${timing.saved_hours} ${t("reports.hours")}`}
                  </strong>
                </div>
                <div className="field">
                  <span>{t("base.savedRatio")}</span>
                  <strong className="mono">
                    {timing.saved_ratio === null
                      ? "—"
                      : `${Math.round(timing.saved_ratio * 100)}%`}
                  </strong>
                </div>
              </div>
              {!timing.measurable && (
                <p className="muted" style={{ fontSize: "0.78rem" }}>
                  {t("base.notMeasurable")}
                </p>
              )}
            </>
          )}
        </div>

        {summary ? (
          <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
            <div>
              <strong>{t("sum.overview")}:</strong>
              <p style={{ margin: "4px 0 0" }}>{summary.overview || "—"}</p>
            </div>
            <div>
              <strong>{t("sum.risks")}:</strong>
              <p style={{ margin: "4px 0 0" }}>{summary.key_risks || "—"}</p>
            </div>
            <div>
              <strong>{t("sum.recs")}:</strong>
              <p style={{ margin: "4px 0 0" }}>{summary.recommendations || "—"}</p>
            </div>
            {eng?.exec_summary_model && (
              <div className="muted" style={{ fontSize: "0.78rem" }}>
                {t("narr.by")}: {eng.exec_summary_model} ·{" "}
                {eng.exec_summary_prompt_version}
              </div>
            )}
          </div>
        ) : (
          <p className="muted" style={{ marginTop: 12 }}>
            {t("sum.none")}
          </p>
        )}
      </section>
      )}

      {tab === "team" && (
        <>
          <section className="card">
            <h3 style={{ marginTop: 0 }}>{t("team.title")}</h3>
            <p className="muted">{t("team.hint")}</p>
            {members.length === 0 ? (
              <p className="muted">{t("team.empty")}</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>{t("team.name")}</th>
                      <th>{t("team.email")}</th>
                      <th>{t("team.role")}</th>
                      <th>{t("team.roleInTeam")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr key={m.user_id}>
                        <td>{m.full_name}</td>
                        <td className="mono">{m.email}</td>
                        <td className="mono">{m.role}</td>
                        <td className="mono">{m.role_in_team}</td>
                        <td>
                          {canApprove && (
                            <button
                              className="btn secondary"
                              onClick={() => {
                                setTeamMsg(null);
                                setError(null);
                                api
                                  .removeMember(id, m.user_id)
                                  .then(() => loadTeam())
                                  .catch((err) =>
                                    setError(
                                      err instanceof ApiError
                                        ? err.message
                                        : String(err)
                                    )
                                  );
                              }}
                            >
                              {t("team.remove")}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {canApprove ? (
              <div className="form-row" style={{ marginTop: 12 }}>
                <label className="field">
                  <span>{t("team.pickUser")}</span>
                  <select
                    value={pickUser}
                    onChange={(e) => setPickUser(e.target.value)}
                  >
                    <option value="">—</option>
                    {allUsers
                      .filter((u) => !members.some((m) => m.user_id === u.id))
                      .map((u) => (
                        <option key={u.id} value={String(u.id)}>
                          {u.full_name} ({u.role})
                        </option>
                      ))}
                  </select>
                </label>
                <button
                  className="btn"
                  disabled={!pickUser}
                  onClick={() => {
                    setTeamMsg(null);
                    setError(null);
                    api
                      .addMember(id, Number(pickUser))
                      .then(() => {
                        setPickUser("");
                        return loadTeam();
                      })
                      .catch((err) =>
                        setError(
                          err instanceof ApiError ? err.message : String(err)
                        )
                      );
                  }}
                >
                  {t("team.add")}
                </button>
              </div>
            ) : (
              <p className="muted">{t("team.forbidden")}</p>
            )}
          </section>

          <section className="card">
            <h3 style={{ marginTop: 0 }}>{t("det.title")}</h3>
            <p className="muted">{t("det.hint")}</p>
            <div className="form-row">
              <label className="field">
                <span>{t("det.periodStart")}</span>
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                />
              </label>
              <label className="field">
                <span>{t("det.periodEnd")}</span>
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                />
              </label>
            </div>
            <label className="field" style={{ marginTop: 8 }}>
              <span>{t("det.scope")}</span>
              <textarea
                rows={3}
                value={scope}
                placeholder={t("det.scopePlaceholder")}
                onChange={(e) => setScope(e.target.value)}
              />
            </label>
            <label
              style={{
                display: "flex",
                gap: 8,
                alignItems: "center",
                marginTop: 8,
              }}
            >
              <input
                type="checkbox"
                checked={kbShareable}
                onChange={(e) => setKbShareable(e.target.checked)}
              />
              <span>{t("det.kbShareable")}</span>
            </label>
            {canApprove && (
              <button
                className="btn"
                style={{ marginTop: 12 }}
                onClick={() => {
                  setTeamMsg(null);
                  setError(null);
                  api
                    .saveEngagementDetails(id, {
                      scope: scope || null,
                      period_start: periodStart || null,
                      period_end: periodEnd || null,
                      kb_shareable: kbShareable,
                    })
                    .then(() => {
                      setTeamMsg(t("det.saved"));
                      return refresh();
                    })
                    .catch((err) =>
                      setError(
                        err instanceof ApiError ? err.message : String(err)
                      )
                    );
                }}
              >
                {t("det.save")}
              </button>
            )}
            {teamMsg && <div className="alert ok">{teamMsg}</div>}
          </section>

          {/* Penghapusan penugasan — administrator saja, dan tak dapat dibatalkan. */}
          {user?.role === "admin" && (
            <section className="card">
              <h3 style={{ marginTop: 0 }}>{t("danger.title")}</h3>
              <p className="muted">{t("danger.hint")}</p>
              <label className="field">
                <span>{t("danger.typeName")}</span>
                <input
                  value={delConfirm}
                  placeholder={eng?.name ?? ""}
                  onChange={(e) => setDelConfirm(e.target.value)}
                />
              </label>
              <button
                className="btn danger"
                disabled={delBusy || !eng || delConfirm.trim() !== (eng?.name ?? "")}
                onClick={() => deleteEngagement()}
              >
                <Trash size={15} />{" "}
                {delBusy ? t("danger.deleting") : t("danger.delete")}
              </button>
            </section>
          )}
        </>
      )}
    </AppShell>
  );
}
