#!/usr/bin/env python3
"""
droid-bridge — remote kontrol HP Android lewat browser, via ADB.
Termasuk cocbot: auto-attack engine CoC (mode farming / push rank + learning).

Jalankan:  python3 bridge.py   (atau ./start.sh / start.bat)
Buka:      http://localhost:3000

Inti bridge: murni Python stdlib, tanpa pip install.
cocbot butuh opencv untuk template matching (opsional):
  pip install -r requirements-bot.txt
Tanpa opencv, bot jalan dalam "mode koordinat".
"""
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import libadb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_dotenv():
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

# bot engine: dibuat malas (lazy) agar import cocbot tidak wajib di startup
_bot = None


def get_bot():
    global _bot
    if _bot is None:
        from cocbot import engine as engine_mod
        _bot = engine_mod.BotEngine(ADB_BIN, ANDROID_SERIAL)
    return _bot


class Handler(BaseHTTPRequestHandler):
    server_version = "droid-bridge/0.2"

    # -- helpers ----------------------------------------------------
    def log_message(self, fmt, *args):
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
                ok, out, _, err = libadb.adb_run(ADB_BIN, ["version"], timeout=5)
                self.send_json(200, {
                    "ok": True, "service": "droid-bridge", "adb": ok,
                    "adbVersion": out.decode("utf-8", "replace").splitlines()[0].strip() if ok else None,
                    **({} if ok else {"error": err}),
                })
            elif path == "/api/devices":
                devices, err = libadb.list_devices(ADB_BIN)
                if devices is None:
                    self.fail(err, 502)
                else:
                    self.ok(devices=devices)
            elif path == "/api/screen-size":
                serial = self.eff_serial()
                try:
                    w, h = libadb.screen_size(ADB_BIN, ANDROID_SERIAL, serial)
                    self.ok(width=w, height=h, model=libadb.device_model(ADB_BIN, ANDROID_SERIAL, serial))
                except Exception as e:  # noqa: BLE001
                    self.fail(str(e), 502)
            elif path == "/api/screenshot":
                ok, data, err = libadb.screencap(ADB_BIN, ANDROID_SERIAL, self.eff_serial(), timeout=12)
                if not ok:
                    self.fail(err, 502)
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            elif path == "/api/bot/status":
                self.ok(**get_bot().status())
            elif path == "/api/bot/log":
                try:
                    limit = int(self.q("limit", "80"))
                except ValueError:
                    limit = 80
                self.ok(lines=get_bot().get_log(limit))
            elif path == "/api/bot/stats":
                self.ok(stats=get_bot().learner.stats(), has_cv2=self._has_cv2())
            elif path == "/api/bot/templates":
                from cocbot import vision
                self.ok(templates=vision.list_templates(), has_cv2=vision.HAS_CV2)
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
                ok, out, _, err = libadb.adb_run(ADB_BIN, ["connect", host], timeout=10)
                msg = out.decode("utf-8", "replace").strip()
                if not ok:
                    return self.fail(err or msg or "adb connect gagal", 502)
                self.ok(message=msg)
            elif path == "/api/tap":
                x, y = body.get("x"), body.get("y")
                if not isinstance(x, int) or not isinstance(y, int) or x < 0 or y < 0:
                    return self.fail("x dan y harus integer >= 0 (koordinat pixel layar device)", 400)
                ok, err = libadb.tap(ADB_BIN, ANDROID_SERIAL, self.eff_serial(body), x, y)
                if not ok:
                    return self.fail(err, 502)
                self.ok(x=x, y=y)
            elif path == "/api/swipe":
                vals = [body.get(k) for k in ("x1", "y1", "x2", "y2")]
                for n, v in zip(("x1", "y1", "x2", "y2"), vals):
                    if not isinstance(v, int) or v < 0:
                        return self.fail(f"{n} harus integer >= 0", 400)
                dur = body.get("durationMs")
                dur = dur if isinstance(dur, int) and dur > 0 else 300
                ok, err = libadb.swipe(ADB_BIN, ANDROID_SERIAL, self.eff_serial(body),
                                       vals[0], vals[1], vals[2], vals[3], dur)
                if not ok:
                    return self.fail(err, 502)
                self.ok(x1=vals[0], y1=vals[1], x2=vals[2], y2=vals[3], durationMs=dur)
            elif path == "/api/key":
                code = str(body.get("code", "")).strip()
                if not code:
                    return self.fail("code wajib diisi (angka atau nama KEYCODE_*)", 400)
                ok, err = libadb.key(ADB_BIN, ANDROID_SERIAL, self.eff_serial(body), code)
                if not ok:
                    return self.fail(err, 502)
                self.ok(code=code)
            elif path == "/api/text":
                text = body.get("text", "")
                if not isinstance(text, str) or not text:
                    return self.fail("text wajib diisi", 400)
                if len(text) > 500:
                    return self.fail("text maksimal 500 karakter", 400)
                ok, err = libadb.text(ADB_BIN, ANDROID_SERIAL, self.eff_serial(body), text)
                if not ok:
                    return self.fail(err, 502)
                self.ok(length=len(text))
            elif path == "/api/unlock":
                serial = self.eff_serial(body)
                ok, err = libadb.key(ADB_BIN, ANDROID_SERIAL, serial, "224")
                if not ok:
                    return self.fail(err, 502)
                import time as _t
                _t.sleep(0.5)
                try:
                    w, h = libadb.screen_size(ADB_BIN, ANDROID_SERIAL, serial)
                    x = w // 2
                    libadb.swipe(ADB_BIN, ANDROID_SERIAL, serial, x, int(h * 0.8), x, int(h * 0.3), 400)
                except Exception:  # noqa: BLE001
                    pass
                self.ok()
            # -- cocbot ---------------------------------------------
            elif path == "/api/bot/start":
                mode = str(body.get("mode", "")).strip()
                ok, err = get_bot().start(mode)
                if not ok:
                    return self.fail(err, 409)
                self.ok(mode=mode)
            elif path == "/api/bot/stop":
                get_bot().stop()
                self.ok()
            elif path == "/api/bot/open-coc":
                from cocbot import config as cfg_mod
                cfg = cfg_mod.load()
                serial = self.eff_serial(body)
                icon = cfg.get("coc_icon")
                if icon:
                    try:
                        w, h = libadb.screen_size(ADB_BIN, ANDROID_SERIAL, serial)
                        ok, err = libadb.tap(ADB_BIN, ANDROID_SERIAL, serial, int(icon[0] * w), int(icon[1] * h))
                    except Exception as e:  # noqa: BLE001
                        ok, err = False, str(e)
                else:
                    ok, err = libadb.start_app(ADB_BIN, ANDROID_SERIAL, serial, cfg["coc_package"])
                if not ok:
                    return self.fail(err or "gagal membuka CoC", 502)
                self.ok()
            elif path == "/api/bot/capture":
                from cocbot import vision
                name = str(body.get("name", "")).strip()
                if not name:
                    return self.fail("name wajib diisi", 400)
                ok, png, err = libadb.screencap(ADB_BIN, ANDROID_SERIAL, self.eff_serial(body), timeout=12)
                if not ok:
                    return self.fail(err, 502)
                try:
                    saved = vision.save_template(name, png)
                except ValueError as e:
                    return self.fail(str(e), 400)
                self.ok(template=saved)
            else:
                self.fail("not found", 404)
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001
            self.fail(str(e), 502)

    def _has_cv2(self):
        try:
            from cocbot import vision
            return vision.HAS_CV2
        except Exception:  # noqa: BLE001
            return False

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
    try:
        from cocbot import vision as _v
        print("  cocbot: template matching %s" % ("AKTIF (opencv)" if _v.HAS_CV2 else "nonaktif (mode koordinat)"))
    except Exception:  # noqa: BLE001
        pass
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
