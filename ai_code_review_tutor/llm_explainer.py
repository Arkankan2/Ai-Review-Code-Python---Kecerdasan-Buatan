import json
import time
from google import genai
from google.genai import types

# FUNGSI 1: Khusus untuk meracik Prompt (Sesuai fungsi build_prompt di proposal)
def meracik_prompt(violation):
    prompt = f"""
    Kamu adalah asisten dosen pemrograman dasar yang ramah.
    Seorang mahasiswa melakukan kesalahan penulisan kode (antipattern).

    Detail Kesalahan:
    - ID Aturan: {violation['rule_id']} ({violation['rule_name']})
    - Baris Kode: {violation['line_no']}
    - Tingkat Keparahan: {violation['severity']}
    - Potongan Kode: `{violation['snippet']}`

    Tolong berikan umpan balik edukatif dalam Bahasa Indonesia.
    
    PENTING: Kamu WAJIB mengembalikan jawabanmu HANYA dalam format JSON yang valid.
    Gunakan persis struktur key di bawah ini tanpa tambahan teks apapun di luar JSON:
    {{
        "penjelasan": "Tulis penjelasan singkat mengapa kebiasaan ini buruk di sini.",
        "kode_perbaikan": "Tulis contoh kode Python yang sudah diperbaiki di sini.",
        "latihan": "Tulis satu soal latihan singkat di sini."
    }}
    """
    return prompt

# FUNGSI 2: Fungsi Utama yang akan dipanggil oleh teman kelompokmu (GenerateFeedback)
def generate_feedback(v_star_list):
    # Kuncimu ditanam langsung di sini
    API_KEY_ASLI = "isi sendiri" # (Pastikan ini terisi kuncimu)
    client = genai.Client(api_key=API_KEY_ASLI)
    f_star_list = [] # Tempat untuk menampung semua balasan dari Gemini
    
    # Looping: Memproses setiap pelanggaran yang ditemukan temanmu satu per satu
    for v in v_star_list:
        print(f"Sedang memproses aturan {v['rule_id']} ({v['rule_name']})...")
        
        prompt_teks = meracik_prompt(v)
        
        # Kirim ke Gemini 3.5 Flash dengan instruksi WAJIB membalas pakai JSON
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt_teks,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # Ubah teks balasan JSON dari Gemini menjadi objek Python
        hasil_json = json.loads(response.text)
        
        # Simpan hasilnya, tetap membawa rule_id agar bisa dilacak (Audit Trail)
        feedback_lengkap = {
            "rule_id": v['rule_id'],
            "hasil_llm": hasil_json
        }
        
        f_star_list.append(feedback_lengkap)
        # ... (kode sebelumnya) ...
        
        hasil_json = json.loads(response.text)
        
        feedback_lengkap = {
            "rule_id": v['rule_id'],
            "hasil_llm": hasil_json
        }
        f_star_list.append(feedback_lengkap)
        
        # --- TAMBAHKAN BARIS INI ---
        # Beri jeda 15 detik agar tidak menabrak batas limit gratisan Google
        time.sleep(15) 
        
    return f_star_list