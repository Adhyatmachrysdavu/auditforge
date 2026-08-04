"""Uji unit Modul 2 — keputusan akses penugasan (tanpa DB)."""
from __future__ import annotations

from app.access import can_access_engagement


def test_admin_sees_everything_without_membership():
    assert can_access_engagement(role="admin", is_member=False) is True


def test_member_can_access():
    assert can_access_engagement(role="auditor", is_member=True) is True
    assert can_access_engagement(role="analyst", is_member=True) is True


def test_non_member_denied_even_as_auditor():
    # Peran tinggi tidak memberi akses ke penugasan yang bukan miliknya.
    assert can_access_engagement(role="auditor", is_member=False) is False


def test_non_member_analyst_denied():
    assert can_access_engagement(role="analyst", is_member=False) is False


def test_unknown_role_denied():
    # Fail-closed: peran yang tak dikenal tidak pernah lolos tanpa keanggotaan.
    assert can_access_engagement(role="", is_member=False) is False
    assert can_access_engagement(role="superuser", is_member=False) is False
