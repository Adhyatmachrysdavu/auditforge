"""Runner CLI eval harness (D12): ``python -m app.eval.run``.

Menjalankan evaluasi deterministik (dedup + enrichment), mencetak ringkasan, dan
menulis `eval_data/report.json`. Keluar dengan kode ≠0 bila ada metrik di bawah
ambang — sehingga bisa dipakai sebagai gerbang CI.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from app.eval.harness import EVAL_DIR, evaluate


def _fmt_pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def main() -> int:
    report = evaluate()
    report["generated_at"] = datetime.now(UTC).isoformat()

    d = report["dedup"]
    e = report["enrichment"]
    n = report["narrative"]

    print("=" * 60)
    print("AuditForge — Eval Harness (D12)")
    print("=" * 60)
    print(
        f"[Dedup]      F1={_fmt_pct(d['f1'])}  P={_fmt_pct(d['precision'])}  "
        f"R={_fmt_pct(d['recall'])}  "
        f"(n={d['n']}, gold={d['gold_clusters']}, pred={d['pred_clusters']}, "
        f"tp={d['tp']} fp={d['fp']} fn={d['fn']})  "
        f"{'OK' if d['passed'] else 'GAGAL'}"
    )
    print(
        f"[Enrichment] acc={_fmt_pct(e['accuracy'])}  "
        f"({e['correct']}/{e['checks']} cek, {e['cases']} kasus)  "
        f"{'OK' if e['passed'] else 'GAGAL'}"
    )
    if e["failures"]:
        for f in e["failures"]:
            print(
                f"   ✗ {f['case']} · {f['field']}: mau={f['want']!r} dapat={f['got']!r}"
            )
    if n["status"] == "skipped":
        print(f"[Narrative]  dilewati — {n['reason']} ({n['golden_cases']} golden)")
    else:
        print(f"[Narrative]  mean overlap={_fmt_pct(n['mean_overlap'])}")
    print("-" * 60)
    print(f"STATUS: {'LULUS' if report['passed'] else 'GAGAL'}")

    out = EVAL_DIR / "report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Laporan ditulis ke {out}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
