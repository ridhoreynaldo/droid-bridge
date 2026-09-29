#!/usr/bin/env python3
"""
droid-bridge — remote kontrol HP Android lewat browser, via ADB.

Jalankan:  python3 bridge.py   (atau ./start.sh / start.bat)
Buka:      http://localhost:3000

Tidak butuh pip install apa pun — murni Python stdlib.
Konfigurasi via environment variable atau file .env di folder ini:
  PORT           (default 3000)
  BRIDGE_TOKEN   (wajib diisi kalau di-expose ke internet!)
  ADB_PATH       (default "adb", harus di PATH)
  ANDROID_SERIAL (opsional, kalau HP lebih dari satu)
"""

import json
import os
import re
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_dotenv():
    """Baca .env sederhana (KEY=VALUE), tidak menimpa env yang sudah ada."""
    path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


load_dotenv()

PORT = int(os.environ.get("PORT", "3000"))
BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
ADB_BIN = os.environ.get("ADB_PATH", "adb")
ANDROID_SERIAL = os.environ.get("ANDROID_SERIAL", "")


# ---------------------------------------------------------------- ADB
def adb_run(args, timeout=15):
    """-> (ok, stdout_bytes, stderr_text, error_text)"""
    try:
        p = subprocess.run([ADB_BIN] + args, capture_output=True, timeout=timeout)
        if p.returncode != 0:
            err = p.stderr.decode("utf-8", "replace").strip() or f"adb exit {p.returncode}"
            return False, p.stdout, p.stderr.decode("utf-8", "replace"), err
        return True, p.stdout, p.stderr.decode("utf-8", "replace"), ""
    except FileNotFoundError:
        return False, b"", "", (
            f"adb tidak ditemukan ('{ADB_BIN}'). Install Android platform-tools "
            "dan pastikan ada di PATH, atau isi ADB_PATH di .env"
        )
    except subprocess.TimeoutExpired:
        return False, b"", "", "adb timeout"
    except Exception as e:  # noqa: BLE001
        return False, b"", "", str(e)


def target_args(serial):
    s = (serial or ANDROID_SERIAL or "").strip()
    return ["-s", s] if s else []


def list_devices():
    ok, out, _, err = adb_run(["devices"], timeout=8)
    if not ok:
        return None, err
    devices = []
    for line in out.decode("utf-8", "replace").splitlines()[1:]:
        m = re.match(r"^(\S+)\s+(\S+)", line.strip())
        if m:
            devices.append({"serial": m.group(1), "status": m.group(2)})
    return devices, ""


def screen_size(serial):
    ok, out, _, err = adb_run(target_args(serial) + ["shell", "wm", "size"], timeout=8)
    m = re.search(r"(\d+)\s*x\s*(\d+)", out.decode("utf-8", "replace"))
    if not m:
        raise RuntimeError("gagal baca ukuran layar: " + (err or "unknown"))
    return int(m.group(1)), int(m.group(2))


def device_model(serial):
    ok, out, _, _ = adb_run(target_args(serial) + ["shell", "getprop", "ro.product.model"], timeout=8)
    return out.decode("utf-8", "replace").strip()


