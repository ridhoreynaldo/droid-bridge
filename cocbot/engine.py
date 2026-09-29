"""Bot engine: state machine real-time yang jalan sebagai thread di bridge.py.

Loop: screenshot -> kenali kondisi -> aksi -> ulangi, secepat ADB memungkinkan.
Learning (learner.py) memilih strategi tiap serangan via epsilon-greedy.
"""
import threading
import time
from collections import deque

from . import config as config_mod
from . import learner as learner_mod
from . import strategies as strat_mod
from . import vision

import libadb

LOG_MAX = 200


class BotEngine:
    def __init__(self, adb_bin, android_serial):
        self.adb_bin = adb_bin
        self.android_serial = android_serial
        self.cfg = config_mod.load()
        self.learner = learner_mod.Learner(epsilon=self.cfg.get("epsilon", 0.25))
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.RLock()  # RLock: start()->log() akuisisi ulang aman
        self.running = False
        self.mode = None
        self.state = "idle"
        self.strategy_name = "-"
        self.attacks_done = 0
        self.last = None
        self.started_at = None
        self.logbuf = deque(maxlen=LOG_MAX)

    # -- API ---------------------------------------------------------
    def start(self, mode):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False, "bot sudah jalan"
            if mode not in ("farming", "push"):
                return False, "mode harus 'farming' atau 'push'"
            self.cfg = config_mod.load()
            self.learner = learner_mod.Learner(epsilon=self.cfg.get("epsilon", 0.25))
            self._stop.clear()
            self.running = True
            self.mode = mode
            self.state = "menyiapkan"
            self.attacks_done = 0
            self.started_at = time.time()
            self._thread = threading.Thread(target=self._run, daemon=True, name="cocbot")
            self._thread.start()
            self.log(f"bot mulai — mode {mode}")
            return True, ""

    def stop(self):
        self._stop.set()
        self.log("bot dihentikan")
        with self._lock:
            self.running = False
            self.state = "idle"

    def status(self):
        with self._lock:
            return {
                "running": self.running and self._thread is not None and self._thread.is_alive(),
                "mode": self.mode,
                "state": self.state,
                "strategy": self.strategy_name,
                "attacks_done": self.attacks_done,
                "last": self.last,
                "has_cv2": vision.HAS_CV2,
                "uptime_s": round(time.time() - self.started_at, 1) if self.started_at else 0,
            }

    def get_log(self, limit=80):
        with self._lock:
            return list(self.logbuf)[-limit:]

    # -- util ----------------------------------------------------------
    def log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        with self._lock:
            self.logbuf.append(line)
        print(f"[cocbot] {msg}")

    def _set_state(self, s):
        with self._lock:
            self.state = s
        self.log(f"→ {s}")

    def _sleep(self, sec):
        end = time.time() + sec
        while time.time() < end:
            if self._stop.is_set():
                return False
            time.sleep(min(0.2, end - time.time()))
        return not self._stop.is_set()

    def _shot(self):
        ok, png, err = libadb.screencap(self.adb_bin, self.android_serial, None, timeout=10)
        if not ok:
            self.log(f"screenshot gagal: {err}")
        return png if ok else b""

    def _size(self, png):
        wh = vision.decode_size(png)
        if wh:
            return wh
        try:
            return libadb.screen_size(self.adb_bin, self.android_serial, None)
        except Exception:  # noqa: BLE001
            return (1080, 2400)

    def _tap(self, x, y):
        ok, err = libadb.tap(self.adb_bin, self.android_serial, None, x, y)
        if not ok:
            self.log(f"tap gagal: {err}")
        return ok

    def _tap_frac(self, fx, fy, w, h):
        return self._tap(int(fx * w), int(fy * h))

    def _tap_ui(self, key, png, w, h):
        """Tap tombol UI: pakai template kalau ada, else koordinat config."""
        if vision.HAS_CV2 and key in vision.list_templates():
            found = vision.find(png, key)
            if found:
                x, y, score = found
                self.log(f"template '{key}' ketemu (score {score:.2f})")
                return self._tap(x, y)
        fx, fy = self.cfg["ui"][key]
        return self._tap_frac(fx, fy, w, h)

    def _seen(self, png, name, threshold=0.8):
        found = vision.find(png, name, threshold)
        return found is not None

    # -- alur serangan ---------------------------------------------------
    def _run(self):
        try:
            while not self._stop.is_set():
                strats = strat_mod.for_mode(self.mode)
                strategy = self.learner.choose(self.mode, strats)
                if not strategy:
                    self.log("tidak ada strategi untuk mode ini")
                    break
                with self._lock:
                    self.strategy_name = strategy["name"]
                self.log(f"strategi dipilih: {strategy['name']}")
                t0 = time.time()
                stars, completed = self._attack_cycle(strategy)
                if not completed:
                    self.log("siklus terinterupsi — tidak dicatat ke learner")
                    break
                dur = time.time() - t0
                entry = self.learner.record(self.mode, strategy["id"], stars=stars, duration_s=dur)
                with self._lock:
                    self.attacks_done += 1
                    self.last = entry
                self.log(f"selesai: {stars if stars is not None else '?'}★ dalam {dur:.0f}s")
                rest = self.cfg.get("rest_between_attacks", 20)
                self._set_state(f"istirahat {rest}s")
                if not self._sleep(rest):
                    break
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")
        finally:
            with self._lock:
                self.running = False
                self.state = "idle"
            self.log("loop berhenti")

    def _attack_cycle(self, strategy):
        pkg = self.cfg["coc_package"]

        # 1. pastikan CoC terbuka
        self._set_state("membuka CoC")
        if not libadb.app_running(self.adb_bin, self.android_serial, None, pkg):
            icon = self.cfg.get("coc_icon")
            png = self._shot()
            w, h = self._size(png)
            if icon:
                self._tap_frac(icon[0], icon[1], w, h)
            else:
                ok, err = libadb.start_app(self.adb_bin, self.android_serial, None, pkg)
                self.log("membuka CoC via monkey" if ok else f"gagal buka CoC: {err}")
        if not self._sleep(8):
            return (None, False)

        # 2. tap tombol Attack di home
        self._set_state("mencari lawan")
        png = self._shot()
        w, h = self._size(png)
        self._tap_ui("attack_button", png, w, h)
        if not self._sleep(2.5):
            return (None, False)

        # 3. Find a match
        png = self._shot()
        self._tap_ui("find_match", png, w, h)
        if not self._sleep(4):
            return (None, False)

        # 4. farming: Next beberapa kali (seleksi kasar, OCR menyusul)
        if self.mode == "farming":
            n = int(self.cfg.get("farming_next_count", 0) or 0)
            for i in range(n):
                if self._stop.is_set():
                    return (None, False)
                png = self._shot()
                self._tap_ui("next_button", png, w, h)
                self.log(f"next {i + 1}/{n}")
                if not self._sleep(2):
                    return (None, False)

        # 5. tunggu battle prep (troop bar)
        self._set_state("menyiapkan pasukan")
        prepped = False
        t_end = time.time() + 20
        while time.time() < t_end and not self._stop.is_set():
            png = self._shot()
            if "troop_bar" in vision.list_templates() and self._seen(png, "troop_bar"):
                prepped = True
                break
            time.sleep(1)
        if not prepped:
            self.log("troop bar tidak terdeteksi, lanjut pakai koordinat")
            if not self._sleep(3):
                return (None, False)
        png = self._shot() or png
        w, h = self._size(png)

        # 6. deploy!
        self._set_state("menyerang!")
        actions = strat_mod.deploy_points(strategy, w, h)
        last_slot = None
        for slot, x, y, gap in actions:
            if self._stop.is_set():
                return (None, False)
            if slot != last_slot:
                sxy = strat_mod.slot_xy(self.cfg, slot, w, h)
                if sxy:
                    self._tap(*sxy)
                    last_slot = slot
                    if not self._sleep(0.4):
                        return (None, False)
            self._tap(x, y)
            if not self._sleep(gap):
                return (None, False)

        # 7. pantau pertempuran sampai selesai
        self._set_state("memantau pertempuran")
        poll = float(self.cfg.get("poll_battle", 0.5) or 0.5)
        t_end = time.time() + float(self.cfg.get("timeout_battle", 200) or 200)
        result_seen = "battle_result" in vision.list_templates()
        while time.time() < t_end and not self._stop.is_set():
            png = self._shot()
            if result_seen and png and self._seen(png, "battle_result"):
                break
            time.sleep(poll)
        if self._stop.is_set():
            return (None, False)
        if time.time() >= t_end:
            # timeout: akhiri manual
            self.log("timeout, mengakhiri battle manual")
            png = self._shot()
            self._tap_ui("end_battle", png, w, h)
            if not self._sleep(1.5):
                return (None, False)
            png = self._shot()
            self._tap_ui("surrender_ok", png, w, h)
            if not self._sleep(3):
                return (None, False)

        # 8. baca hasil & kembali
        self._set_state("membaca hasil")
        stars = None
        png = self._shot()
        if png and "star" in vision.list_templates():
            stars = vision.count_matches(png, "star")
            self.log(f"bintang terdeteksi: {stars}")
        elif png:
            self.log("template 'star' belum ada — capture dari UI untuk baca bintang")
        if png:
            self._tap_ui("return_home", png, w, h)
        self._sleep(4)
        return (stars, True)
