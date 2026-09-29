"""Konfigurasi cocbot — dibaca dari cocbot_config.json (atau default)."""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "cocbot_config.json")

DEFAULTS = {
    # Package CoC (jangan diubah kecuali Supercell ganti)
    "coc_package": "com.supercell.clashofclans",
    # Posisi ikon CoC di home screen (fraksi 0-1 dari lebar/tinggi layar).
    # Dipakai tombol "buka CoC". Isi sesuai HP kamu, atau kosongkan.
    "coc_icon": None,

    # Kecepatan loop bot (detik). Lebih kecil = lebih real-time, tapi lebih berat.
    "poll_menu": 1.0,
    "poll_battle": 0.5,

    # Waktu tunggu maksimum tiap tahap (detik)
    "timeout_find_match": 25,
    "timeout_battle": 200,

    # Farming: jumlah tap tombol "Next" sebelum menyerang (0 = langsung serang).
    # v1 buta loot — ini seleksi kasar. OCR loot menyusul.
    "farming_next_count": 0,

    # Slot troops di battle-prep (fraksi x,y). Sesuaikan urutan army kamu.
    # Contoh: 5 slot goblin -> archer -> barbarian -> giant -> wallbreaker
    "slots": [
        {"name": "troop_1", "x": 0.10, "y": 0.925},
        {"name": "troop_2", "x": 0.20, "y": 0.925},
        {"name": "troop_3", "x": 0.30, "y": 0.925},
        {"name": "troop_4", "x": 0.40, "y": 0.925},
        {"name": "troop_5", "x": 0.50, "y": 0.925},
    ],

    # Koordinat tombol UI CoC (fraksi 0-1). Layout CoC stabil antar device.
    # Kalau meleset di HP kamu, ubah di sini (atau pakai template matching).
    "ui": {
        "attack_button": [0.075, 0.62],     # tombol Attack di home village
        "find_match": [0.72, 0.80],         # "Find a match" (multiplayer)
        "next_button": [0.83, 0.82],        # tombol Next saat scouting
        "end_battle": [0.055, 0.115],       # "End Battle" saat perang
        "surrender_ok": [0.60, 0.60],       # konfirmasi "Okay" end battle
        "return_home": [0.50, 0.85],        # "Return Home" di layar hasil
    },

    # Jeda antar attack (detik) — kasih napas buat train troops / anti rate-limit
    "rest_between_attacks": 20,

    # Epsilon-greedy untuk learning: peluang coba strategi non-terbaik
    "epsilon": 0.25,
}


def load():
    cfg = dict(DEFAULTS)
    cfg["ui"] = dict(DEFAULTS["ui"])
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if k == "ui" and isinstance(v, dict):
                    cfg["ui"].update(v)
                else:
                    cfg[k] = v
        except Exception as e:  # noqa: BLE001
            print(f"[cocbot] config rusak ({e}), pakai default")
    return cfg
