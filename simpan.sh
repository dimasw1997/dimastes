#!/usr/bin/env bash
# Simpan perubahan ke GitHub dengan satu perintah (macOS/Linux).
# Contoh: ./simpan.sh
#         ./simpan.sh "Perbaiki filter judul"
# Skrip ini: git add -A -> commit -> tarik perubahan terbaru -> push.
# Aman dipakai berkali-kali: kalau tidak ada perubahan, hanya push saja.
set -uo pipefail
cd "$(dirname "$0")"

PESAN="${1:-}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[GAGAL] Folder ini bukan repo Git."
    exit 1
fi

CABANG="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
CABANG="${CABANG:-main}"
echo "[1/4] Cabang: $CABANG"

git add -A

if ! git diff --cached --quiet; then
    if [ -z "$PESAN" ]; then
        PESAN="Update otomatis $(date '+%Y-%m-%d %H:%M')"
    fi
    echo "[2/4] Commit: $PESAN"
    if ! git commit -m "$PESAN"; then
        echo "[GAGAL] Commit ditolak. Periksa pesan di atas."
        exit 1
    fi
else
    echo "[2/4] Tidak ada perubahan baru yang perlu di-commit."
fi

if git ls-remote --exit-code --heads origin "$CABANG" >/dev/null 2>&1; then
    echo "[3/4] Menarik perubahan terbaru dari GitHub..."
    if ! git pull --rebase --autostash origin "$CABANG"; then
        echo "[GAGAL] Gagal menarik perubahan (rebase bentrok)."
        echo "  1. Ketik:  git rebase --abort"
        echo "  2. Simpan salinan folder ini, lalu jalankan lagi ./simpan.sh"
        exit 1
    fi
else
    echo "[3/4] Cabang belum ada di GitHub, langsung dikirim."
fi

echo "[4/4] Mengirim ke GitHub..."
if ! git push origin "$CABANG"; then
    echo "[GAGAL] Push ditolak. Kemungkinan login GitHub belum tersimpan."
    echo "  Jalankan sekali:  git push origin $CABANG"
    echo "  lalu ikuti login (browser/token). Setelah sekali berhasil,"
    echo "  kredensial tersimpan dan ./simpan.sh berikutnya tidak bertanya lagi."
    exit 1
fi

echo
echo "Selesai. Perubahan sudah ada di GitHub (cabang $CABANG)."
