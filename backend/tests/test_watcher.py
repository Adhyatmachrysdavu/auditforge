"""Uji unit R3 — logika pemindai folder terpantau (tanpa DB/MinIO/Celery)."""
from __future__ import annotations

import os
import time
from pathlib import Path

from app.ingest.watcher import iter_inbox_files, move_result


def _touch(path: Path, *, age: float = 0.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"data")
    if age:
        old = time.time() - age
        os.utime(path, (old, old))
    return path


def test_iter_picks_stable_files_under_numeric_dirs(tmp_path):
    base = tmp_path
    _touch(base / "inbox" / "1" / "a.json", age=10)
    _touch(base / "inbox" / "2" / "b.xml", age=10)
    found = sorted((eid, p.name) for eid, p in iter_inbox_files(base, settle_seconds=5))
    assert found == [(1, "a.json"), (2, "b.xml")]


def test_iter_skips_recently_written_files(tmp_path):
    base = tmp_path
    _touch(base / "inbox" / "1" / "fresh.json", age=0)  # baru ditulis → dilewati
    _touch(base / "inbox" / "1" / "old.json", age=10)
    found = [p.name for _, p in iter_inbox_files(base, settle_seconds=5)]
    assert found == ["old.json"]


def test_iter_ignores_non_numeric_subdirs(tmp_path):
    base = tmp_path
    _touch(base / "inbox" / "notanid" / "x.json", age=10)
    _touch(base / "inbox" / "3" / "y.json", age=10)
    found = [eid for eid, _ in iter_inbox_files(base, settle_seconds=5)]
    assert found == [3]


def test_iter_empty_when_no_inbox(tmp_path):
    assert list(iter_inbox_files(tmp_path)) == []


def test_move_result_processed_and_failed(tmp_path):
    base = tmp_path
    ok_file = _touch(base / "inbox" / "1" / "good.json", age=10)
    bad_file = _touch(base / "inbox" / "1" / "bad.json", age=10)

    dest_ok = move_result(ok_file, base, 1, ok=True)
    dest_bad = move_result(bad_file, base, 1, ok=False)

    assert dest_ok == base / "processed" / "1" / "good.json"
    assert dest_bad == base / "failed" / "1" / "bad.json"
    assert dest_ok.exists() and not ok_file.exists()
    assert dest_bad.exists() and not bad_file.exists()


def test_move_result_no_overwrite(tmp_path):
    base = tmp_path
    (base / "processed" / "1").mkdir(parents=True)
    (base / "processed" / "1" / "dup.json").write_bytes(b"existing")
    incoming = _touch(base / "inbox" / "1" / "dup.json", age=10)

    dest = move_result(incoming, base, 1, ok=True)
    # Tidak menimpa berkas lama: tujuan mendapat sufiks unik.
    assert dest.name != "dup.json"
    assert (base / "processed" / "1" / "dup.json").read_bytes() == b"existing"
