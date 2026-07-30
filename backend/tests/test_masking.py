"""Uji unit D9 — lapisan masking data sensitif.

Murni (tanpa DB/infra): `pytest tests/test_masking.py`.
"""
from __future__ import annotations

from app.ai.masking import mask_text, unmask_text


# ---------- IP ----------

def test_masks_internal_ip_but_keeps_public():
    r = mask_text("Host internal 192.168.1.10 dan publik 8.8.8.8 terbuka.")
    assert "192.168.1.10" not in r.text
    assert "[IP-INTERNAL-1]" in r.text
    assert "8.8.8.8" in r.text  # IP publik dibiarkan (konteks)


def test_internal_ip_ranges():
    for ip in ("10.0.0.5", "172.16.4.4", "127.0.0.1", "169.254.1.1"):
        r = mask_text(f"alamat {ip} ditemukan")
        assert ip not in r.text


def test_same_ip_same_placeholder():
    r = mask_text("192.168.1.10 lalu lagi 192.168.1.10")
    # Nilai sama → placeholder sama → hanya satu entri peta.
    assert r.text.count("[IP-INTERNAL-1]") == 2
    assert r.count == 1


# ---------- hostname ----------

def test_masks_internal_hostnames_keeps_public():
    r = mask_text("Server db01.corp.local dan situs www.example.com.")
    assert "db01.corp.local" not in r.text
    assert "[HOST-1]" in r.text
    assert "www.example.com" in r.text


def test_extra_client_domain_masked():
    r = mask_text("Portal di app.klienrahasia.com aktif.", extra_domains=["klienrahasia.com"])
    assert "klienrahasia.com" not in r.text
    assert "[HOST-1]" in r.text


# ---------- kredensial ----------

def test_masks_basic_auth_in_url():
    r = mask_text("Akses https://admin:S3cret!@intranet.local/panel")
    assert "admin:S3cret!" not in r.text
    assert "[CRED-1]" in r.text


def test_masks_labeled_secrets():
    r = mask_text('config: password="hunter2", api_key=AB12CD34EF')
    assert "hunter2" not in r.text
    assert "AB12CD34EF" not in r.text
    assert r.text.count("[SECRET-") >= 2


def test_masks_bearer_header():
    r = mask_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def")
    assert "eyJhbGciOiJIUzI1NiJ9.abc.def" not in r.text
    assert "Authorization: Bearer [SECRET-1]" in r.text


def test_masks_aws_key_and_private_key_block():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"
    r = mask_text(f"key AKIAIOSFODNN7EXAMPLE\n{pem}")
    assert "AKIAIOSFODNN7EXAMPLE" not in r.text
    assert "PRIVATE KEY" not in r.text


def test_masks_email():
    r = mask_text("Kontak admin@klien.local untuk detail.")
    assert "admin@klien.local" not in r.text
    assert "[EMAIL-1]" in r.text


# ---------- round-trip ----------

def test_unmask_restores_original():
    original = "Host 10.0.0.5 pada db01.corp.local, password=hunter2"
    r = mask_text(original)
    assert r.text != original
    assert unmask_text(r.text, r.mapping) == original


def test_empty_input():
    r = mask_text(None)
    assert r.text == ""
    assert r.mapping == {}
