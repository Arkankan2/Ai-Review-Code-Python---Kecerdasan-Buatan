"""
sample_bad_code.py — File contoh yang sengaja melanggar SEMUA 15 antipattern rules.

** PERINGATAN **
File ini DENGAN SENGAJA mengandung banyak kesalahan. JANGAN ditulis seperti
ini di kode beneran! File ini dipakai sebagai input demo & testing untuk
AI Code Review Tutor.

Setiap blok kode dikomentari dengan ID rule yang sengaja dilanggar
(R01–R15). Saat di-analisis oleh engine, semua 15 rules harus fire.
"""

# R12: variabel global di top-level (akan diakses dengan `global` keyword di bawah)
# R02: nama satu huruf 'g' (bukan dari himpunan {i,j,k,x,y,n})
g = "admin"


def login(u):  # R02: param 'u' satu huruf; R03: tidak ada docstring
    print("debug: logging in")  # R09: print() di dalam fungsi (sisa debug)
    if u == "admin_secret_token":  # R11: string ini akan diulang → hardcoded
        return True
    if u == "admin_secret_token":  # R11: pengulangan kedua → memicu rule
        return True
    return False


def calculate_price(qty, price, discount, tax, fee, shipping):
    # R07: 6 parameter > 5
    """Hitung total harga akhir dengan diskon, pajak, dan ongkir."""
    total = qty * price * 42  # R04: magic number 42
    try:
        result = total - discount + tax + fee + shipping
    except:  # R01: bare except (tanpa tipe Exception)
        result = total
    return result


def silent_failure():
    """Demonstrasi empty except — paling berbahaya."""
    try:
        risky_op()  # noqa: F821 (sengaja undefined untuk simulasi)
    except Exception:
        pass  # R13: empty except → CRITICAL


def infinite_worker():
    """Demonstrasi infinite loop tanpa break."""
    while True:  # R14: while True tanpa break → CRITICAL
        print("working")  # R09: print di dalam fungsi


def process_items(items, cache={}):  # R08: mutable default argument (list/dict/set)
    """Simpan panjang setiap item ke cache lalu return."""
    for item in items:
        cache[item] = item
    return cache


def deeply_nested(items):
    """Demonstrasi nesting > 4 tingkat."""
    for item in items:                       # depth 1
        if item:                             # depth 2
            for ch in item:                  # depth 3
                if ch.isalpha():             # depth 4
                    if ch.islower():         # depth 5 → R05 fired
                        return ch


def long_function():
    """Demonstrasi fungsi terlalu panjang (>20 statements).

    Body diisi statement trivial supaya tidak memicu rule lain selain R06.
    Pakai assignment ke 'x' (allowed di R02) dengan nilai 0/1 (allowed di R04).
    """
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0
    x = 1
    x = 0  # statement ke-21 → R06 fired (>20)


def compute_no_return(numbers):
    """Komputasi total dan rata-rata tapi tidak ada return — kemungkinan lupa."""
    total = 0
    for n in numbers:
        total = total + n
    average = total  # R10: ada komputasi (Assign + For) tapi tidak return


def use_global():
    """Akses variabel global dengan `global` keyword."""
    global g          # R12: keyword global → anti-modularity
    g = "changed"     # R02: g satu huruf juga di sini


# ----------------------------------------------------------------------
# R15: dua fungsi berikut body-nya identik > 80% → memicu code duplication
# ----------------------------------------------------------------------
def calculate_area_rectangle(width, height):
    """Hitung luas persegi panjang."""
    result = width * height
    result = result + 0
    result = result * 1
    result = result + 0
    return result


def calculate_area_box(width, height):
    """Hitung luas kotak (sebenarnya sama dengan persegi panjang ↑)."""
    result = width * height
    result = result + 0
    result = result * 1
    result = result + 0
    return result
