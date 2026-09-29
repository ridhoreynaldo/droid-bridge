"""Vision v1: template matching (butuh opencv) + fallback koordinat.

Tanpa opencv, bot jalan dalam "mode koordinat": semua aksi pakai posisi
fraksi dari cocbot_config.json. Dengan opencv + template di folder templates/,
bot bisa menemukan tombol/ikon di layar secara presisi.

Template dibuat dari web UI: buka layar yang diinginkan di HP, klik
"📸 jadikan template", beri nama (mis. attack_button).
"""
import os

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")


def template_path(name):
    return os.path.join(TEMPLATE_DIR, f"{name}.png")


def list_templates():
    if not os.path.isdir(TEMPLATE_DIR):
        return []
    return sorted(f[:-4] for f in os.listdir(TEMPLATE_DIR) if f.endswith(".png"))


def save_template(name, png_bytes):
    """Simpan screenshot sebagai template. Nama dibersihkan dari path traversal."""
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_"))[:40]
    if not safe:
        raise ValueError("nama template tidak valid")
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    p = template_path(safe)
    with open(p, "wb") as f:
        f.write(png_bytes)
    return safe


def _decode(png_bytes):
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def find(png_bytes, name, threshold=0.8):
    """Cari template di screenshot. -> (x, y, score) piksel atau None."""
    if not HAS_CV2:
        return None
    tp = template_path(name)
    if not os.path.isfile(tp):
        return None
    screen = _decode(png_bytes)
    templ = cv2.imread(tp)
    if screen is None or templ is None:
        return None
    res = cv2.matchTemplate(screen, templ, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < threshold:
        return None
    h, w = templ.shape[:2]
    return (loc[0] + w // 2, loc[1] + h // 2, float(score))


def count_matches(png_bytes, name, threshold=0.75):
    """Hitung kemunculan template (mis. ikon bintang di layar hasil)."""
    if not HAS_CV2:
        return 0
    tp = template_path(name)
    if not os.path.isfile(tp):
        return 0
    screen = _decode(png_bytes)
    templ = cv2.imread(tp)
    if screen is None or templ is None:
        return 0
    res = cv2.matchTemplate(screen, templ, cv2.TM_CCOEFF_NORMED)
    ys, xs = (res >= threshold).nonzero()
    # non-maximum suppression kasar: kelompokkan titik berdekatan
    pts = sorted(zip(xs.tolist(), ys.tolist()))
    kept = []
    for x, y in pts:
        if all(abs(x - kx) > 20 or abs(y - ky) > 20 for kx, ky in kept):
            kept.append((x, y))
    return len(kept)


def decode_size(png_bytes):
    """Ukuran screenshot tanpa opencv (baca header PNG). -> (w, h) atau None."""
    try:
        import struct
        if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        w, h = struct.unpack(">II", png_bytes[16:24])
        return w, h
    except Exception:  # noqa: BLE001
        return None
