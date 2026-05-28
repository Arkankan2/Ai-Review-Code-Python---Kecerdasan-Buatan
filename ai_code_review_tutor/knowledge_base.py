"""
knowledge_base.py — Knowledge Base berisi 15 RULES Antipattern.

Setiap rule = sebuah IF-THEN production rule dari proposal §3.2.
Implementasi: Object-Oriented dengan inheritance untuk reusability:

    Rule (ABC)
    ├── PerNodeRule  → dievaluasi terhadap setiap node AST
    │       (R01–R14)
    └── GlobalRule   → dievaluasi atas seluruh tree
            (R15 — code duplication)

Setiap PerNodeRule memenuhi kontrak:
    - rule_id, rule_name, severity (class-level metadata)
    - condition(node, ctx) -> bool : KOMPONEN "IF"
    - make_violation(node, ctx)    : KOMPONEN "THEN" (auto, dari Rule)

GlobalRule memenuhi:
    - evaluate(ctx) -> List[Violation]

Pemisahan ini penting: R15 tidak fit pola "iterate node, check rule"
karena harus membandingkan PASANGAN fungsi, bukan single node.

Author : Kelompok AI Code Review Tutor
Course : Kecerdasan Buatan, Semester Genap 2025/2026
"""

import ast
import difflib
from abc import ABC, abstractmethod
from itertools import combinations
from typing import List, Set

from models import Severity, Violation
from parser import (
    AnalysisContext, get_snippet, nesting_depth,
    is_inside_function, has_break, is_constant_true,
)


# ============================================================
# Base classes
# ============================================================

class Rule(ABC):
    """Abstract base untuk semua rules. Tidak dipakai langsung."""
    rule_id: str = ""
    rule_name: str = ""
    severity: Severity = Severity.LOW


class PerNodeRule(Rule):
    """Rule yang dievaluasi sekali per AST node.

    Subclass cukup mendefinisikan condition(); generate_violation() sudah
    di-default-kan. Jika perlu format snippet khusus, override
    make_violation().
    """

    @abstractmethod
    def condition(self, node: ast.AST, ctx: AnalysisContext) -> bool:
        """Komponen IF: True jika node ini melanggar rule.

        Tidak boleh memodifikasi node, ctx, maupun state global.
        Harus deterministik (input sama → output sama).
        """

    def make_violation(self, node: ast.AST, ctx: AnalysisContext) -> Violation:
        """Komponen THEN: hasilkan Violation dari node."""
        return Violation(
            rule_id=self.rule_id,
            line_no=getattr(node, "lineno", 0),
            severity=self.severity,
            snippet=get_snippet(node, ctx.source),
            rule_name=self.rule_name,
        )


class GlobalRule(Rule):
    """Rule yang butuh inspeksi seluruh tree (bukan satu node)."""

    @abstractmethod
    def evaluate(self, ctx: AnalysisContext) -> List[Violation]:
        """Hasilkan SEMUA violation rule ini dari satu kali traversal."""


# ============================================================
# RULES R01 — R14 (per-node)
# ============================================================

class R01_BareExcept(PerNodeRule):
    """`except:` tanpa tipe exception — menangkap SEMUA error termasuk
    KeyboardInterrupt dan SystemExit. Sangat berbahaya untuk debugging."""
    rule_id = "R01_bare_except"
    rule_name = "Bare except (except tanpa tipe Exception)"
    severity = Severity.HIGH

    def condition(self, node, ctx):
        return isinstance(node, ast.ExceptHandler) and node.type is None


class R02_NonDescriptiveName(PerNodeRule):
    """Nama variabel/parameter satu huruf di luar konvensi loop counter."""
    rule_id = "R02_non_descriptive_name"
    rule_name = "Nama variabel tidak deskriptif (1 huruf)"
    severity = Severity.MEDIUM
    ALLOWED = {"i", "j", "k", "x", "y", "n", "_"}

    def condition(self, node, ctx):
        # Target 1: argumen fungsi (def f(x): ...)
        if isinstance(node, ast.arg):
            return len(node.arg) == 1 and node.arg not in self.ALLOWED
        # Target 2: variabel sisi kiri assignment (x = ...)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            return len(node.id) == 1 and node.id not in self.ALLOWED
        return False

    def make_violation(self, node, ctx):
        v = super().make_violation(node, ctx)
        # Tambahkan info nama yang bermasalah ke snippet untuk kejelasan
        name = node.arg if isinstance(node, ast.arg) else node.id
        v.snippet = f"nama: '{name}'   →   {v.snippet}"
        return v


