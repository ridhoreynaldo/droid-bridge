# 📱 Droid Bridge

Remote kontrol HP Android lewat browser — ala Vysor, tapi web based dan punya REST API.
Screenshot layar HP + kirim tap/swipe/tombol, semua via **ADB**. Satu file Python,
**tanpa pip install** (murni stdlib). Dibuat sebagai **Phase 1** dari proyek
"AI main Clash of Clans": aplikasi ini yang jalan di **laptop** (satu jaringan/USB
dengan HP), lalu diakses dari jauh — mis. oleh agen AI — untuk melihat layar dan
menggerakkan HP.

```
┌──────────┐   USB / WiFi (ADB)   ┌──────────────┐   HTTP (localhost / tunnel)   ┌───────────┐
│ HP       │ ◄──────────────────► │ droid-bridge │ ◄───────────────────────────► │ Browser / │
│ Android  │  screencap + input   │ (laptop)     │   UI web + REST API           │ Agen AI   │
└──────────┘                      └──────────────┘                               └───────────┘
```

> ⚠️ **Wajib jalan di laptop/PC yang satu WiFi (atau kabel USB) dengan HP.**
> ADB butuh koneksi langsung ke HP — tidak bisa jalan di VPS.

## Kebutuhan

- Python 3.8+ (biasanya sudah ada di laptop)
- **Android platform-tools** (`adb`) — [download di sini](https://developer.android.com/tools/releases/platform-tools),
  lalu pastikan `adb` ada di PATH (atau isi `ADB_PATH` di `.env`)
- HP Android dengan **USB debugging** aktif (Opsi Pengembang), atau **Wireless debugging**

## Cara jalan

```bash
# 1. Colok HP via USB (atau hubungkan via wireless, lihat bawah), pastikan terdeteksi:
adb devices
#    -> muncul "xxxxxx  device". Kalau "unauthorized", setujui prompt RSA di HP.

# 2. Jalankan:
./start.sh            # Linux / Mac
# atau:  start.bat    # Windows (klik dua kali)
# atau:  python3 bridge.py

# 3. Buka http://localhost:3000 di Chrome
#    klik = tap, drag = swipe, klik kanan = back
```

### Wireless (tanpa kabel USB)

1. HP & laptop satu WiFi.
2. Di HP: **Setelan → Opsi Pengembang → Wireless debugging** → ON.
3. Tap **"Pair device with pairing code"** → di laptop: `adb pair IP:PORT` → masukkan kode.
4. Kembali ke layar Wireless debugging, lihat **IP address & Port** → di web UI droid-bridge
   masukkan `IP:PORT` → **connect wireless**. Atau via API:
   `curl -X POST localhost:3000/api/connect -H 'Content-Type: application/json' -d '{"host":"192.168.1.20:5555"}'`

## Diakses dari jauh (biar agen AI / kamu bisa pakai dari mana saja)

1. Isi `BRIDGE_TOKEN` di `.env` (bikin acak: `openssl rand -hex 16`), restart app.
2. Jalankan tunnel:
   ```bash
   cloudflared tunnel --url http://localhost:3000
   ```
3. Dapat URL publik `https://xxx.trycloudflare.com` → buka di browser / kasih ke agen AI
   beserta tokennya. Di web UI, tempel token di kolom kanan atas.
4. ⚠️ **Jangan pernah expose tanpa BRIDGE_TOKEN** — siapapun yang pegang URL+token bisa
   mengendalikan HP kamu penuh.

## REST API (untuk agen / scripting)

Base URL: `http://localhost:3000` (atau URL tunnel). Kalau `BRIDGE_TOKEN` di-set,
tambahkan header `Authorization: Bearer <token>` di semua request (kecuali `/api/health`).

| Method & path | Body | Keterangan |
|---|---|---|
| `GET /api/health` | — | status service & adb |
| `GET /api/devices` | — | daftar device adb |
| `POST /api/connect` | `{"host":"192.168.1.20:5555"}` | wireless connect |
| `GET /api/screen-size?serial=` | — | `{width,height,model}` layar |
| `GET /api/screenshot?serial=` | — | **PNG** screenshot saat ini |
| `POST /api/tap` | `{"x":540,"y":1200}` | tap (koordinat pixel device) |
| `POST /api/swipe` | `{"x1":540,"y1":1800,"x2":540,"y2":600,"durationMs":400}` | swipe |
| `POST /api/key` | `{"code":"4"}` | tombol: 3=home 4=back 187=recent 26=power 24/25=volume |
| `POST /api/text` | `{"text":"halo"}` | ketik teks |
| `POST /api/unlock` | — | nyalakan layar + swipe buka kunci |

Contoh loop agen (bash):

```bash
BASE=https://xxx.trycloudflare.com
TOKEN=isi-token-disini
# 1. lihat ukuran layar
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/screen-size"
# 2. ambil screenshot
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/screenshot" -o shot.png
# 3. tap di tengah
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"x":540,"y":1200}' "$BASE/api/tap"
```

## Troubleshooting

- **`adb tidak ditemukan`** → install platform-tools & tambahkan ke PATH, atau isi `ADB_PATH` di `.env` dengan full path.
- **device `unauthorized`** → cabut-colok USB, setujui dialog "Allow USB debugging?" di HP (centang always allow).
- **screenshot hitam / gagal** → buka kunci layar HP dulu (tombol 🔓 unlock di UI), atau app yang dibuka memblokir screencap (DRM).
- **Windows**: pakai adb dari platform-tools terbaru; `start.bat` butuh `python` di PATH.
- **Lemot via tunnel** → turunkan ke 0.5 fps di UI; tiap screenshot ~200–500 KB.
- **HP kedua tidak kepilih** → pilih serial di dropdown Device, atau set `ANDROID_SERIAL` di `.env`.

## Roadmap

- **Phase 1** (ini): remote kontrol web + API ✅
- **Phase 2**: otak strategi CoC — deteksi base via computer vision, template serangan, loop belajar (bandit/RL ringan)
- Nanti: multi-touch/pinch, rekam aksi, clipboard sync

## Lisensi

MIT — pakai bebas, risiko di tangan masing-masing. Ingat: automasi game bisa melanggar
ToS game (risiko ban akun) — disarankan pakai akun eksperimen.
