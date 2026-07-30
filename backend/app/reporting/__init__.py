"""Generator laporan AuditForge (D15+).

Menyusun data laporan deterministik dari temuan yang telah ditinjau auditor, lalu
merender ke DOCX (D15) — dengan letterhead brand yang dapat dikonfigurasi runtime.
Prinsip: laporan hanya memuat temuan yang DISETUJUI auditor (bukan draf mentah).
"""
