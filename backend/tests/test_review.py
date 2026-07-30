"""Uji unit D13 — mesin status review + batas persetujuan peran (pure)."""
from __future__ import annotations

from app.review import (
    can_transition,
    is_valid_status,
    role_allows_transition,
)


def test_valid_status():
    assert is_valid_status("approved")
    assert not is_valid_status("selesai")


def test_forward_flow_allowed():
    assert can_transition("draft", "in_review")
    assert can_transition("in_review", "approved")
    assert can_transition("in_review", "rejected")
    assert can_transition("in_review", "false_positive")


def test_illegal_shortcuts_blocked():
    assert not can_transition("draft", "approved")  # tak boleh lompat
    assert not can_transition("approved", "rejected")
    assert not can_transition("draft", "draft")  # tak berubah


def test_reopen_allowed():
    assert can_transition("approved", "in_review")
    assert can_transition("rejected", "in_review")
    assert can_transition("false_positive", "in_review")
    assert can_transition("in_review", "draft")


def test_approval_requires_auditor():
    for target in ("approved", "rejected", "false_positive"):
        assert role_allows_transition("auditor", target)
        assert role_allows_transition("admin", target)
        assert not role_allows_transition("analyst", target)


def test_submit_allowed_for_analyst():
    assert role_allows_transition("analyst", "in_review")
    assert role_allows_transition("auditor", "in_review")


def test_unknown_role_denied():
    assert not role_allows_transition("guest", "in_review")
    assert not role_allows_transition("guest", "approved")
