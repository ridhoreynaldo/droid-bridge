# Templates

Folder ini berisi gambar template (PNG) untuk computer vision cocbot.
Bot memakai template matching (opencv) untuk menemukan tombol/ikon di layar
secara presisi — lebih akurat daripada koordinat mentah.

## Cara membuat template (dari web UI)

1. Buka layar yang diinginkan di HP (mis. layar hasil pertempuran).
2. Di panel **CoC Bot**, isi nama template → klik **📸 jadikan template**.
3. File tersimpan sebagai `templates/<nama>.png`.

## Template yang dikenali bot (nama harus persis)

| Nama | Fungsi |
|---|---|
| `attack_button` | tombol Attack di home village (ganti koordinat config) |
| `find_match` | tombol "Find a match" |
| `next_button` | tombol Next saat scouting |
| `troop_bar` | penanda layar battle-prep (mis. potongan troop bar) |
| `battle_result` | penanda layar hasil (mis. panel Victory/Defeat) |
| `return_home` | tombol "Return Home" di layar hasil |
| `end_battle` | tombol "End Battle" |
| `surrender_ok` | tombol konfirmasi surrender |
| `star` | **satu ikon bintang penuh** — dipakai menghitung bintang (0-3) |

Tips: crop sekecil mungkin tapi unik (cukup ikon/tombolnya saja, bukan
seluruh layar). Kalau skor match rendah, coba capture ulang dengan ukuran
layar yang sama — template matching sensitif terhadap skala.
