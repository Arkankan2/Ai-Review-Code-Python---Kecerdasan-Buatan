"""
models.py — Struktur data inti untuk AI Code Review Tutor.

Mendefinisikan:
- Severity: enum tingkat keparahan (CRITICAL > HIGH > MEDIUM > LOW)
- Violation: representasi sebuah pelanggaran rule yang dideteksi

Catatan untuk anggota tim:
- Violation adalah "kontrak" antara Rule Engine (tugas Rezky + Andi) dan
  LLM Explainer (tugas Habel). LLM akan menerima list[Violation] sebagai
  input untuk menghasilkan feedback edukatif.
- Method to_dict() menghasilkan dict JSON-serializable yang bisa langsung
  dikirim ke UI (tugas Arkan) atau ke API LLM (tugas Habel).

Author : Kelompok AI Code Review Tutor
Course : Kecerdasan Buatan, Semester Genap 2025/2026
"""

from dataclasses import dataclass, asdict
from enum import Enum


class Severity(Enum):
    """Tingkat keparahan sebuah antipattern.

    Urutan numerik ditetapkan agar bisa di-sort: nilai lebih kecil = lebih parah.
    Dipakai oleh InferenceEngine untuk prioritisasi violations dalam output.
    """
    CRITICAL = 1   # Bug nyata / risk besar (mis. empty except, infinite loop)
    HIGH = 2       # Antipattern berbahaya (mis. bare except, mutable default)
    MEDIUM = 3     # Mengurangi kualitas (mis. magic number, long function)
    LOW = 4        # Style/best-practice (mis. missing docstring)

    def __str__(self) -> str:
        return self.name


@dataclass
class Violation:
    """
    Sebuah antipattern yang berhasil dideteksi rule engine.

    Setiap instance Violation merepresentasikan satu pelanggaran satu rule
    pada satu lokasi di kode mahasiswa. Beberapa rule bisa fire pada lokasi
    yang sama (misal `except: pass` memicu R01 DAN R13) — masing-masing
    menghasilkan Violation terpisah.

    Attributes
    ----------
    rule_id : str
        ID aturan yang dilanggar. Format: "R<nn>_<nama_singkat>"
        (mis. "R01_bare_except"). Bersifat unik dan stable — dipakai
        sebagai audit trail oleh LLM Explainer (lihat proposal §3.4).
    line_no : int
        Nomor baris (1-indexed) di kode sumber tempat violation muncul.
    severity : Severity
        Tingkat keparahan. Lihat enum Severity.
    snippet : str
        Potongan kode aktual yang melanggar rule (untuk ditampilkan ke user).
    rule_name : str
        Nama aturan dalam bahasa natural Indonesia.
    """
    rule_id: str
    line_no: int
    severity: Severity
    snippet: str
    rule_name: str

    def to_dict(self) -> dict:
        """Konversi ke dict JSON-serializable.

        Severity diubah ke string namanya supaya bisa di-serialize ke JSON
        dan dibaca langsung oleh sistem downstream (LLM prompt, UI rendering).
        """
        d = asdict(self)
        d["severity"] = str(self.severity)
        return d

    def __str__(self) -> str:
        return (f"[{self.severity}] {self.rule_id} "
                f"(line {self.line_no}): {self.rule_name}")
