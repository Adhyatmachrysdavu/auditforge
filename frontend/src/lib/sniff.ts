/**
 * Pengenalan perkakas dari isi berkas, di sisi peramban.
 *
 * PERINGATAN — ATURAN GANDA. Berkas ini MENIRU `backend/app/parsers/`, dan
 * keduanya harus tetap seiring. Yang menentukan hasil akhir tetap backend:
 * `select_parser()` di `backend/app/parsers/__init__.py`. Fungsi di sini hanya
 * mendahului tebakannya agar pengguna melihat perkakasnya terisi sebelum
 * menekan Unggah. Bila salah satu parser di backend berubah aturan
 * pengenalannya, ubah juga di sini — kalau tidak, dropdown akan menampilkan
 * tebakan yang keliru sementara backend mengurai dengan benar.
 *
 * Urutan pemeriksaan wajib sama dengan `_PARSERS` di backend, sebab berkas
 * bisa memenuhi lebih dari satu aturan. Contohnya keluaran ZAP berformat JSON
 * juga berawalan `{`, jadi Nuclei diperiksa lebih dulu dan SARIF paling akhir.
 *
 * Sumber tiap aturan:
 *   nuclei → parsers/nuclei.py:sniff
 *   zap    → parsers/zap.py:sniff
 *   nmap   → parsers/nmap.py:sniff
 *   burp   → parsers/burp.py:sniff
 *   sarif  → parsers/sarif.py:sniff
 */

/** Perkakas yang dikenali. Sama persis dengan `ScanTool` di backend. */
export type SniffedTool = "nuclei" | "zap" | "nmap" | "burp" | "sarif";

/**
 * Backend memotong 4096 **byte**; di sini 4096 **karakter**. Untuk berkas
 * UTF-8 multibyte potongannya sedikit lebih panjang, jadi lebih longgar,
 * bukan lebih ketat — penanda yang dicari selalu berada di kepala berkas.
 */
const HEAD = 4096;

/**
 * Di atas ukuran ini berkas tidak diuraikan sebagai JSON di peramban.
 * Aturan ZAP dan SARIF menuntut mengurai seluruh isi, dan mengerjakan itu
 * pada berkas ratusan megabyte akan membekukan tab. Melewatinya aman:
 * hasilnya jadi "tak dikenali", dan backend tetap mendeteksinya sendiri.
 */
const BATAS_JSON = 8 * 1024 * 1024;

/** Baris tak kosong pertama. Setara `first_json_line()` di parsers/util.py. */
function barisPertama(teks: string): string | null {
  for (const baris of teks.split(/\r?\n/)) {
    const s = baris.trim();
    if (s) return s;
  }
  return null;
}

function jsonObjek(teks: string): Record<string, unknown> | null {
  if (teks.length > BATAS_JSON) return null;
  if (teks.trimStart()[0] !== "{") return null;
  try {
    const data: unknown = JSON.parse(teks);
    return data && typeof data === "object" && !Array.isArray(data)
      ? (data as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function nuclei(namaBerkas: string, teks: string): boolean {
  if (namaBerkas.toLowerCase().endsWith(".jsonl")) return true;
  const baris = barisPertama(teks);
  return (
    !!baris &&
    (baris.includes("template-id") ||
      baris.includes("templateID") ||
      baris.includes("template_id")) &&
    baris.includes("info")
  );
}

function zap(teks: string): boolean {
  if (teks.trimStart()[0] === "{") {
    const data = jsonObjek(teks);
    return !!data && "site" in data;
  }
  const kepala = teks.slice(0, HEAD);
  return kepala.includes("OWASPZAPReport") || kepala.includes("alertitem");
}

function nmap(teks: string): boolean {
  return teks.slice(0, HEAD).includes("<nmaprun");
}

function burp(teks: string): boolean {
  const kepala = teks.slice(0, HEAD);
  return (
    kepala.includes("burpVersion") ||
    (kepala.includes("<issues") && kepala.includes("<issue"))
  );
}

function sarif(teks: string): boolean {
  const data = jsonObjek(teks);
  return !!data && "runs" in data;
}

/**
 * Kenali perkakas dari nama dan isi berkas. `null` berarti tak dikenali;
 * pemanggilnya harus menyerahkan keputusan ke backend, bukan menebak sendiri.
 */
export function sniffTool(namaBerkas: string, teks: string): SniffedTool | null {
  if (nuclei(namaBerkas, teks)) return "nuclei";
  if (zap(teks)) return "zap";
  if (nmap(teks)) return "nmap";
  if (burp(teks)) return "burp";
  if (sarif(teks)) return "sarif";
  return null;
}

/** Baca berkas lalu kenali perkakasnya. Kegagalan baca diperlakukan sebagai tak dikenali. */
export async function sniffFile(file: File): Promise<SniffedTool | null> {
  try {
    // Berkas besar dipotong: seluruh aturan hanya melihat kepala berkas,
    // kecuali ZAP/SARIF yang butuh JSON utuh — dan keduanya sudah dilewati
    // di atas BATAS_JSON. Memotong di sini menahan pemakaian memori tab.
    const potongan = file.size > BATAS_JSON ? file.slice(0, HEAD * 4) : file;
    return sniffTool(file.name, await potongan.text());
  } catch {
    return null;
  }
}