class R03_MissingDocstring(PerNodeRule):
    """Fungsi tanpa docstring — sulit dipahami orang lain (atau diri sendiri
    di masa depan)."""
    rule_id = "R03_missing_docstring"
    rule_name = "Fungsi tanpa docstring"
    severity = Severity.LOW

    def condition(self, node, ctx):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        if not node.body:
            return True
        first = node.body[0]
        return not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )


class R04_MagicNumber(PerNodeRule):
    """Angka literal di tengah kode tanpa nama variabel/konstanta —
    pembacanya tidak tahu maksud angka itu."""
    rule_id = "R04_magic_number"
    rule_name = "Magic Number (angka tanpa nama/konteks)"
    severity = Severity.MEDIUM
    ALLOWED = {0, 1, -1}  # nilai-nilai trivial yang biasa muncul (per proposal)

    def condition(self, node, ctx):
        if not isinstance(node, ast.Constant):
            return False
        # bool adalah subclass int → cek dan exclude
        if isinstance(node.value, bool):
            return False
        if not isinstance(node.value, (int, float)):
            return False
        if node.value in self.ALLOWED:
            return False

        parent = getattr(node, "_parent", None)
        # Skip jika ada di dalam pemanggilan range()
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name):
            if parent.func.id == "range":
                return False
        # Skip jika ini standalone Expr (kemungkinan number docstring/typo)
        if isinstance(parent, ast.Expr):
            return False
        return True


class R05_DeepNesting(PerNodeRule):
    """Nesting > 4 tingkat — kode sulit dibaca dan diuji."""
    rule_id = "R05_deep_nesting"
    rule_name = "Nesting terlalu dalam (>4 tingkat)"
    severity = Severity.HIGH

    def condition(self, node, ctx):
        # Hanya cek pada node "kontainer" supaya tidak triple-flag children
        if not isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            return False
        return nesting_depth(node) > 4


class R06_LongFunction(PerNodeRule):
    """Fungsi dengan >20 statements — sulit di-review dan biasanya melanggar
    Single Responsibility Principle."""
    rule_id = "R06_long_function"
    rule_name = "Fungsi terlalu panjang (>20 statement)"
    severity = Severity.MEDIUM
    MAX_BODY = 20

    def condition(self, node, ctx):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        return len(node.body) > self.MAX_BODY


class R07_TooManyParams(PerNodeRule):
    """Fungsi dengan >5 parameter — kemungkinan besar perlu dipecah atau
    parameter perlu dibungkus dalam objek/dict."""
    rule_id = "R07_too_many_params"
    rule_name = "Fungsi punya terlalu banyak parameter (>5)"
    severity = Severity.MEDIUM
    MAX_PARAMS = 5

    def condition(self, node, ctx):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        return len(node.args.args) > self.MAX_PARAMS


class R08_MutableDefault(PerNodeRule):
    """Default argument berupa list/dict/set — bug klasik Python:
    default object dishare antar pemanggilan."""
    rule_id = "R08_mutable_default"
    rule_name = "Default argument mutable (list/dict/set)"
    severity = Severity.HIGH

    def condition(self, node, ctx):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                return True
        return False


class R09_PrintDebug(PerNodeRule):
    """Pemanggilan print() di dalam fungsi — biasanya sisa debugging
    yang lupa dihapus."""
    rule_id = "R09_print_debug"
    rule_name = "print() di dalam fungsi (kemungkinan sisa debug)"
    severity = Severity.LOW

    def condition(self, node, ctx):
        if not isinstance(node, ast.Call):
            return False
        if not isinstance(node.func, ast.Name):
            return False
        if node.func.id != "print":
            return False
        return is_inside_function(node)


