"""
test_engine.py — Smoke test untuk Rule Engine.

Memverifikasi:
1. Engine bisa parse & analisis sample_bad_code.py tanpa error
2. SEMUA 15 rules berhasil fire pada sample_bad_code.py
3. Output Violation memenuhi kontrak struktural
4. Engine deterministik (jalankan 2x → hasil identik)
5. Edge case: kode kosong, kode syntax error

Cara jalankan:
    python test_engine.py

Tidak butuh pytest atau library testing eksternal — sengaja stdlib-only.

Author : Kelompok AI Code Review Tutor
Course : Kecerdasan Buatan, Semester Genap 2025/2026
"""

import sys
from pathlib import Path

from inference_engine import InferenceEngine
from knowledge_base import KnowledgeBase
from models import Severity, Violation


# ============================================================
# Helpers
# ============================================================

PASSED = []
FAILED = []


def test(label: str):
    """Decorator untuk register test."""
    def wrap(fn):
        try:
            fn()
            PASSED.append(label)
            print(f"  ✓ {label}")
        except AssertionError as e:
            FAILED.append((label, str(e)))
            print(f"  ✗ {label}")
            print(f"      → {e}")
        except Exception as e:
            FAILED.append((label, f"unexpected {type(e).__name__}: {e}"))
            print(f"  ✗ {label}  (unexpected {type(e).__name__})")
            print(f"      → {e}")
        return fn
    return wrap


# ============================================================
# Fixtures
# ============================================================

SAMPLE_PATH = Path(__file__).parent / "sample_bad_code.py"
SAMPLE_CODE = SAMPLE_PATH.read_text(encoding="utf-8")
ENGINE = InferenceEngine()


# ============================================================
# Tests
# ============================================================

print()
print("=" * 60)
print(" Test Suite: AI Code Review Tutor — Rule Engine")
print("=" * 60)
print()


@test("KB punya tepat 15 rules (sesuai proposal §3.2)")
def _():
    kb = KnowledgeBase()
    assert len(kb) == 15, f"expected 15 rules, got {len(kb)}"
    assert len(kb.per_node_rules) == 14, "expected 14 per-node rules (R01-R14)"
    assert len(kb.global_rules) == 1, "expected 1 global rule (R15)"


@test("Engine bisa analisis sample_bad_code.py tanpa exception")
def _():
    violations = ENGINE.run(SAMPLE_CODE)
    assert len(violations) > 0, "tidak ada violations sama sekali"


@test("SEMUA 15 rules fire pada sample_bad_code.py")
def _():
    violations = ENGINE.run(SAMPLE_CODE)
    fired = {v.rule_id for v in violations}
    expected = {
        "R01_bare_except", "R02_non_descriptive_name", "R03_missing_docstring",
        "R04_magic_number", "R05_deep_nesting", "R06_long_function",
        "R07_too_many_params", "R08_mutable_default", "R09_print_debug",
        "R10_no_return", "R11_hardcoded_string", "R12_global_variable",
        "R13_empty_except", "R14_infinite_loop_risk", "R15_code_duplication",
    }
    missing = expected - fired
    assert not missing, f"rules yang tidak fire: {sorted(missing)}"


@test("Setiap Violation punya struktur lengkap")
def _():
    violations = ENGINE.run(SAMPLE_CODE)
    for v in violations:
        assert isinstance(v, Violation), f"bukan Violation: {type(v)}"
        assert v.rule_id, "rule_id kosong"
        assert v.line_no > 0, f"line_no tidak valid: {v.line_no}"
        assert isinstance(v.severity, Severity), \
            f"severity bukan Severity enum: {type(v.severity)}"
        assert v.rule_name, "rule_name kosong"
        # snippet boleh kosong untuk node tertentu


@test("Output sorted: CRITICAL > HIGH > MEDIUM > LOW")
def _():
    violations = ENGINE.run(SAMPLE_CODE)
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    prev = -1
    for v in violations:
        cur = order[v.severity.name]
        assert cur >= prev, f"violation tidak terurut: {v.severity} setelah severity yg lebih kecil"
        prev = cur


@test("Engine deterministik (2 run → output identik)")
def _():
    # Pakai engine baru tiap run karena R11 menyimpan state internal
    # antar node dalam SATU run (di-reset setiap kali engine.run() dipanggil).
    v1 = InferenceEngine().run(SAMPLE_CODE)
    v2 = InferenceEngine().run(SAMPLE_CODE)
    assert len(v1) == len(v2), f"jumlah violations berbeda: {len(v1)} vs {len(v2)}"
    for a, b in zip(v1, v2):
        assert a.rule_id == b.rule_id, f"rule_id berbeda: {a.rule_id} vs {b.rule_id}"
        assert a.line_no == b.line_no, f"line_no berbeda di {a.rule_id}"


@test("Kode kosong/blank menghasilkan 0 violations")
def _():
    v = ENGINE.run("")
    assert len(v) == 0, f"expected 0, got {len(v)}"


@test("Kode bersih sederhana menghasilkan sedikit violations")
def _():
    clean = '''"""Modul bersih."""


def add(left, right):
    """Tambahkan dua angka."""
    return left + right
'''
    v = ENGINE.run(clean)
    assert len(v) == 0, f"expected 0 violations on clean code, got {len(v)}: {[x.rule_id for x in v]}"


@test("Syntax error di-raise sebagai SyntaxError")
def _():
    try:
        ENGINE.run("def broken(:")
    except SyntaxError:
        return  # expected
    raise AssertionError("seharusnya raise SyntaxError")


@test("to_dict() menghasilkan JSON-serializable dict")
def _():
    import json
    v = ENGINE.run(SAMPLE_CODE)
    for vi in v:
        d = vi.to_dict()
        # Round-trip via JSON
        json.dumps(d)
        assert d["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        assert "rule_id" in d
        assert "line_no" in d


@test("R01 fire pada `except:` tapi tidak pada `except Exception:`")
def _():
    code_a = "try:\n    pass\nexcept:\n    raise\n"
    code_b = "try:\n    pass\nexcept Exception:\n    raise\n"
    va = ENGINE.run(code_a)
    vb = ENGINE.run(code_b)
    assert any(v.rule_id == "R01_bare_except" for v in va), "R01 tidak fire pada bare except"
    assert not any(v.rule_id == "R01_bare_except" for v in vb), "R01 salah fire pada typed except"


@test("R14 NOT fire kalau while True ada break-nya")
def _():
    code = "def f():\n    while True:\n        if x():\n            break\n"
    v = ENGINE.run(code)
    assert not any(vi.rule_id == "R14_infinite_loop_risk" for vi in v), \
        "R14 salah fire padahal ada break"


@test("R02 NOT fire pada nama loop counter standar (i, j, k, x, y, n)")
def _():
    code = "for i in range(10):\n    x = i\n"
    v = ENGINE.run(code)
    r02 = [vi for vi in v if vi.rule_id == "R02_non_descriptive_name"]
    assert len(r02) == 0, f"R02 salah fire pada nama allowed: {r02}"


# ============================================================
# Ringkasan
# ============================================================
print()
print("=" * 60)
print(f" Hasil: {len(PASSED)} passed, {len(FAILED)} failed")
print("=" * 60)
if FAILED:
    print()
    for label, msg in FAILED:
        print(f"  ✗ {label}")
        print(f"      {msg}")
    sys.exit(1)
sys.exit(0)
