"""
parser.py — AST Parser dan utilitas traversal.

Modul ini menyediakan:
1. parse_source(): parse string kode Python jadi AST
2. attach_parents(): pasang referensi parent ke setiap node
   (penting untuk rule yang butuh context, mis. R04 perlu tahu apakah
    sebuah angka ada di dalam range())
3. bfs_traverse(): traversal Breadth-First Search atas AST,
   sesuai dengan algoritma forward chaining di proposal §3.3
4. Helper functions: nesting_depth, is_inside_function, has_break,
   is_constant_true, find_strings_in_compare_or_assign
5. AnalysisContext: container info global yang dishare antar rules

Modul ini menggunakan HANYA standard library Python (ast, collections,
difflib) sesuai dengan klaim di proposal §4.1 — tidak ada dependency eksternal.

Author : Kelompok AI Code Review Tutor
Course : Kecerdasan Buatan, Semester Genap 2025/2026
"""

import ast
from collections import deque
from typing import Dict, List


# ============================================================
# Konstruksi AST
# ============================================================

def parse_source(source: str) -> ast.AST:
    """Parse kode Python (string) menjadi AST root node.

    Args:
        source: Kode sumber Python (string utuh).

    Returns:
        AST root node (instance ast.Module).

    Raises:
        SyntaxError: jika kode mengandung syntax error.
        Tidak ditangkap di sini — caller (mis. main.py) yang bertanggung
        jawab memberi pesan ramah ke user.
    """
    return ast.parse(source)


def attach_parents(tree: ast.AST) -> None:
    """Pasang atribut `_parent` ke setiap node sebagai referensi ke parent-nya.

    Mekanisme ini WAJIB dipanggil sebelum traversal karena banyak rule
    yang butuh inspeksi parent (mis. R04 perlu tahu apakah angka ada
    di dalam `range()`; R11 perlu cari Compare/Assign ke atas).

    Implementasi:
        Iterasi BFS: untuk setiap node, set _parent pada semua child-nya.

    Catatan: parent dari root (Module) tetap tidak diset (akses
    via getattr(node, '_parent', None) akan mengembalikan None).
    """
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            # AST nodes mendukung atribut dinamis — assignment ini aman.
            child._parent = parent


# ============================================================
# Traversal
# ============================================================

def bfs_traverse(tree: ast.AST) -> List[ast.AST]:
    """Traversal Breadth-First Search atas seluruh AST.

    Menghasilkan list node dalam urutan level-order (root → children → grandchildren).
    Ini sesuai algoritma forward chaining di proposal §3.3 langkah 3.

    Mengapa BFS, bukan DFS?
    --------------------
    BFS memastikan node "luar" (mis. FunctionDef) dievaluasi sebelum
    node "dalam" (mis. statements di body fungsi). Ini relevan untuk
    rule yang sifatnya struktural seperti R06 (long function) dan R07
    (too many params) — sehingga prioritas inferensi mengalir dari
    bentuk besar ke detail kecil.
    """
    result: List[ast.AST] = []
    queue: deque = deque([tree])
    while queue:
        node = queue.popleft()
        result.append(node)
        for child in ast.iter_child_nodes(node):
            queue.append(child)
    return result


# ============================================================
# Ekstraksi snippet
# ============================================================

def get_snippet(node: ast.AST, source: str, max_lines: int = 3) -> str:
    """Ekstrak potongan kode aktual yang menjadi tempat node.

    Args:
        node: AST node yang sudah dievaluasi melanggar rule.
        source: kode sumber original (string utuh).
        max_lines: batas baris snippet — supaya tidak overwhelming
            di UI/output untuk fungsi yang panjang.

    Returns:
        String snippet kode (sudah di-strip).
    """
    if not hasattr(node, "lineno"):
        return ""
    lines = source.splitlines()
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno) - 1
    end = min(end, start + max_lines - 1, len(lines) - 1)
    snippet_lines = lines[start:end + 1]
    return "\n".join(snippet_lines).strip()


# ============================================================
# Helper rules
# ============================================================

# Tipe node yang dianggap sebagai "lapisan nesting"
_NESTING_TYPES = (
    ast.For, ast.AsyncFor, ast.While, ast.If,
    ast.Try, ast.With, ast.AsyncWith,
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
)


def nesting_depth(node: ast.AST) -> int:
    """Hitung kedalaman nesting node dari root ke node ini.

    Catatan: attach_parents() harus sudah dipanggil sebelumnya.

    Logika: walk up parent chain, hitung jumlah ancestor yang termasuk
    _NESTING_TYPES. Module sendiri tidak dihitung sebagai depth.
    """
    depth = 0
    current = getattr(node, "_parent", None)
    while current is not None:
        if isinstance(current, _NESTING_TYPES):
            depth += 1
        current = getattr(current, "_parent", None)
    return depth


