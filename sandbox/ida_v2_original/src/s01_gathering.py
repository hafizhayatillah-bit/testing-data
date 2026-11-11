"""TAHAP 1 - GATHERING.
Membaca nilai (cached) dari Draft_DS_Kurir_v2.xlsx dan menyimpannya sebagai CSV mentah
berformat rapi. Tidak ada perubahan nilai di tahap ini; hanya penamaan kolom dan pemisahan tabel.
"""
import re
import unicodedata
import pandas as pd
from openpyxl import load_workbook

from .config import RAW, XLSX


def slug(s, maks=55):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:maks]


def tabel(ws, header_row, first_row, last_row, ncols, nama=None):
    hdr = [ws.cell(header_row, c).value for c in range(1, ncols + 1)]
    cols = nama or [slug(h) for h in hdr]
    rows = [[ws.cell(r, c).value for c in range(1, ncols + 1)] for r in range(first_row, last_row + 1)]
    return pd.DataFrame(rows, columns=cols)


T4_COLS = ["klaster", "jarak_rute_km", "jarak_tempuh_pp_km", "biaya_motor_per_km", "biaya_motor_per_antaran",
           "upah_penuh", "upah_efektif", "untung_kurir_per_antaran", "waktu_per_antaran_menit",
           "untung_kurir_per_jam", "status_kurir", "biaya_cabang_per_antaran", "biaya_2m_sebelum_ongkir",
           "ongkir_minimum_2m", "pembanding", "batas_ongkir", "ongkir_disarankan", "subsidi_2m",
           "kantong_2m", "status_2m", "ongkir_lama", "kantong_2m_lama", "status_lama"]
T2_COLS = ["kode", "jenis_motor", "klaster", "konsumsi_klaim_kmpl", "sumber_konsumsi", "faktor_penyesuaian",
           "konsumsi_dipakai_kmpl", "harga_bensin", "energi_rp_km", "perawatan_rp_km", "harga_motor",
           "penyusutan_rp_km", "total_rp_km", "total_macet_rp_km", "bobot_armada", "tingkat_keyakinan"]


def parameter(ws):
    rows, sec = [], ""
    for r in range(3, ws.max_row + 1):
        a, b = ws.cell(r, 1).value, ws.cell(r, 2).value
        if a is None:
            continue
        if re.match(r"^[A-I]\. ", str(a)) and b is None:
            sec = str(a)
            continue
        rows.append([sec, a, b] + [ws.cell(r, c).value for c in range(3, 7)])
    df = pd.DataFrame(rows, columns=["bagian", "parameter", "nilai", "satuan", "tingkat", "status", "sumber_catatan"])
    df["nilai_num"] = pd.to_numeric(df["nilai"], errors="coerce")
    return df


def main():
    wb = load_workbook(XLSX, data_only=True)
    out = {}
    out["parameter_model_raw"] = parameter(wb["Parameter"])
    out["motor_klaster_raw"] = tabel(wb["T2_Klaster_Motor"], 3, 4, 10, 16, T2_COLS)
    out["klaster_ringkasan_raw"] = tabel(wb["T2_Klaster_Motor"], 13, 14, 15, 12)
    out["pembanding_harga_raw"] = tabel(wb["T3_Pembanding_Harga"], 9, 10, 17, 6,
                                         ["jarak_km", "pembanding_rp", "ojol_penumpang_ref_rp", "ongkir_disarankan_rp",
                                          "selisih_rp", "ongkir_lama_rp"])
    out["grid_jarak_excel_raw"] = tabel(wb["T4_Grid_Jarak"], 5, 6, 85, 23, T4_COLS)
    out["target_kurir_excel_raw"] = tabel(wb["T5_Target_Kurir"], 10, 11, 26, 21)
    out["skenario_t6_excel_raw"] = tabel(wb["T6_Sensitivitas"], 58, 59, 64, 28)
    out["tornado_excel_raw"] = tabel(wb["T6_Sensitivitas"], 21, 22, 27, 7)
    out["sebaran_jarak_excel_raw"] = tabel(wb["T7_Skenario_Jarak"], 3, 4, 21, 13)
    out["sebaran_jarak_ringkas_raw"] = tabel(wb["T7_Skenario_Jarak"], 25, 26, 31, 9)
    out["output_tidy_excel_raw"] = tabel(wb["Output_Tidy"], 2, 3, wb["Output_Tidy"].max_row, 8)
    out["sumber_data_sekunder_raw"] = tabel(wb["Panduan"], 35, 36, 45, 4,
                                             ["data", "nilai_dipakai", "sumber", "catatan"])
    for nama, df in out.items():
        df.to_csv(RAW / f"{nama}.csv", index=False)
        print(f"[gathering] {nama}.csv  {df.shape}")
    pd.DataFrame({"sheet": wb.sheetnames}).to_csv(RAW / "inventaris_sheet.csv", index=False)


if __name__ == "__main__":
    main()
