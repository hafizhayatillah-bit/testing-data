"""Jalankan seluruh pipeline DS dari nol:  python run_all.py
Urutan: gathering -> data sintetis -> assessing/cleaning -> analisis -> pemeriksaan akurasi."""
import time
from src import s01_gathering, synth_orders, s02_assessing_cleaning, s04_analisis, s05_cek_akurasi

for nama, fn in [("1 gathering", s01_gathering.main), ("2 data sintetis", synth_orders.main),
                 ("3 assessing + cleaning", s02_assessing_cleaning.main), ("4 analisis", s04_analisis.run),
                 ("5 cek akurasi", s05_cek_akurasi.main)]:
    t = time.time(); print(f"\n=== {nama} ==="); fn(); print(f"(selesai {time.time()-t:.1f} dtk)")
print("\nSELESAI. Lihat data/clean, output/tabel, output/grafik.")
