"""Definisi strategi serangan per mode. Format data — gampang ditambah/dioprek.

Satu strategi = daftar step:
  {"slot": <index slot troops>, "points": [[fx, fy], ...], "gap": <detik antar tap>}

Semua koordinat dalam fraksi 0-1 dari lebar/tinggi layar.
"slot": -1 artinya tanpa pilih troops dulu (mis. untuk spell kalau didukung).
"""
from . import config as config_mod

STRATEGIES = {
    "farming": [
        {
            "id": "edge_goblins",
            "name": "Goblin keliling tepi",
            "desc": "Tebar goblin di sepanjang tepi kiri-kanan (sasar collector di perimeter)",
            "steps": [
                {"slot": 0, "points": [[0.06, 0.3], [0.06, 0.5], [0.06, 0.7]], "gap": 0.6},
                {"slot": 0, "points": [[0.94, 0.3], [0.94, 0.5], [0.94, 0.7]], "gap": 0.6},
                {"slot": 1, "points": [[0.06, 0.4], [0.94, 0.4], [0.06, 0.6], [0.94, 0.6]], "gap": 0.5},
            ],
        },
        {
            "id": "corner_archers",
            "name": "Archer dari sudut",
            "desc": "Archer dari 4 sudut, lalu goblin susulan",
            "steps": [
                {"slot": 1, "points": [[0.08, 0.25], [0.92, 0.25], [0.08, 0.75], [0.92, 0.75]], "gap": 0.5},
                {"slot": 1, "points": [[0.08, 0.35], [0.92, 0.35], [0.08, 0.65], [0.92, 0.65]], "gap": 0.5},
                {"slot": 0, "points": [[0.08, 0.3], [0.92, 0.3], [0.08, 0.7], [0.92, 0.7]], "gap": 0.6},
            ],
        },
        {
            "id": "line_barb",
            "name": "Barbarian garis depan",
            "desc": "Barbarian segaris di sisi bawah, archer di belakang",
            "steps": [
                {"slot": 2, "points": [[0.2, 0.85], [0.35, 0.85], [0.5, 0.85], [0.65, 0.85], [0.8, 0.85]], "gap": 0.4},
                {"slot": 1, "points": [[0.25, 0.9], [0.5, 0.9], [0.75, 0.9]], "gap": 0.5},
            ],
        },
    ],
    "push": [
        {
            "id": "funnel_left",
            "name": "Funnel kiri → tengah",
            "desc": "Buka funnel dari kiri, pasukan inti ke tengah",
            "steps": [
                {"slot": 3, "points": [[0.15, 0.6], [0.15, 0.75]], "gap": 0.8},
                {"slot": 2, "points": [[0.1, 0.55], [0.1, 0.8], [0.2, 0.5], [0.2, 0.85]], "gap": 0.4},
                {"slot": 1, "points": [[0.15, 0.62], [0.15, 0.72], [0.25, 0.55], [0.25, 0.8]], "gap": 0.4},
                {"slot": 0, "points": [[0.3, 0.6], [0.3, 0.7]], "gap": 0.6},
            ],
        },
        {
            "id": "funnel_right",
            "name": "Funnel kanan → tengah",
            "desc": "Cermin dari funnel kiri",
            "steps": [
                {"slot": 3, "points": [[0.85, 0.6], [0.85, 0.75]], "gap": 0.8},
                {"slot": 2, "points": [[0.9, 0.55], [0.9, 0.8], [0.8, 0.5], [0.8, 0.85]], "gap": 0.4},
                {"slot": 1, "points": [[0.85, 0.62], [0.85, 0.72], [0.75, 0.55], [0.75, 0.8]], "gap": 0.4},
                {"slot": 0, "points": [[0.7, 0.6], [0.7, 0.7]], "gap": 0.6},
            ],
        },
        {
            "id": "all_sides",
            "name": "Kepung semua sisi",
            "desc": "Tebar merata mengelilingi base (untuk base menyebar)",
            "steps": [
                {"slot": 2, "points": [[0.5, 0.15], [0.5, 0.85], [0.08, 0.5], [0.92, 0.5]], "gap": 0.4},
                {"slot": 1, "points": [[0.3, 0.2], [0.7, 0.2], [0.3, 0.8], [0.7, 0.8]], "gap": 0.4},
                {"slot": 0, "points": [[0.5, 0.25], [0.5, 0.75]], "gap": 0.6},
            ],
        },
    ],
}


def for_mode(mode):
    return STRATEGIES.get(mode, [])


def get(mode, strategy_id):
    for s in for_mode(mode):
        if s["id"] == strategy_id:
            return s
    return None


def deploy_points(strategy, screen_w, screen_h):
    """Flatten strategi jadi urutan aksi tap absolut: [(slot, x, y, gap)]."""
    actions = []
    for step in strategy["steps"]:
        for fx, fy in step["points"]:
            actions.append((step["slot"], int(fx * screen_w), int(fy * screen_h), step.get("gap", 0.5)))
    return actions


def slot_xy(cfg, index, screen_w, screen_h):
    slots = cfg["slots"]
    if index < 0 or index >= len(slots):
        return None
    s = slots[index]
    return int(s["x"] * screen_w), int(s["y"] * screen_h)
