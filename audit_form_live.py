"""Audit baca-saja kontrol pada tab Chrome yang sudah terbuka.

Tidak menavigasi, mengklik, mengisi, mengambil nilai, atau menyimpan HTML.
Audit ini bukan pengujian pengiriman dan tidak mengubah riwayat lamaran.
"""

from browser import tempel_chrome

# Hanya statistik; tidak membaca teks halaman, atribut identitas, nilai isian,
# cookie, atau URL lengkap. Host hanya dipakai menentukan kategori situs.
# Iframe dan shadow DOM tidak diperiksa.
SKRIP_BACA = r"""
const host = location.hostname.toLowerCase();
const situs = ['jobstreet.com', 'glints.com', 'indeed.com'].find(
    domain => host === domain || host.endsWith('.' + domain)) || 'lain';
const hasil = {situs, kontrol: 0, wajib: 0, radio: 0, checkbox: 0,
               select: 0, combobox: 0, teks: 0,
               pilihan_terpilih: 0, pilihan_tidak_terpilih: 0,
               pilihan_tidak_diketahui: 0, iframe: 0};
hasil.iframe = document.querySelectorAll('iframe').length;
for (const el of document.querySelectorAll(
    'input, select, textarea, [role="radio"], [role="checkbox"], '
    + '[role="combobox"]')) {
    const style = window.getComputedStyle(el);
    if (!el.getClientRects().length || style.visibility === 'hidden' ||
        style.display === 'none') continue;
    const tag = el.tagName.toLowerCase();
    const tipe = tag === 'input'
        ? (el.getAttribute('type') || 'text').toLowerCase() : '';
    const role = (el.getAttribute('role') || '').toLowerCase();
    let jenis = '';
    if (role === 'radio' || (tag === 'input' && tipe === 'radio')) jenis = 'radio';
    else if (role === 'checkbox' || (tag === 'input' && tipe === 'checkbox'))
        jenis = 'checkbox';
    else if (role === 'combobox') jenis = 'combobox';
    else if (tag === 'select') jenis = 'select';
    else if (tag === 'textarea' || (tag === 'input' &&
        ['text', 'number', 'email', 'tel', 'url', 'search'].includes(tipe)))
        jenis = 'teks';
    if (!jenis) continue;
    hasil.kontrol++;
    hasil[jenis]++;
    if (el.hasAttribute('required') || el.getAttribute('aria-required') === 'true')
        hasil.wajib++;
    if (jenis === 'radio' || jenis === 'checkbox') {
        let status = null;
        if (tag === 'input' && (tipe === 'radio' || tipe === 'checkbox'))
            status = el.checked;
        else if (el.getAttribute('aria-checked') === 'true') status = true;
        else if (el.getAttribute('aria-checked') === 'false') status = false;
        if (status === true) hasil.pilihan_terpilih++;
        else if (status === false) hasil.pilihan_tidak_terpilih++;
        else hasil.pilihan_tidak_diketahui++;
    }
}
return hasil;
"""


def baca_tab(driver) -> dict:
    """Baca satu tab tanpa navigasi atau interaksi dengan elemen."""
    return driver.execute_script(SKRIP_BACA)


def audit(port: int) -> dict:
    """Tempel hanya ke Chrome yang sudah aktif; jangan membuka browser baru."""
    if not 1 <= port <= 65535:
        raise ValueError("Port Chrome harus antara 1 dan 65535")
    driver = tempel_chrome(port)
    try:
        return baca_tab(driver)
    finally:
        # Hentikan ChromeDriver saja; Chrome yang sudah ada tidak ditutup.
        driver.service.stop()
