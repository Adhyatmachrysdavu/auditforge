# Folder terpantau (auto-ingest R3)

Folder ini di-*mount* ke kontainer `worker` sebagai `/watch`. Celery beat memindainya
tiap ~30 dtk (`watch_interval_seconds`) dan **otomatis mengurai** berkas baru — auditor
tak perlu unggah manual lewat UI.

## Cara pakai

Taruh berkas keluaran perkakas di:

```
inbox/<engagement_id>/namaberkas.ext
```

Contoh: `inbox/1/nuclei-scan.jsonl` → diserap ke penugasan **#1**. Perkakas dideteksi
otomatis (`sniff()`), jadi ekstensi/nama bebas.

Setelah diproses, berkas dipindah:

```
processed/<engagement_id>/...   ← berhasil diurai
failed/<engagement_id>/...      ← gagal (format tak dikenali / penugasan tak ada)
```

## Catatan

- Berkas yang **baru saja ditulis** (< 5 dtk, `watch_settle_seconds`) dilewati dulu agar
  tak mengurai berkas yang masih separuh tertulis.
- Subfolder yang **bukan angka** diabaikan.
- Isi `inbox/`, `processed/`, `failed/` tidak di-commit (lihat `.gitignore`).
