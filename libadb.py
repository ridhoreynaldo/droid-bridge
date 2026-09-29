"""Lapisan ADB untuk droid-bridge & cocbot. Stdlib only."""
import re
import subprocess


def adb_run(adb_bin, args, timeout=15):
    """-> (ok, stdout_bytes, stderr_text, error_text)"""
    try:
        p = subprocess.run([adb_bin] + args, capture_output=True, timeout=timeout)
        if p.returncode != 0:
            err = p.stderr.decode("utf-8", "replace").strip() or f"adb exit {p.returncode}"
            return False, p.stdout, p.stderr.decode("utf-8", "replace"), err
        return True, p.stdout, p.stderr.decode("utf-8", "replace"), ""
    except FileNotFoundError:
        return False, b"", "", (
            f"adb tidak ditemukan ('{adb_bin}'). Install Android platform-tools "
            "dan pastikan ada di PATH, atau isi ADB_PATH di .env"
        )
    except subprocess.TimeoutExpired:
        return False, b"", "", "adb timeout"
    except Exception as e:  # noqa: BLE001
        return False, b"", "", str(e)


def target_args(android_serial, serial):
    s = (serial or android_serial or "").strip()
    return ["-s", s] if s else []


def list_devices(adb_bin):
    ok, out, _, err = adb_run(adb_bin, ["devices"], timeout=8)
    if not ok:
        return None, err
    devices = []
    for line in out.decode("utf-8", "replace").splitlines()[1:]:
        m = re.match(r"^(\S+)\s+(\S+)", line.strip())
        if m:
            devices.append({"serial": m.group(1), "status": m.group(2)})
    return devices, ""


def screen_size(adb_bin, android_serial, serial):
    ok, out, _, err = adb_run(adb_bin, target_args(android_serial, serial) + ["shell", "wm", "size"], timeout=8)
    m = re.search(r"(\d+)\s*x\s*(\d+)", out.decode("utf-8", "replace"))
    if not m:
        raise RuntimeError("gagal baca ukuran layar: " + (err or "unknown"))
    return int(m.group(1)), int(m.group(2))


def device_model(adb_bin, android_serial, serial):
    ok, out, _, _ = adb_run(adb_bin, target_args(android_serial, serial) + ["shell", "getprop", "ro.product.model"], timeout=8)
    return out.decode("utf-8", "replace").strip()


def screencap(adb_bin, android_serial, serial, timeout=12):
    """-> (ok, png_bytes, error)"""
    ok, data, _, err = adb_run(adb_bin, target_args(android_serial, serial) + ["exec-out", "screencap", "-p"], timeout=timeout)
    if not ok or not data:
        return False, b"", err or "screencap gagal (device belum connect?)"
    return True, data, ""


def tap(adb_bin, android_serial, serial, x, y):
    ok, _, _, err = adb_run(adb_bin, target_args(android_serial, serial) + ["shell", "input", "tap", str(x), str(y)], timeout=8)
    return ok, err


def swipe(adb_bin, android_serial, serial, x1, y1, x2, y2, duration_ms=300):
    ok, _, _, err = adb_run(
        adb_bin, target_args(android_serial, serial) +
        ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)], timeout=10)
    return ok, err


def key(adb_bin, android_serial, serial, code):
    ok, _, _, err = adb_run(adb_bin, target_args(android_serial, serial) + ["shell", "input", "keyevent", str(code)], timeout=8)
    return ok, err


def escape_for_adb_shell(s):
    return re.sub(r"([\"'\\$`&|;<>()!#*?~^])", r"\\\1", s.replace("%", "%25").replace(" ", "%s"))


def text(adb_bin, android_serial, serial, s):
    ok, _, _, err = adb_run(
        adb_bin, target_args(android_serial, serial) + ["shell", "input", "text", escape_for_adb_shell(s)], timeout=10)
    return ok, err


def app_running(adb_bin, android_serial, serial, package):
    """Cek apakah package sedang berjalan (pidof). -> bool"""
    ok, out, _, _ = adb_run(adb_bin, target_args(android_serial, serial) + ["shell", "pidof", package], timeout=8)
    return ok and bool(out.decode("utf-8", "replace").strip())


def start_app(adb_bin, android_serial, serial, package):
    """Buka app via monkey (tanpa perlu tahu activity)."""
    ok, _, _, err = adb_run(
        adb_bin, target_args(android_serial, serial) +
        ["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"], timeout=10)
    return ok, err