class R10_NoReturn(PerNodeRule):
    """Fungsi melakukan komputasi (Assign/AugAssign/loop) tapi tidak ada
    return — kemungkinan lupa, atau seharusnya jadi prosedur saja."""
    rule_id = "R10_no_return"
    rule_name = "Fungsi melakukan komputasi tapi tidak ada return"
    severity = Severity.HIGH

    def condition(self, node, ctx):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False

        # Apakah fungsi punya return statement?
        has_return = False
        has_computation = False
        for child in ast.walk(node):
            if child is node:
                continue
            # Jangan masuk ke nested function (scope yang berbeda)
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(child, ast.Return):
                has_return = True
            if isinstance(child, (ast.Assign, ast.AugAssign, ast.For, ast.While)):
                has_computation = True

        return has_computation and not has_return


class R11_HardcodedString(PerNodeRule):
    """String literal yang dipakai >1 kali dalam Compare/Assign — sebaiknya
    diekstrak jadi konstanta bernama supaya bila berubah cukup edit di satu
    tempat dan maknanya jelas."""
    rule_id = "R11_hardcoded_string"
    rule_name = "String literal yang berulang (sebaiknya jadi konstanta)"
    severity = Severity.MEDIUM

    # Key untuk ctx.scratch — supaya state per-run, bukan per-instance.
    _SCRATCH_KEY = "_r11_flagged"

    def condition(self, node, ctx):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            return False
        # Skip string kosong / sangat pendek (biasanya sentinel, bukan magic)
        if len(node.value) < 2:
            return False

        # Apakah node ini ada di dalam Compare atau Assign?
        parent = getattr(node, "_parent", None)
        in_compare_or_assign = False
        while parent is not None:
            if isinstance(parent, (ast.Compare, ast.Assign)):
                in_compare_or_assign = True
                break
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef, ast.Module)):
                break
            parent = getattr(parent, "_parent", None)

        if not in_compare_or_assign:
            return False
        # is_repeated?
        if ctx.string_counts.get(node.value, 0) < 2:
            return False

        # State per-run disimpan di ctx.scratch (bukan di self) supaya
        # rule instance bisa dipakai berulang kali tanpa state leak.
        flagged: Set[str] = ctx.scratch.setdefault(self._SCRATCH_KEY, set())
        if node.value in flagged:
            return False
        flagged.add(node.value)
        return True


class R12_GlobalVariable(PerNodeRule):
    """Penggunaan keyword `global` — merusak modularity, sulit di-test,
    sumber bug yang sulit dilacak."""
    rule_id = "R12_global_variable"
    rule_name = "Penggunaan keyword `global` (merusak modularity)"
    severity = Severity.MEDIUM

    def condition(self, node, ctx):
        return isinstance(node, ast.Global)


class R13_EmptyExcept(PerNodeRule):
    """`except ...: pass` — menelan error tanpa jejak. Bug yang
    terjadi di dalam try akan hilang tanpa pesan apa pun."""
    rule_id = "R13_empty_except"
    rule_name = "Empty except (menyembunyikan error secara diam-diam)"
    severity = Severity.CRITICAL

    def condition(self, node, ctx):
        if not isinstance(node, ast.ExceptHandler):
            return False
        if len(node.body) != 1:
            return False
        return isinstance(node.body[0], ast.Pass)


class R14_InfiniteLoopRisk(PerNodeRule):
    """`while True:` tanpa `break` di body — program tidak akan pernah
    berhenti dengan sendirinya."""
    rule_id = "R14_infinite_loop_risk"
    rule_name = "Risiko infinite loop (while True tanpa break)"
    severity = Severity.CRITICAL

    def condition(self, node, ctx):
        if not isinstance(node, ast.While):
            return False
        if not is_constant_true(node.test):
            return False
        return not has_break(node)


# ============================================================
# RULE R15 (global)
# ============================================================