def escape_for_adb_shell(s):
    return re.sub(r"([\"'\\$`&|;<>()!#*?~^])", r"\\\1", s.replace("%", "%25").replace(" ", "%s"))


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "droid-bridge/0.1"

    # -- helpers ----------------------------------------------------
    def log_message(self, fmt, *args):  # lebih ringkas dari default
        print(f"[{self.command}] {self.path.split('?')[0]}")

    def query(self):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    def q(self, name, default=""):
        return self.query().get(name, [default])[0]

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def eff_serial(self, body=None):
        return self.q("serial") or (body or {}).get("serial") or None

    def authorized(self):
        if not BRIDGE_TOKEN:
            return True
        if urllib.parse.urlparse(self.path).path == "/api/health":
            return True
        if self.headers.get("Authorization", "") == f"Bearer {BRIDGE_TOKEN}":
            return True
        if self.q("token") == BRIDGE_TOKEN:
            return True
        return False

    def send_json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def ok(self, **kw):
        self.send_json(200, {"ok": True, **kw})

    def fail(self, error, code=500):
        self.send_json(code, {"ok": False, "error": error})

    # -- routing ----------------------------------------------------
    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            return self.serve_index()
        if not path.startswith("/api/"):
            return self.fail("not found", 404)
        if not self.authorized():
            return self.fail("unauthorized", 401)
        try:
            if path == "/api/health":
                ok, out, _, err = adb_run(["version"], timeout=5)
                self.send_json(200, {
                    "ok": True, "service": "droid-bridge", "adb": ok,
                    "adbVersion": out.decode("utf-8", "replace").splitlines()[0].strip() if ok else None,
                    **({} if ok else {"error": err}),
                })
            elif path == "/api/devices":
                devices, err = list_devices()
                if devices is None:
                    self.fail(err, 502)
                else:
                    self.ok(devices=devices)
            elif path == "/api/screen-size":
                serial = self.eff_serial()
                w, h = screen_size(serial)
                self.ok(width=w, height=h, model=device_model(serial))
            elif path == "/api/screenshot":
                serial = self.eff_serial()
                ok, data, _, err = adb_run(target_args(serial) + ["exec-out", "screencap", "-p"], timeout=12)
                if not ok or not data:
                    self.fail(err or "screencap gagal (device belum connect?)", 502)
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            else:
                self.fail("not found", 404)
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001
            self.fail(str(e), 502)

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            return self.fail("not found", 404)
        if not self.authorized():
            return self.fail("unauthorized", 401)
        body = self.read_json()
        try:
            if path == "/api/connect":
                host = str(body.get("host", "")).strip()
                if not host:
                    return self.fail("host wajib diisi, mis. 192.168.1.20:5555", 400)
                ok, out, _, err = adb_run(["connect", host], timeout=10)
                msg = (out.decode("utf-8", "replace")).strip()
                if not ok:
                    return self.fail(err or msg or "adb connect gagal", 502)
                self.ok(message=msg)
            elif path == "/api/tap":
                x, y = body.get("x"), body.get("y")
                if not isinstance(x, int) or not isinstance(y, int) or x < 0 or y < 0:
                    return self.fail("x dan y harus integer >= 0 (koordinat pixel layar device)", 400)
                ok, _, _, err = adb_run(
                    target_args(self.eff_serial(body)) + ["shell", "input", "tap", str(x), str(y)], timeout=8)
                if not ok:
                    return self.fail(err, 502)
                self.ok(x=x, y=y)
            elif path == "/api/swipe":
                vals = [body.get(k) for k in ("x1", "y1", "x2", "y2")]
                names = ("x1", "y1", "x2", "y2")
                for n, v in zip(names, vals):
                    if not isinstance(v, int) or v < 0:
                        return self.fail(f"{n} harus integer >= 0", 400)
                dur = body.get("durationMs")
                dur = dur if isinstance(dur, int) and dur > 0 else 300
                ok, _, _, err = adb_run(
                    target_args(self.eff_serial(body)) + ["shell", "input", "swipe",
                        str(vals[0]), str(vals[1]), str(vals[2]), str(vals[3]), str(dur)], timeout=10)
                if not ok:
                    return self.fail(err, 502)
                self.ok(x1=vals[0], y1=vals[1], x2=vals[2], y2=vals[3], durationMs=dur)
            elif path == "/api/key":
                code = str(body.get("code", "")).strip()
                if not code:
                    return self.fail("code wajib diisi (angka atau nama KEYCODE_*)", 400)
                ok, _, _, err = adb_run(
                    target_args(self.eff_serial(body)) + ["shell", "input", "keyevent", code], timeout=8)
                if not ok:
                    return self.fail(err, 502)
                self.ok(code=code)
            elif path == "/api/text":
                text = body.get("text", "")
                if not isinstance(text, str) or not text:
                    return self.fail("text wajib diisi", 400)
                if len(text) > 500:
                    return self.fail("text maksimal 500 karakter", 400)
                ok, _, _, err = adb_run(
                    target_args(self.eff_serial(body)) + ["shell", "input", "text", escape_for_adb_shell(text)],
                    timeout=10)
                if not ok:
                    return self.fail(err, 502)
                self.ok(length=len(text))
            elif path == "/api/unlock":
                serial = self.eff_serial(body)
                ok, _, _, err = adb_run(target_args(serial) + ["shell", "input", "keyevent", "224"], timeout=8)
                if not ok:
                    return self.fail(err, 502)
                time.sleep(0.5)
                try:
                    w, h = screen_size(serial)
                    x = w // 2
                    adb_run(target_args(serial) + ["shell", "input", "swipe",
                            str(x), str(int(h * 0.8)), str(x), str(int(h * 0.3)), "400"], timeout=10)
                except Exception:  # noqa: BLE001
                    pass  # layar mungkin sudah terbuka / terkunci PIN — abaikan
                self.ok()
            else:
                self.fail("not found", 404)
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001
            self.fail(str(e), 502)

    def serve_index(self):
        p = os.path.join(BASE_DIR, "static", "index.html")
        try:
            with open(p, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            return self.fail("index.html tidak ditemukan", 500)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print("=" * 56)
    print("  📱 droid-bridge jalan di  http://localhost:%d" % PORT)
    print("  adb: %s" % ADB_BIN)
    if BRIDGE_TOKEN:
        print("  🔒 BRIDGE_TOKEN aktif")
    else:
        print("  ⚠️  BRIDGE_TOKEN kosong — JANGAN expose ke internet!")
    print("  Ctrl+C untuk berhenti")
    print("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nberhenti.")


if __name__ == "__main__":
    main()
