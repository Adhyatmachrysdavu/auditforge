"""Uji unit D16 — grafik SVG laporan (deterministik, tanpa dependensi sistem)."""
from __future__ import annotations

from app.reporting.charts import matrix_from, risk_matrix_svg, severity_bar_svg


def test_severity_bar_contains_svg_and_values():
    svg = severity_bar_svg({"critical": 2, "low": 5})
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "<rect" in svg
    assert ">2<" in svg and ">5<" in svg  # nilai count muncul


def test_severity_bar_empty():
    svg = severity_bar_svg({})
    assert svg.startswith("<svg") and "</svg>" in svg
    assert "<rect" not in svg


def test_matrix_from_counts_and_defaults():
    cells = matrix_from([("critical", 1), ("critical", 1), ("high", 2), ("low", None), ("x", 9)])
    assert cells[("critical", 1)] == 2
    assert cells[("high", 2)] == 1
    assert cells[("low", 4)] == 1  # prioritas None → P4
    assert cells[("x", 4)] == 1  # prioritas tak valid → P4


def test_risk_matrix_svg_headers_and_cells():
    svg = risk_matrix_svg(matrix_from([("critical", 1), ("info", 4)]))
    assert svg.startswith("<svg")
    for p in ("P1", "P2", "P3", "P4"):
        assert f">{p}<" in svg
    assert "Critical" in svg and "Info" in svg
