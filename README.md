# dimastes — JobStreet Job Review Assistant

Alat bantu (Bahasa Indonesia) untuk mencari lowongan di
[id.jobstreet.com](https://id.jobstreet.com) **mulai dari yang paling baru
diposting**, menyaringnya sesuai kriteria Anda, lalu:

- **mode manual** — setiap lowongan dibuka di Chrome agar Anda tinjau dan
  kirim lamarannya sendiri, atau
- **mode otomatis** — bot menekan Lamar/Lanjutkan/Kirim lamaran sendiri.
  Bila alur tidak bisa dipastikan (lamaran lewat situs perusahaan, perlu
  unggah berkas, ada pertanyaan wajib), lowongan dikembalikan ke Anda
  sebagai daftar "perlu dilamar manual".

Program tidak menyimpan password JobStreet; login tetap Anda lakukan sendiri
di browser.

> **Penting:** melamar otomatis berarti mengirim lamaran tanpa Anda baca
> dulu. Pastikan CV dan profil JobStreet sudah benar, gunakan batas harian
> yang wajar, dan sadari bahwa otomatisasi dapat melanggar ketentuan layanan
> JobStreet (risiko akun dibatasi). Gunakan dengan tanggung jawab sendiri.

## Fitur

- Mencari lowongan berdasarkan daftar kata kunci dan **banyak lokasi**
  sekaligus (Bandung, Jakarta, Tangerang, Jababeka, Cimahi, Purwakarta,
  Bogor, dan seterusnya).
- Menyimpan lowongan ke SQLite agar tidak diproses dua kali.
- Lowongan yang sudah berlabel **"Applied"/"Anda sudah melamar"** di JobStreet
  otomatis dilewati: tidak ditampilkan lagi, tidak dilamar ulang, dan tidak
  memakan kuota harian.
- Menyaring lowongan: **judul harus cocok dengan minat**, kata kunci
  terlarang, posisi terlalu senior, gaji minimum, batas pengalaman, umur
  lowongan, dan (opsional) lokasi ketat.
- Hasil pencarian diurutkan **dari yang terbaru** (`sortmode=ListedDate`),
  dengan opsi hanya mengambil lowongan N hari terakhir.
- Memeringkat lowongan: yang terbaru didahulukan, lalu skor relevansi.
- Mode manual: halaman lowongan dibuka di Chrome, Anda yang melamar.
- Mode otomatis (`run --auto`): klik Lamar → Lanjutkan → Kirim lamaran,
  dengan pengaman dan batas per sesi.
- **Sesi login tersimpan** di profil Chrome khusus, jadi login hanya sekali
  (tidak setiap kali menjalankan).
- **Mode otomatis adalah default**: `python cli.py run` langsung melamar
  otomatis. Isian cover letter dan unggah CV juga otomatis bila
  `COVER_LETTER`/`RESUME_PATH` diisi.
- Mencatat lamaran yang sudah dikirim beserta batas harian.
- Blacklist perusahaan dan notifikasi Telegram (opsional).
- Laporan singkat di akhir sesi: `python cli.py stats`, `history`, `config`.
- Perintah `python cli.py repair` untuk merapikan data lama (judul kosong,
  status tidak seragam, baris lamaran ganda).

## Kebutuhan

- Python **3.10+**
- Google Chrome (Selenium 4.6+ mengunduh ChromeDriver otomatis)
- Koneksi internet

## Cara cepat (disarankan)

Skrip bantu sudah disiapkan: ia membuat `.venv`, memasang dependensi,
menyalin `.env.example` menjadi `.env` (sekali), lalu menjalankan perintah.

**Windows** — letakkan folder proyek di tempat biasa (misalnya
`C:\Users\NamaAnda\Documents\dimastes`, **bukan** di `C:\WINDOWS`), buka
PowerShell/Command Prompt di folder itu, lalu:

```powershell
.\jalankan.bat config
.\jalankan.bat run
```

Di Command Prompt lama, `.\` boleh dihilangkan (`jalankan.bat run`).

**macOS / Linux**:

```bash
chmod +x jalankan.sh
./jalankan.sh config
./jalankan.sh run
```

Argumen apa pun diteruskan ke `cli.py`, misalnya
`jalankan.bat history --limit 10` atau `jalankan.bat repair`.

## Instalasi manual

```bash
git clone https://github.com/dimasw1997/dimastes.git
cd dimastes

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Konfigurasi

Semua pengaturan dibaca dari file `.env` di folder proyek. Kunci yang belum
ada di `.env` (misalnya setelah pembaruan versi) otomatis memakai nilai dari
`.env.example`, jadi Anda tidak perlu menyalin ulang file contoh. Mulai dari
contoh:

```bash
cp .env.example .env
```

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `KEYWORDS` | `inventory control,PPIC,...` | Daftar kata kunci, dipisah koma |
| `LOCATIONS` | kosong | Daftar lokasi dipisah koma, mis. `Bandung,Jakarta,Tangerang` |
| `LOCATION` | `Bandung` | Dipakai hanya bila `LOCATIONS` kosong |
| `ALLOW_REMOTE` | `false` | `true` = lowongan "Remote" juga diterima saat `STRICT_LOCATION` aktif |
| `REQUIRE_KEYWORD_MATCH` | `true` | Hanya lamar lowongan yang judulnya cocok dengan minat |
| `TITLE_KEYWORDS` | kosong | Kata kunci untuk mencocokkan judul (kosong = ikut `KEYWORDS`) |
| `MIN_SALARY` | `0` | Gaji minimum (0 = tanpa filter) |
| `MAX_EXPERIENCE_YEARS` | `5` | Tolak lowongan yang minta pengalaman lebih dari ini |
| `EXCLUDE_KEYWORDS` | `principal,director,head,senior,lead` | Kata yang membuat judul otomatis ditolak |
| `STRICT_LOCATION` | `false` | `true` = tolak lowongan yang lokasinya di luar `LOCATION` |
| `MAX_APPLY_PER_DAY` | `5` | Batas lamaran tercatat per hari |
| `DELAY_BETWEEN_APPLY` | `3` | Jeda (detik) antar lowongan |
| `MAX_PAGES` | `3` | Jumlah halaman hasil pencarian per kata kunci |
| `HEADLESS_MODE` | `false` | `true` = Chrome tanpa jendela (tidak cocok untuk tinjau manual) |
| `TELEGRAM_BOT_TOKEN` | kosong | Opsional, untuk notifikasi |
| `TELEGRAM_CHAT_ID` | kosong | Opsional, untuk notifikasi |
| `SORT_MODE` | `ListedDate` | Urutan hasil; `ListedDate` = terbaru dulu, `KeywordRelevance` = relevansi |
| `PREFER_NEWEST` | `true` | Dahulukan lowongan paling baru saat antrean melamar |
| `MAX_AGE_DAYS` | `0` | Hanya lowongan N hari terakhir (0 = semua). Nilai valid JobStreet: 1, 3, 7, 14, 31 |
| `USE_PROFILE` | `true` | Simpan sesi login di profil Chrome khusus |
| `CHROME_PROFILE_DIR` | `~/.dimastes/chrome-profile` | Lokasi profil Chrome |
| `LOGIN_WAIT` | `true` | `false` = jangan menunggu; berhenti bila belum login |
| `LOGIN_TIMEOUT` | `300` | Lama menunggu login di Chrome (detik) |
| `AUTO_APPLY` | `true` | Kirim lamaran otomatis; pakai `run --manual` untuk meninjau sendiri |
| `COVER_LETTER` | kosong | Teks cover letter/pesan yang diisi otomatis |
| `RESUME_PATH` | kosong | Path berkas CV untuk unggah otomatis |
| `AUTO_APPLY_MAX_PER_SESSION` | `25` | Batas lamaran otomatis per sesi |
| `AUTO_APPLY_STEP_TIMEOUT` | `3` | Batas detik mengenali tiap langkah; lewat itu lowongan dilewati |
| `DB_PATH` | `jobstreet_auto.db` | Lokasi file database |

## Cara pakai

```bash
# 1. Lihat konfigurasi yang benar-benar terbaca
python cli.py config

# 2a. Jalankan pencarian + kirim lamaran otomatis (default)
python cli.py run

# 2b. Meninjau sendiri (tanpa mengirim otomatis)
python cli.py run --manual

# Hanya lowongan 3 hari terakhir, 5 halaman per kata kunci
python cli.py run --auto --max-age-days 3 --max-pages 5

# Lokasi lain tanpa mengubah .env
python cli.py run --auto --locations "Bandung,Jakarta,Tangerang,Jababeka"

# 3. Lihat hasil
python cli.py stats
python cli.py history --limit 20

# 4. Blacklist perusahaan
python cli.py blacklist "PT Contoh" --reason "tidak sesuai"

# 5. Rapikan data lama
python cli.py repair
```

Saat `run` berjalan:

1. Chrome terbuka. Bila sesi belum ada, Anda login di Chrome — **tidak perlu
   menekan apa pun di terminal**, program mendeteksinya sendiri.
2. Setiap lowongan yang lolos filter dibuka satu per satu.
3. Tinjau di browser. Setelah selesai, kembali ke terminal:
   - tekan **Enter** saja jika lamaran **tidak** dikirim (dicatat `skipped`);
   - ketik **y** jika lamaran benar-benar sudah dikirim (dicatat `applied`).

### Login sekali saja (sesi tersimpan)

Secara default program memakai profil Chrome sendiri di
`~/.dimastes/chrome-profile` (Windows: `C:\Users\NamaAnda\.dimastes\chrome-profile`).
Jadi:

1. Jalankan pertama kali: `python cli.py run --auto`
2. Login di jendela Chrome yang terbuka. Program menunggu dan mendeteksinya
   otomatis (tanpa Enter), maksimal `LOGIN_TIMEOUT` detik.
3. Sesi disimpan. Sesi berikutnya program mendeteksi sudah login dan
   **tidak menanyakan apa pun**.

Program **tidak pernah meminta email atau password JobStreet** — tidak ada
formulir kredensial di mana pun. Semua login terjadi di jendela Chrome milik
Anda, dan hasilnya disimpan sebagai cookie di profil tersebut.

Untuk sesi terjadwal/tanpa orang di depan komputer:

```bash
python cli.py run --auto --no-login-wait
```

Perintah itu langsung berhenti dengan pesan jelas bila sesi sudah kedaluwarsa
(sehingga Anda tahu perlu login sekali lagi), bukan menggantung menunggu.

Opsi lain: `--profile-dir "D:\chrome-dimastes"` untuk lokasi profil lain, dan
`--no-profile` untuk kembali ke profil sementara (selalu login ulang).

Pastikan Chrome lain tidak memakai folder profil yang sama; bila terkunci,
tutup Chrome tersebut atau pakai `--profile-dir` yang berbeda.

Bila sesi JobStreet kedaluwarsa di tengah sesi, program mendeteksinya
(halaman dialihkan ke Sign in) lalu **berhenti** dengan pesan jelas, bukan
mengulang-ulang error. Login sekali lagi, sesi tersimpan kembali.

Ingin memaksa login ulang dari nol? Hapus folder profil:

```powershell
Remove-Item -Recurse -Force "$HOME\.dimastes\chrome-profile"
```

atau jalankan sekali dengan `--no-profile`.

### Banyak lokasi

Isi `.env`:

```
LOCATIONS=Bandung,Jakarta,Tangerang,Jababeka,Cimahi,Purwakarta,Bogor
STRICT_LOCATION=true
```

Pencarian dijalankan **per lokasi** (bukan digabung), lalu hasilnya
digabung dan diurutkan dari yang terbaru. Karena itu:

- Jumlah pencarian = lokasi × kata kunci × halaman. Dengan 7 lokasi,
  8 kata kunci, dan `MAX_PAGES=3` ada 168 pemuatan halaman. Kurangi
  `MAX_PAGES` (mis. 2) atau pakai `--max-age-days 3` agar lebih cepat.
- `STRICT_LOCATION=true` membuang lowongan di luar daftar lokasi. Nama
  wilayah dicocokkan dengan beberapa alias, misalnya **Jababeka** juga
  menerima lokasi *Cikarang* dan *Bekasi*, **Tangerang** menerima
  *Tangerang Selatan/BSD/Serpong*, **Jakarta** menerima *Jakarta
  Selatan/Pusat/Barat/Timur/Utara*.
- Bila JobStreet tidak mengenali nama lokasi (mis. "Jababeka"), hasilnya
  bisa kosong. Coba `--locations "Bandung,Cikarang,Bekasi,..."` atau cek
  sendiri di situs: `https://id.jobstreet.com/jobs?where=Jababeka`.

### Hanya melamar yang Anda minati

Secara default program **hanya melamar lowongan yang judulnya memuat salah
satu `KEYWORDS`** (mis. mengandung "PPIC", "inventory control", "stock
controller"). Judul yang nyasar di hasil pencarian — misalnya "Marketing
Staff" — otomatis dilewati, tidak dilamar.

Bila ada istilah lain yang juga Anda minati, tambahkan sinonim:

```
TITLE_KEYWORDS=inventory control,inventory controller,PPIC,production planner,material planner,material controller,stock controller,inventory analyst,gudang,stok,production planning
```

Ingin mematikan filter ini (lamar semua yang muncul)? `REQUIRE_KEYWORD_MATCH=false`.

### Isian lamaran otomatis

Bila formulir meminta cover letter atau berkas CV, isi dulu di `.env`:

```
COVER_LETTER=Saya tertarik pada posisi ini dan siap bergabung.\nTerima kasih.
RESUME_PATH=C:\Users\NAMA\Documents\cv.pdf
```

Program akan mengisi textarea kosong dan mengunggah berkas tersebut secara
otomatis, lalu melanjutkan klik Kirim lamaran. Tanpa konfigurasi ini,
lowongan yang meminta isian khusus akan **dilewati** (bukan diminta dikerjakan
manual).

Pertanyaan pilihan wajib dari perusahaan (radio/select) **tidak** ditebak
jawabannya, karena salah jawab lebih merugikan daripada tidak melamar.
Lowongan seperti itu dilewati otomatis dan hanya dicatat di akhir sesi.

### Mode otomatis (default)

`python cli.py run` sudah otomatis. Gunakan `run --manual` hanya bila ingin
meninjau sendiri.

1. Bot membuka halaman lowongan, lalu mencari tombol **Lamar**.
2. Bila muncul langkah berikutnya (**Lanjutkan/Kirim lamaran**), bot menekan
   otomatis sampai muncul konfirmasi "lamaran telah dikirim".
3. Lamaran hanya dicatat `applied` **setelah** konfirmasi itu terlihat.
4. Bot berhenti dan menyerahkan ke Anda bila:
   - lowongan memakai **"Lamar di situs perusahaan"** (ATS eksternal),
   - alur meminta **unggah berkas/cover letter** atau ada **pertanyaan wajib**,
   - alur tidak dikenali dalam `AUTO_APPLY_STEP_TIMEOUT` detik (default **3**);
     lowongan itu langsung dilewati, tanpa jeda, dan lanjut ke berikutnya.
5. Di akhir sesi muncul daftar **"Lowongan yang perlu Anda lamar manual"**
   lengkap dengan tautannya.

Batas pengaman: `MAX_APPLY_PER_DAY` (harian), `AUTO_APPLY_MAX_PER_SESSION`
(per sesi), dan `DELAY_BETWEEN_APPLY` (jeda antar lamaran). Jangan
menaikkannya terlalu tinggi.

### Versi ringan tanpa Selenium

```bash
python buka_pencarian.py
```

Perintah ini membuka tab pencarian JobStreet untuk setiap lokasi × kata
kunci (default maksimal 24 tab) dan menyiapkan `catatan_lamaran.csv` sebagai
pelacak manual.

```bash
python buka_pencarian.py --locations "Bandung,Jakarta,Bekasi" --max-tabs 12
```

## Struktur proyek

| File | Isi |
| --- | --- |
| `config.py` | Membaca `.env` dan menyediakan objek `config` |
| `database.py` | Skema dan operasi SQLite (`jobs`, `applications`, `blacklist`) |
| `scraper.py` | Selenium: buka Chrome, cari lowongan, baca kartu lowongan |
| `job_filter.py` | Aturan lolos/tidak dan pemeringkatan |
| `main.py` | Alur sesi: login → cari → saring → tinjau |
| `cli.py` | Perintah `run`, `stats`, `history`, `config`, `repair`, `blacklist` |
| `notifier.py` | Notifikasi Telegram (opsional) |
| `auto_apply.py` | Alur klik Lamar → Lanjutkan → Kirim + deteksi pengaman |
| `buka_pencarian.py` | Pembuka tab pencarian tanpa Selenium |
| `jalankan.bat` / `jalankan.sh` | Skrip bantu: siapkan `.venv`, pasang dependensi, jalankan CLI |
| `tests/` | Unit test untuk filter dan database |

## Seberapa otomatis alat ini?

| Langkah | Status |
|---|---|
| Mencari lowongan di 7 kota | otomatis |
| Urut dari posting terbaru | otomatis |
| Menyaring (senior, gaji, pengalaman, lokasi) | otomatis |
| Login JobStreet | **sekali saja**, lalu tersimpan — satu-satunya langkah yang melibatkan Anda (tanpa Enter) |
| Klik Lamar → Lanjutkan → Kirim | otomatis (`--auto`) |
| Lowongan lewat situs perusahaan (ATS) | **manual** — JobStreet mengalihkan keluar |
| Lowongan berlabel "You applied"/sudah pernah dilamar | otomatis dilewati (tidak ditampilkan) |
| Lowongan yang minta cover letter/unggah CV | otomatis diisi bila `COVER_LETTER`/`RESUME_PATH` disetel; jika tidak, dilewati otomatis |
| Pertanyaan pilihan wajib dari perusahaan | dilewati otomatis (jawaban tidak ditebak) |
| Captcha/OTP saat login | **manual** (tidak bisa dilewati) |
| Menaikkan batas harian, memilih kota | Anda (lewat `.env`/flag) |

Lowongan yang tidak bisa diproses otomatis hanya **dicatat** di akhir sesi
(lengkap dengan tautan) — Anda tidak perlu mengerjakan apa pun agar sesi
selesai.

## Menjalankan test

```bash
pip install pytest
pytest -q
```

Test tidak membutuhkan Chrome maupun koneksi internet.

## Troubleshooting

**Muncul "Tidak ada lowongan yang berhasil dibaca".**
JobStreet kadang mengubah struktur HTML. Pastikan Anda sudah login, halaman
hasil pencarian terbuka normal di Chrome, lalu periksa selector di
`scraper.py` (`CARD_SELECTORS` dan `_parse_job_card`).

**Chrome tidak bisa dibuka.**
Pastikan Google Chrome terpasang dan bukan versi portabel. Bila unduhan
ChromeDriver otomatis gagal, program mencoba `webdriver-manager`; Anda juga
bisa memasang ChromeDriver manual dan menaruhnya di `PATH`.

**Riwayat menampilkan posisi kosong.**
Itu data lama dari versi sebelumnya yang menyimpan judul kosong. Jalankan
`python cli.py repair`; data lama tidak dihapus, hanya diisi teks pengganti.

**Lowongan muncul tapi lokasinya bukan Kota Anda.**
Aktifkan `STRICT_LOCATION=true` di `.env`.

**Diminta login setiap kali menjalankan.**
Pastikan `USE_PROFILE=true` (default), tidak memakai `--no-profile`, dan
folder profil (`~/.dimastes/chrome-profile` di Windows
`C:\Users\NamaAnda\.dimastes\chrome-profile`) tidak dihapus. Permintaan
login di layar hanya muncul bila cookie sesi benar-benar sudah tidak ada —
program tidak pernah menanyakan email/password.

**Lowongan yang menurut saya relevan malah dilewati.**
Judulnya tidak memuat kata kunci minat. Tambahkan istilahnya ke
`TITLE_KEYWORDS` di `.env` (mis. `gudang`, `stok`, `production planning`),
atau set `REQUIRE_KEYWORD_MATCH=false`.

**Lowongan yang sudah saya lamar masih muncul.**
Pastikan JobStreet sudah menampilkan label "Applied" pada kartu lowongan
tersebut. Bila labelnya tidak terdeteksi, jalankan mode manual sekali dan
kirimkan potongan HTML kartunya agar selector
`APPLIED_CARD_SELECTORS`/`APPLIED_CARD_TEXTS` di `scraper.py` disesuaikan.
Lowongan yang sudah tercatat di database tetap dilewati walau tanpa label.

**Program berhenti dengan pesan "Login dibatalkan" atau "Batas waktu login habis".**
Sesi belum ada dan login tidak terdeteksi. Jalankan lagi, login di Chrome, dan
biarkan jendela Chrome terbuka — program melanjutkan sendiri. Bila Anda memang
tidak ingin menunggu, set `LOGIN_WAIT=false`.

**Terlalu banyak lowongan dilewati dengan alasan "alur tidak dikenali".**
Koneksi/laman JobStreet bisa lambat. Naikkan batasnya, mis. `AUTO_APPLY_STEP_TIMEOUT=8`
di `.env`, lalu jalankan lagi.

**Program masih menunggu Enter saat lowongan dibuka.**
Berarti mode manual aktif. Pastikan `AUTO_APPLY=true` di `.env` (atau jalankan
`run --auto`). Di mode otomatis tidak ada permintaan Enter.

**Semua lowongan masuk "perlu dilamar manual".**
Penyebab yang paling sering: lowongan memakai "Lamar di situs perusahaan",
meminta unggah berkas, atau punya pertanyaan wajib. Bot sengaja tidak menebak
jawaban. Selesaikan lewat tautan di daftar akhir sesi.

**Lowongan Jakarta/Tangerang tidak muncul.**
Pastikan `LOCATIONS` berisi kota itu (bukan hanya `LOCATION`), dan
`STRICT_LOCATION` tidak memakai daftar lama. Cek juga nama lokasi yang
dipakai JobStreet; "Jababeka" sering tampil sebagai *Cikarang* atau *Bekasi*.

**Ingin hanya lowongan yang baru tayang.**
Tambahkan `--max-age-days 3` (atau `1`) saat menjalankan `run`, atau isi
`MAX_AGE_DAYS` di `.env`. Hasil sudah otomatis diurutkan dari yang terbaru.

**Tombol Lamar tidak ditemukan.**
JobStreet memakai beberapa variasi tombol. Jalankan sekali dengan mode manual
(`run --manual`) di jendela Chrome yang terlihat, lalu kirimkan potongan HTML
tombol Lamar agar selector di `auto_apply.py` bisa disesuaikan.

**Lamaran tidak bertambah padahal sudah melamar.**
Pastikan Anda mengetik `y` saat terminal bertanya, bukan hanya Enter. Lamaran
tanpa konfirmasi dicatat sebagai `skipped` dan tidak dihitung di batas harian.

## Catatan

Gunakan alat ini dengan wajar dan sesuai ketentuan layanan JobStreet. Program
hanya membantu proses penelusuran; keputusan melamar tetap milik Anda.