def is_inside_function(node: ast.AST) -> bool:
    """True jika node berada di dalam FunctionDef atau AsyncFunctionDef.

    Dipakai oleh R09 (print sebagai debug) untuk memastikan print
    yang di top-level Module tidak salah-flag.
    """
    current = getattr(node, "_parent", None)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return True
        current = getattr(current, "_parent", None)
    return False


def has_break(loop_node: ast.AST) -> bool:
    """Cek apakah ada `break` di body loop ini (bukan di nested loop).

    Penting:
    --------
    `break` di dalam nested loop TIDAK menghentikan outer loop, jadi kita
    harus skip nested loops saat traversal. Tanpa ini, R14 akan keliru:
    `while True: for ...: break` akan dianggap aman padahal break-nya
    tidak menghentikan outer while.
    """
    def _walk(n: ast.AST) -> bool:
        if isinstance(n, ast.Break):
            return True
        # Skip masuk ke nested loop (kecuali node ini sendiri adalah loop target)
        if n is not loop_node and isinstance(n, (ast.For, ast.While, ast.AsyncFor)):
            return False
        # Skip masuk ke nested function/class (scope yang berbeda)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False
        for child in ast.iter_child_nodes(n):
            if _walk(child):
                return True
        return False
    return _walk(loop_node)


def is_constant_true(node: ast.AST) -> bool:
    """Cek apakah node merepresentasikan konstanta True (untuk R14).

    Mengakomodasi: `True`, `1` (integer literal).
    Tidak mengakomodasi: variable yang nilainya True (itu bukan literal).

    Catatan kompatibilitas: di Python 3.7-, ast.NameConstant dan ast.Num
    masih ada (sekarang sudah deprecated tapi tidak dihapus).
    """
    if isinstance(node, ast.Constant):
        # bool dulu (karena bool is int subclass — cek ini lebih dulu)
        if isinstance(node.value, bool):
            return node.value is True
        if isinstance(node.value, int):
            return node.value == 1
        return False
    return False


def find_strings_in_compare_or_assign(tree: ast.AST) -> Dict[str, int]:
    """Hitung kemunculan setiap string literal dalam konteks Compare/Assign.

    Output: dict {string_value: jumlah_kemunculan}.

    Dipakai oleh R11 (hardcoded_string) untuk memutuskan apakah string
    "is_repeated" — string yang muncul ≥2 kali dalam konteks ini layak
    dijadikan konstanta bernama.

    Algoritma:
    ---------
    Untuk setiap ast.Constant berisi string, walk UP parent chain.
    Jika ketemu Compare atau Assign sebelum menyentuh boundary (FunctionDef/
    ClassDef/Module), increment counter untuk string itu.
    """
    counts: Dict[str, int] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        parent = getattr(node, "_parent", None)
        while parent is not None:
            if isinstance(parent, (ast.Compare, ast.Assign)):
                counts[node.value] = counts.get(node.value, 0) + 1
                break
            # Boundary: jangan tembus ke parent yang jauh
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef, ast.Module)):
                break
            parent = getattr(parent, "_parent", None)
    return counts


# ============================================================
# Context object (working memory pendamping)
# ============================================================

class AnalysisContext:
    """Container info global yang dipakai oleh rules selama analisis.

    Konsepnya mirip "working memory" pada sistem pakar klasik
    (lihat Russell & Norvig 2010 — referensi di proposal):
    selain working memory utama (yaitu set Violation), beberapa rule
    butuh info "lookup" yang dihitung sekali di awal (mis. R11 butuh
    daftar kemunculan string).

    Attributes
    ----------
    source : str
        Kode sumber original (untuk ekstraksi snippet).
    tree : ast.AST
        AST root setelah parent attachment.
    bfs_nodes : List[ast.AST]
        List seluruh node dalam urutan BFS, di-cache supaya tidak perlu
        traversal ulang per rule.
    string_counts : Dict[str, int]
        Cache hitungan string literal untuk R11.
    scratch : Dict[str, object]
        "Working memory" per-run: rules yang butuh state lintas-node DALAM
        satu run (mis. R11 perlu ingat string apa yang sudah di-flag supaya
        tidak double) menyimpannya di sini. Setiap engine.run() bikin ctx
        baru → rules tetap stateless di luar konteks satu analisis.
    """

    def __init__(self, source: str, tree: ast.AST):
        self.source = source
        self.tree = tree
        self.bfs_nodes: List[ast.AST] = bfs_traverse(tree)
        self.string_counts: Dict[str, int] = find_strings_in_compare_or_assign(tree)
        self.scratch: Dict[str, object] = {}