class R15_CodeDuplication(GlobalRule):
    """Dua atau lebih fungsi dengan body yang mirip >80% — kandidat refactor:
    ekstrak ke helper function.

    Algoritma:
    ---------
    1. Kumpulkan semua FunctionDef yang body-nya >= MIN_BODY_LEN
    2. Untuk setiap pasangan (f1, f2):
         a. Hitung "signature" body = "\\n".join(ast.dump(stmt))
            (ast.dump menormalisasi struktur — variabel/literal jadi bagian
            dari string, jadi fungsi dengan struktur identik akan punya
            signature sama; perbedaan minor → ratio tinggi)
         b. Bandingkan signature dengan difflib.SequenceMatcher
         c. Jika ratio > THRESHOLD: tambah Violation untuk kedua fungsi
    3. Setiap fungsi hanya di-flag SEKALI walau ditemukan duplikat dengan
       beberapa fungsi lain.

    Pemilihan threshold 0.8 dan MIN_BODY_LEN=4: sesuai proposal §3.2 R15.
    """
    rule_id = "R15_code_duplication"
    rule_name = "Duplikasi kode (similarity >80% antar fungsi)"
    severity = Severity.HIGH
    THRESHOLD = 0.8
    MIN_BODY_LEN = 4

    def _body_signature(self, func: ast.FunctionDef) -> str:
        """Hasilkan signature string dari body sebuah fungsi.

        Pakai ast.dump dengan annotate_fields=False supaya output lebih
        ringkas dan lebih sensitif ke perbedaan struktur.
        """
        return "\n".join(
            ast.dump(stmt, annotate_fields=False) for stmt in func.body
        )

    def evaluate(self, ctx: AnalysisContext) -> List[Violation]:
        funcs: List[ast.FunctionDef] = [
            n for n in ctx.bfs_nodes
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and len(n.body) >= self.MIN_BODY_LEN
        ]

        violations: List[Violation] = []
        flagged: Set[int] = set()   # id(node) yang sudah di-flag

        for f1, f2 in combinations(funcs, 2):
            sig1 = self._body_signature(f1)
            sig2 = self._body_signature(f2)
            ratio = difflib.SequenceMatcher(None, sig1, sig2).ratio()
            if ratio <= self.THRESHOLD:
                continue
            for f in (f1, f2):
                if id(f) in flagged:
                    continue
                flagged.add(id(f))
                violations.append(Violation(
                    rule_id=self.rule_id,
                    line_no=f.lineno,
                    severity=self.severity,
                    snippet=(f"def {f.name}(...):  "
                             f"# mirip dengan fungsi lain (ratio={ratio:.2f})"),
                    rule_name=self.rule_name,
                ))
        return violations


# ============================================================
# Knowledge Base — container 15 rules
# ============================================================

class KnowledgeBase:
    """Kumpulan semua rules yang aktif.

    Dipakai oleh InferenceEngine. Jika tim ingin menambah/menonaktifkan
    rule, cukup edit list di __init__ (open-closed principle).
    """

    def __init__(self):
        self.per_node_rules: List[PerNodeRule] = [
            R01_BareExcept(),
            R02_NonDescriptiveName(),
            R03_MissingDocstring(),
            R04_MagicNumber(),
            R05_DeepNesting(),
            R06_LongFunction(),
            R07_TooManyParams(),
            R08_MutableDefault(),
            R09_PrintDebug(),
            R10_NoReturn(),
            R11_HardcodedString(),
            R12_GlobalVariable(),
            R13_EmptyExcept(),
            R14_InfiniteLoopRisk(),
        ]
        self.global_rules: List[GlobalRule] = [
            R15_CodeDuplication(),
        ]

    @property
    def all_rules(self) -> List[Rule]:
        return list(self.per_node_rules) + list(self.global_rules)

    def __len__(self) -> int:
        return len(self.per_node_rules) + len(self.global_rules)

    def describe(self) -> List[dict]:
        """Hasilkan metadata semua rules untuk dokumentasi/UI."""
        return [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "severity": str(r.severity),
            }
            for r in self.all_rules
        ]
