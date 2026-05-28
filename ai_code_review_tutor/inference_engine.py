"""
inference_engine.py — Forward Chaining Inference Engine.

Mengimplementasikan algoritma forward chaining sesuai proposal §3.3.

Sifat-sifat engine ini:
- DETERMINISTIK  : input yang sama → output yang sama (tanpa randomness)
- DATA-DRIVEN    : dimulai dari fakta (node AST), bukan dari goal/target
- EXPLAINABLE    : setiap violation traceable ke rule_id spesifik
- MONOTONIC      : sekali violation ditambah ke working memory, tidak dicabut
                   (sifat alami forward chaining — Russell & Norvig 2010)

ALGORITMA (dari proposal):
    INPUT  : C = kode sumber mahasiswa
    OUTPUT : V* = himpunan violation

    1. T  <- parse_ast(C)            # parse kode jadi AST
    2. V* <- ∅                       # inisialisasi working memory kosong
    3. QUEUE <- BFS_traverse(T)      # traversal BFS seluruh node

    4. FOR EACH node n IN QUEUE:
         FOR EACH rule r IN KB:
           IF r.condition(n) == TRUE:
              V* <- V* ∪ { r.generate_violation(n) }

    5. (extension) jalankan global rules yang tidak fit pola node-by-node
    6. V* <- sort_by_severity(V*)    # CRITICAL > HIGH > MEDIUM > LOW
    7. RETURN V*

Kondisi terminasi (quiescence):
    Seluruh node × seluruh rule sudah dievaluasi. Tidak ada rule baru
    yang bisa difire karena working memory bersifat additive: fakta yang
    ada di awal (AST) tidak berubah, dan output (violations) tidak
    me-modifikasi fakta input.

Author : Kelompok AI Code Review Tutor
Course : Kecerdasan Buatan, Semester Genap 2025/2026
Penanggung jawab modul ini: Andi Ahmad Naufal Madani (NIM 241011128)
"""

from typing import List, Optional

from models import Severity, Violation
from parser import parse_source, attach_parents, AnalysisContext
from knowledge_base import KnowledgeBase


# Urutan severity untuk sorting (lebih kecil = lebih parah, muncul lebih dulu)
_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


class InferenceEngine:
    """Forward chaining inference engine.

    Cara pakai
    ----------
    >>> from inference_engine import InferenceEngine
    >>> engine = InferenceEngine()
    >>> violations = engine.run("def f():\\n    pass\\n")
    >>> for v in violations:
    ...     print(v)

    Atau dengan custom knowledge base (mis. untuk testing subset rule):

    >>> from knowledge_base import KnowledgeBase, R01_BareExcept
    >>> kb = KnowledgeBase()
    >>> kb.per_node_rules = [R01_BareExcept()]  # hanya R01
    >>> engine = InferenceEngine(kb)
    """

    def __init__(self, knowledge_base: Optional[KnowledgeBase] = None):
        """
        Args:
            knowledge_base: KB yang akan dipakai. Jika None, pakai default
                yang berisi semua 15 rules.
        """
        self.kb: KnowledgeBase = knowledge_base or KnowledgeBase()

    # --------------------------------------------------------
    # API utama
    # --------------------------------------------------------
    def run(self, source_code: str) -> List[Violation]:
        """Eksekusi forward chaining atas source code.

        Args:
            source_code: kode Python mahasiswa (string utuh).

        Returns:
            List[Violation] terurut dari paling parah (CRITICAL) ke paling
            ringan (LOW). Dalam severity yang sama, diurut berdasarkan
            nomor baris (atas ke bawah).

        Raises:
            SyntaxError: jika kode mengandung syntax error. Engine sengaja
                tidak menangkap ini supaya caller (UI/CLI) bisa memberi pesan
                yang sesuai konteks pengguna.
        """
        # ----- STEP 1: parse + persiapan working memory -----
        tree = parse_source(source_code)
        attach_parents(tree)
        ctx = AnalysisContext(source_code, tree)

        # ----- STEP 2-4: forward chaining loop -----
        violations: List[Violation] = []

        # Loop forward chaining UTAMA (per proposal langkah 4):
        # untuk setiap fakta (node) × setiap rule, evaluasi kondisi.
        # Bila kondisi terpenuhi, hasilkan violation (langkah THEN).
        for node in ctx.bfs_nodes:
            for rule in self.kb.per_node_rules:
                if rule.condition(node, ctx):
                    violations.append(rule.make_violation(node, ctx))

        # ----- STEP 5: jalankan global rules (R15 dst) -----
        # Global rule = rule yang butuh inspeksi seluruh tree, tidak fit
        # pola "iterate per node" (mis. R15 banding-bandingkan pasangan fungsi).
        for grule in self.kb.global_rules:
            violations.extend(grule.evaluate(ctx))

        # ----- STEP 6: urutkan output berdasarkan keparahan -----
        violations.sort(
            key=lambda v: (_SEVERITY_ORDER[v.severity], v.line_no)
        )

        # ----- STEP 7: return — kondisi terminasi tercapai -----
        return violations

    # --------------------------------------------------------
    # Helper: ringkasan statistik
    # --------------------------------------------------------
    def summary(self, violations: List[Violation]) -> dict:
        """Hasilkan ringkasan statistik dari hasil run().

        Berguna untuk:
        - Header tampilan UI ("Detected 12 issues: 2 CRITICAL, 5 HIGH, ...")
        - Konteks tambahan untuk prompt LLM
        - Logging/analitik untuk evaluasi sistem (proposal §2 RM-4)
        """
        by_severity = {sev.name: 0 for sev in Severity}
        by_rule: dict = {}
        for v in violations:
            by_severity[v.severity.name] += 1
            by_rule[v.rule_id] = by_rule.get(v.rule_id, 0) + 1
        return {
            "total": len(violations),
            "by_severity": by_severity,
            "by_rule": by_rule,
        }

    # --------------------------------------------------------
    # Helper: trace/debugging (penjelasan alur inference)
    # --------------------------------------------------------
    def trace(self, source_code: str) -> dict:
        """Hasilkan log "fired rules" untuk demo/dokumentasi/presentasi.

        Berguna saat presentasi: tunjukkan ke dosen bahwa engine memang
        deterministik dan tiap violation bisa di-trace.

        Return format:
            {
              "ast_node_count": int,
              "rule_firings": [{node_type, line_no, rule_id, rule_name}, ...]
            }
        """
        tree = parse_source(source_code)
        attach_parents(tree)
        ctx = AnalysisContext(source_code, tree)

        firings = []
        for node in ctx.bfs_nodes:
            for rule in self.kb.per_node_rules:
                if rule.condition(node, ctx):
                    firings.append({
                        "node_type": type(node).__name__,
                        "line_no": getattr(node, "lineno", None),
                        "rule_id": rule.rule_id,
                        "rule_name": rule.rule_name,
                    })
        # Global rules: laporkan firing dari evaluate()
        for grule in self.kb.global_rules:
            for v in grule.evaluate(ctx):
                firings.append({
                    "node_type": "(global)",
                    "line_no": v.line_no,
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                })

        return {
            "ast_node_count": len(ctx.bfs_nodes),
            "rule_firings": firings,
        }
