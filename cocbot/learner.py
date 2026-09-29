"""Learning loop: catat tiap serangan, pilih strategi pakai epsilon-greedy.

Reward per serangan:
  push    -> stars (0-3). Tanpa data stars -> 1.0 (dianggap percobaan).
  farming -> stars juga (proxy; loot OCR menyusul) + bonus kecepatan.

Bobot disimpan di cocbot_state.json sehingga "belajar terus" antar sesi.
"""
import json
import os
import random
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "cocbot_state.json")
LOG_PATH = os.path.join(BASE_DIR, "cocbot_log.jsonl")


class Learner:
    def __init__(self, epsilon=0.25):
        self.epsilon = epsilon
        self.weights = {}   # (mode, strategy_id) -> {"n": int, "reward_sum": float}
        self.load()

    # -- persistensi -----------------------------------------------
    def load(self):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                self.weights = json.load(f).get("weights", {})
        except Exception:  # noqa: BLE001
            self.weights = {}

    def save(self):
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"weights": self.weights, "saved_at": time.time()}, f)
        os.replace(tmp, STATE_PATH)

    # -- inti --------------------------------------------------------
    def _key(self, mode, strategy_id):
        return f"{mode}:{strategy_id}"

    def avg(self, mode, strategy_id):
        w = self.weights.get(self._key(mode, strategy_id))
        if not w or not w["n"]:
            return 0.0
        return w["reward_sum"] / w["n"]

    def choose(self, mode, strategies):
        """Epsilon-greedy: kadang eksplorasi, biasanya eksploitasi."""
        if not strategies:
            return None
        if random.random() < self.epsilon or all(self.avg(mode, s["id"]) == 0 for s in strategies):
            return random.choice(strategies)
        return max(strategies, key=lambda s: self.avg(mode, s["id"]))

    def record(self, mode, strategy_id, stars=None, duration_s=0.0, notes=""):
        reward = float(stars) if stars is not None else 1.0
        k = self._key(mode, strategy_id)
        w = self.weights.setdefault(k, {"n": 0, "reward_sum": 0.0})
        w["n"] += 1
        w["reward_sum"] += reward
        entry = {
            "ts": time.time(), "mode": mode, "strategy": strategy_id,
            "stars": stars, "duration_s": round(duration_s, 1),
            "reward": reward, "notes": notes,
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.save()
        return entry

    def stats(self, mode=None):
        out = []
        for k, w in self.weights.items():
            m, sid = k.split(":", 1)
            if mode and m != mode:
                continue
            out.append({
                "mode": m, "strategy": sid, "attacks": w["n"],
                "avg_reward": round(w["reward_sum"] / w["n"], 2) if w["n"] else 0.0,
            })
        out.sort(key=lambda x: -x["avg_reward"])
        return out

    def recent(self, limit=50):
        if not os.path.isfile(LOG_PATH):
            return []
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = f.readlines()
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except Exception:  # noqa: BLE001
                pass
        return out
