# AI Code Review Tutor — Rule Engine

> Komponen **AST Parser + Knowledge Base + Inference Engine (forward chaining)**
> dari proyek **Sistem AI Code Review Tutor Berbasis Rule-Based Reasoning dan LLM
> untuk Meningkatkan Kualitas Kode Mahasiswa Pemrograman Dasar (Python)**.
>
> Mata Kuliah: **Kecerdasan Buatan, Semester Genap 2025/2026**
> Institusi: **Institut Teknologi Bacharuddin Jusuf Habibie**

---

## 1. Apa yang sudah dikerjakan di folder ini?

Folder ini berisi **3 dari 5 komponen sistem** sesuai proposal §6.2:

| Komponen proposal             | Penanggung jawab    | Status di folder ini |
|-------------------------------|---------------------|----------------------|
| AST Parser + Knowledge Base   | Rezky Arya Palanni  | ✅ selesai            |
| Inference Engine (fwd chain.) | Andi Ahmad Naufal M | ✅ selesai            |
| LLM Integration               | Habel Mangopo       | ⏭ tinggal pakai output engine |
| User Interface                | Muhammad Arkan      | ⏭ tinggal pakai output JSON |
| Testing, Evaluasi, Dokumentasi| Muhammad Akmal A    | ⏭ basic test sudah ada |

Yang sudah berjalan:
- Parsing kode Python → AST (modul `ast` bawaan Python)
- 15 rules antipattern dalam Knowledge Base (sesuai proposal §3.2)
- Forward chaining engine dengan BFS traversal (sesuai proposal §3.3)
- Output deterministik dan explainable (setiap violation traceable ke `rule_id`)
- Demo CLI runner
- Sample bad code (memicu semua 15 rules saat di-test)

---

## 2. Struktur Folder

```
ai_code_review_tutor/
├── __init__.py            # Package marker
├── models.py              # Severity enum & Violation dataclass
├── parser.py              # AST parser + utilitas traversal
├── knowledge_base.py      # 15 IF-THEN rules antipattern
├── inference_engine.py    # Forward chaining engine
├── main.py                # Demo CLI runner
├── sample_bad_code.py     # File contoh: memicu SEMUA 15 rules
├── test_engine.py         # Smoke test (memverifikasi semua 15 fire)
└── README.md              # File ini
```

**Tidak ada dependency eksternal.** Sesuai janji di proposal §4.1, kami hanya
pakai standard library Python (`ast`, `collections`, `difflib`, `itertools`,
`dataclasses`, `enum`, `pathlib`, `typing`, `json`, `sys`). Cukup Python 3.8+.

---

## 3. Cara Menjalankan

### Demo cepat (rekomendasi pertama)

```bash
cd ai_code_review_tutor
python main.py
```

Output: pretty-print 22 violations dari `sample_bad_code.py`, terurut
dari `CRITICAL → HIGH → MEDIUM → LOW`. Hasil ini memvalidasi 15/15 rules fire.

### Analisis file lain

```bash
python main.py path/to/file_mahasiswa.py
```

### Output JSON (untuk anggota tim lain)

Ini format yang dipakai oleh **anggota 3 (Habel — LLM Explainer)** dan
**anggota 4 (Arkan — UI)**:

```bash
python main.py sample_bad_code.py --json > violations.json
```

Format output:
```json
{
  "source_file": "sample_bad_code.py",
  "summary": {
    "total": 22,
    "by_severity": {"CRITICAL": 2, "HIGH": 9, "MEDIUM": 8, "LOW": 3},
    "by_rule": {"R01_bare_except": 1, "R02_non_descriptive_name": 3, ...}
  },
  "violations": [
    {
      "rule_id": "R13_empty_except",
      "line_no": 42,
      "severity": "CRITICAL",
      "snippet": "except Exception:\n        pass",
      "rule_name": "Empty except (menyembunyikan error secara diam-diam)"
    },
    ...
  ]
}
```

### Mode lain

```bash
python main.py --rules          # daftar lengkap 15 rules + severity
python main.py --trace          # log rule firings (untuk presentasi/demo)
python main.py --no-color       # disable ANSI color
```

### Pakai sebagai library (untuk integrasi)

```python
from inference_engine import InferenceEngine

engine = InferenceEngine()
with open("kode_mahasiswa.py") as f:
    source = f.read()

violations = engine.run(source)
for v in violations:
    print(v.rule_id, v.line_no, v.severity, v.rule_name)
    # → "R13_empty_except 42 CRITICAL Empty except ..."
```

---

## 4. Daftar 15 Rules

