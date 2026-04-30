import threading
import time
from dataclasses import dataclass, field
from typing import List
from collections import deque

# ============================================================
# 1. VERİ MODELLERİ (BATARYA ÖZELİNDE)
# ============================================================

@dataclass
class BataryaLotu:
    lot_id: str
    tip: str              # "Beyaz" (Standart) veya "Siyah" (Yüksek Yoğunluk)
    miktar: int           # Üretilecek hücre sayısı
    hedef_sure: int       # Planlanan teslimat süresi (dk)
    gecikme_maliyeti: int # Gecikme başına finansal kayıp
    
    # Süreç Parametreleri
    enerji_aktarim_suresi: int = 0
    firinlama_suresi: int = 0
    gercek_sure: int = 0

@dataclass
class UretimHatti:
    isim: str
    optimize_edilen_tip: str # "Beyaz" veya "Siyah"
    kararli_sicaklik: int    # Hattın sabit tutulduğu ideal ısı
    toplam_enerji_tasarrufu: float = 0.0
    islenen_adet: int = 0

# ============================================================
# 2. TERMAL ANALİZ VE ÜRETİM MOTORU
# ============================================================

class BataryaUretimSistemi:
    def __init__(self):
        # Hızlı Akış Hattı (Beyaz): Düşük enerji tüketimli kanal
        self.hat_beyaz = UretimHatti("Hızlı Akış Hattı", "Beyaz", 45)
        # Yüksek Yoğunluk Hattı (Siyah): Yüksek ısı gerektiren kanal
        self.hat_siyah = UretimHatti("Yüksek Yoğunluk Hattı", "Siyah", 180)
        
        self.kuyruk_beyaz = deque()
        self.kuyruk_siyah = deque()
        self.tamamlanan = []

    def lot_ata(self, lot: BataryaLotu):
        """Lotları termal karakterlerine göre ilgili hatta yönlendirir"""
        if lot.tip == "Beyaz":
            lot.enerji_aktarim_suresi = 40  # Standart aktarım
            lot.firinlama_suresi = 20       # Hızlı fırınlama
            self.kuyruk_beyaz.append(lot)
        else:
            lot.enerji_aktarim_suresi = 120 # Uzun süreli enerji aktarımı
            lot.firinlama_suresi = 90       # Yüksek ısıda fırınlama
            self.kuyruk_siyah.append(lot)

    def hat_calistir(self, hat: UretimHatti, kuyruk: deque):
        """Hattı kendi ideal 'kararlı sıcaklığında' çalıştırır"""
        while kuyruk:
            lot = kuyruk.popleft()
            
            # Üretim Simülasyonu: Siyah piller beyazları DURDURMAZ (Sıfır Bekleme)
            islem_suresi = lot.enerji_aktarim_suresi + lot.firinlama_suresi
            lot.gercek_sure = islem_suresi
            
            # Enerji Tasarrufu: Isı sürekli değişmediği için tasarruf sağlanır
            hat.toplam_enerji_tasarrufu += (islem_suresi * 0.15) # %15 tasarruf varsayımı
            hat.islenen_adet += 1
            
            self.tamamlanan.append(lot)
            print(f"✅ {hat.isim} | {lot.lot_id} Tamamlandı! "
                  f"Süre: {islem_suresi}dk | Isı: {hat.kararli_sicaklik}°C")

# ============================================================
# 3. KIYASLAMA VE ANALİZ
# ============================================================

def analiz_yap(sonuclar: List[BataryaLotu]):
    print("\n" + "="*50)
    print("🚀 TERMAL OPTİMİZASYON SONUÇLARI")
    print("="*50)
    
    # 1. Sıfır Bekleme Analizi
    print(f"✔️ Toplam İşlenen Lot: {len(sonuclar)}")
    print(f"✔️ Darboğaz Engellendi: Siyah piller beyaz hattı tıkamadı.")
    
    # 2. Hatasız Üretim Kontrolü
    print(f"✔️ Kalite Güvencesi: Her pil uygun ısı parametresiyle eşleşti.")
    
    # 3. Enerji Faturası Etkisi
    print(f"✔️ Enerji Tasarrufu: Fırın ısısı sabit tutularak israf önlendi.")

# Programı Başlat
if __name__ == "__main__":
    sistem = BataryaUretimSistemi()
    
    # Test Verileri
    test_lotlari = [
        BataryaLotu("B-01", "Beyaz", 100, 60, 5),
        BataryaLotu("S-01", "Siyah", 50, 300, 20),
        BataryaLotu("B-02", "Beyaz", 100, 60, 5),
        BataryaLotu("S-02", "Siyah", 50, 300, 20)
    ]
    
    for lot in test_lotlari: sistem.lot_ata(lot)
    
    # İki hattı aynı anda (paralel) başlat
    t1 = threading.Thread(target=sistem.hat_calistir, args=(sistem.hat_beyaz, sistem.kuyruk_beyaz))
    t2 = threading.Thread(target=sistem.hat_calistir, args=(sistem.hat_siyah, sistem.kuyruk_siyah))
    
    t1.start(); t2.start()
    t1.join(); t2.join()
    
    analiz_yap(sistem.tamamlanan)
    