| ID  | Nama Rule                | Severity | Yang dideteksi                         |
|-----|--------------------------|----------|----------------------------------------|
| R01 | bare_except              | HIGH     | `except:` tanpa tipe Exception         |
| R02 | non_descriptive_name     | MEDIUM   | Variabel/param 1 huruf (luar i,j,k,x,y,n) |
| R03 | missing_docstring        | LOW      | Fungsi tanpa docstring                 |
| R04 | magic_number             | MEDIUM   | Angka literal (selain 0, 1, -1)        |
| R05 | deep_nesting             | HIGH     | Nesting > 4 tingkat                    |
| R06 | long_function            | MEDIUM   | Fungsi > 20 statement                  |
| R07 | too_many_params          | MEDIUM   | Fungsi > 5 parameter                   |
| R08 | mutable_default          | HIGH     | Default argument list/dict/set         |
| R09 | print_debug              | LOW      | `print()` di dalam fungsi              |
| R10 | no_return                | HIGH     | Komputasi tanpa return statement       |
| R11 | hardcoded_string         | MEDIUM   | String literal berulang                |
| R12 | global_variable          | MEDIUM   | Penggunaan keyword `global`            |
| R13 | empty_except             | CRITICAL | `except: pass` (menelan error)         |
| R14 | infinite_loop_risk       | CRITICAL | `while True:` tanpa break              |
| R15 | code_duplication         | HIGH     | Dua fungsi mirip > 80% (AST signature) |

---

## 5. Bagaimana Sistem Bekerja (sesuai Proposal §3.3)

Algoritma forward chaining:

```
INPUT  : C = kode sumber mahasiswa
OUTPUT : V* = himpunan violation

1. T  <- parse_ast(C)            ← parser.py: parse_source()
2. V* <- ∅
3. QUEUE <- BFS_traverse(T)      ← parser.py: bfs_traverse()

4. FOR EACH node n IN QUEUE:
     FOR EACH rule r IN KB:
       IF r.condition(n) == TRUE:
          V* <- V* ∪ { r.generate_violation(n) }

5. JALANKAN global rules (R15)   ← rule yang butuh inspeksi seluruh tree
6. V* <- sort_by_severity(V*)
7. RETURN V*
```

Kondisi terminasi (quiescence):
**seluruh node × seluruh rule sudah dievaluasi, dan tidak ada rule baru yang
dapat difire** — sifat ini dijamin oleh sifat monotonic forward chaining
(Russell & Norvig 2010).

---

## 6. Untuk Tim — Cara Integrasi

### Habel (LLM Explainer)

Engine ini menghasilkan `List[Violation]`. Setiap Violation punya field yang
cukup untuk dibangun prompt LLM:

```python
from inference_engine import InferenceEngine

engine = InferenceEngine()
violations = engine.run(source_code)

for v in violations:
    prompt = build_prompt(
        rule_id=v.rule_id,        # ID rule (untuk audit trail)
        snippet=v.snippet,         # kode yang melanggar
        line_no=v.line_no,
        severity=str(v.severity),
        rule_name=v.rule_name,
        context="mahasiswa pemrograman dasar, Bahasa Indonesia",
    )
    feedback = llm.generate(prompt)
```

Sesuai proposal §3.4: **LLM hanya menerjemahkan output rule engine, tidak
memutuskan apakah kode bermasalah**. Field `rule_id` di setiap feedback
membentuk audit trail seperti yang dipromise di proposal §4.2.

### Arkan (UI)

Pakai mode `--json` untuk dapat struktur data yang gampang di-render:

```bash
python main.py file_user.py --json
```

Output JSON siap dikonsumsi oleh frontend (HTML/JS). Severity dikirim sebagai
string ("CRITICAL"/"HIGH"/"MEDIUM"/"LOW") yang bisa langsung di-map ke warna
badge di UI.

### Akmal (Testing & Dokumentasi)

Sudah ada `test_engine.py` sebagai smoke test (memverifikasi semua 15 rules
fire pada sample_bad_code.py). Bisa ditambah test case per-rule menggunakan
input kecil dengan format:

```python
from inference_engine import InferenceEngine
engine = InferenceEngine()
violations = engine.run('try:\n    x()\nexcept:\n    pass\n')
assert any(v.rule_id == 'R01_bare_except' for v in violations)
assert any(v.rule_id == 'R13_empty_except' for v in violations)
```

---

## 7. Justifikasi Pemenuhan Panduan Dosen

| Syarat di Panduan Tugas Dosen      | Dipenuhi oleh                                  |
|-------------------------------------|------------------------------------------------|
| Ada metode AI yang jelas            | Forward chaining (symbolic AI) di `inference_engine.py` |
| Bukan hanya LLM                     | Rule engine = inti deteksi; LLM hanya explainer (di luar folder ini) |
| Representasi masalah formal         | State (C,T,V,F) di `models.py`; rules IF-THEN di `knowledge_base.py` |
| Sistem dapat dijelaskan (explainable)| Setiap violation traceable ke `rule_id` spesifik |
| Sistem dapat dijalankan             | `python main.py` — lihat Section 3            |
| Visualisasi proses (nilai +)        | `--trace` menampilkan rule firings           |

---

## 8. Author & Penanggung Jawab Komponen

Berdasarkan pembagian di proposal §6.2:

- **Rezky Arya Palanni** (NIM 241011106) — Ketua, AST Parser + Knowledge Base
  → `parser.py`, `knowledge_base.py`, `models.py`
- **Andi Ahmad Naufal Madani** (NIM 241011128) — Inference Engine
  → `inference_engine.py`

Folder ini dirilis dalam kondisi siap-pakai oleh anggota tim lainnya.
