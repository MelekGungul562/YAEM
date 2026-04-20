import asyncio
import threading
import time
import random
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional
import queue

# ============================================================
# VERİ MODELLERİ
# ============================================================

@dataclass
class Siparis:
    siparis_id: str
    renk: str
    renk_grubu: str          # 'ACIK' veya 'KOYU'
    miktar_kg: float
    oncelik: int             # 1=yüksek, 2=normal, 3=düşük
    teslim_suresi_dk: int    # müşteri istediği süre
    gecikme_cezasi_tl: float # dk başına ceza
    giris_zamani: float = field(default_factory=time.time)
    
    # İşlem süreleri (dakika)
    temizlik_suresi: int = 0
    boyama_suresi: int = 0
    bitis_zamani: Optional[float] = None
    gercek_sure: Optional[float] = None
    gecikme_dk: float = 0
    ceza_tl: float = 0
    atanan_hat: str = ""
    durum: str = "BEKLIYOR"

@dataclass  
class MakineHat:
    hat_adi: str             # "HAT_A" veya "HAT_B"
    hat_tipi: str            # "ACIK_RENK" veya "KOYU_RENK"
    mevcut_renk: Optional[str] = None
    mevcut_renk_grubu: Optional[str] = None
    mesgul: bool = False
    toplam_uretim_kg: float = 0
    toplam_gecikme_ceza: float = 0
    islem_sayisi: int = 0
    bitis_zamani: float = field(default_factory=time.time)
    kimyasal_izolasyon: bool = True  # Çapraz bulaşma yok!

# ============================================================
# RENK VE SÜRE VERİTABANI
# ============================================================

RENK_VERITABANI = {
    # AÇIK RENKLER - Hat A
    "Beyaz":     {"grup": "ACIK", "temizlik": 0,  "boyama": 45,  "hat": "HAT_A"},
    "Pamuk":     {"grup": "ACIK", "temizlik": 5,  "boyama": 40,  "hat": "HAT_A"},
    "Polyester": {"grup": "ACIK", "temizlik": 5,  "boyama": 45,  "hat": "HAT_A"},
    "San Polyester": {"grup": "ACIK", "temizlik": 0, "boyama": 40, "hat": "HAT_A"},
    
    # KOYU RENKLER - Hat B
    "Kirmizi":   {"grup": "KOYU", "temizlik": 10, "boyama": 65,  "hat": "HAT_B"},
    "Yesil":     {"grup": "KOYU", "temizlik": 25, "boyama": 90,  "hat": "HAT_B"},
    "Siyah":     {"grup": "KOYU", "temizlik": 20, "boyama": 330, "hat": "HAT_B"},
    "Lacivert":  {"grup": "KOYU", "temizlik": 15, "boyama": 55,  "hat": "HAT_B"},
}

TEMIZLIK_MATRISI = {
    # (onceki_grup, sonraki_grup) -> ek temizlik süresi (dk)
    ("ACIK",  "ACIK"):  0,    # Açık -> Açık: Hızlı geçiş
    ("ACIK",  "KOYU"):  10,   # Açık -> Koyu: Az temizlik
    ("KOYU",  "ACIK"):  25,   # Koyu -> Açık: Kapsamlı temizlik!
    ("KOYU",  "KOYU"):  5,    # Koyu -> Koyu: Minimal
    (None,    "ACIK"):  0,
    (None,    "KOYU"):  0,
}

# ============================================================
# ANA OPTİMİZASYON SİSTEMİ
# ============================================================

class ParalelUretimSistemi:
    
    def __init__(self):
        self.hat_a = MakineHat("HAT_A", "ACIK_RENK")
        self.hat_b = MakineHat("HAT_B", "KOYU_RENK")
        
        # Ayrı kuyruklar - kimyasal izolasyon!
        self.kuyruk_acik = deque()   # Hat A kuyruğu
        self.kuyruk_koyu = deque()   # Hat B kuyruğu
        
        self.tamamlanan = []
        self.log_kayitlari = []
        self.baslangic = time.time()
        
        # Kilitleme (thread-safe)
        self.lock_a = threading.Lock()
        self.lock_b = threading.Lock()
        
        self._log("🏭 Paralel Üretim Sistemi başlatıldı")
        self._log("   HAT A → Açık/Steril Renkler")
        self._log("   HAT B → Koyu/Yoğun Renkler")
        self._log("   ✅ Kimyasal İzolasyon: AKTİF")
    
    def _log(self, mesaj: str):
        zaman = datetime.now().strftime("%H:%M:%S")
        kayit = f"[{zaman}] {mesaj}"
        self.log_kayitlari.append(kayit)
        print(kayit)
    
    # ----------------------------------------------------------
    # SİPARİŞ SINIFLANDIRMA
    # ----------------------------------------------------------
    
    def siparis_siniflandir(self, siparis: Siparis) -> Siparis:
        """Renk grubuna göre hat ataması yap"""
        if siparis.renk not in RENK_VERITABANI:
            self._log(f"⚠️ Bilinmeyen renk: {siparis.renk}")
            siparis.renk_grubu = "KOYU"  # Güvenli taraf
        else:
            veri = RENK_VERITABANI[siparis.renk]
            siparis.renk_grubu = veri["grup"]
            siparis.temizlik_suresi = veri["temizlik"]
            siparis.boyama_suresi = veri["boyama"]
        
        # Hat ataması
        if siparis.renk_grubu == "ACIK":
            siparis.atanan_hat = "HAT_A"
            self.kuyruk_acik.append(siparis)
        else:
            siparis.atanan_hat = "HAT_B"
            self.kuyruk_koyu.append(siparis)
        
        self._log(f"📋 {siparis.siparis_id} → {siparis.atanan_hat} "
                  f"({siparis.renk} | {siparis.miktar_kg}kg)")
        return siparis
    
    # ----------------------------------------------------------
    # KUYRUK SIRALAMA (Dinamik Öncelik)
    # ----------------------------------------------------------
    
    def kuyruk_sirala(self, kuyruk: deque, hat: MakineHat) -> List[Siparis]:
        """
        Sıralama kriteri:
        1. Gecikme cezası/dakika (yüksek → önce)
        2. Öncelik seviyesi
        3. Temizlik maliyeti (mevcut renkten geçiş)
        """
        liste = list(kuyruk)
        
        def skor(s: Siparis):
            # Gecikme ceza puanı
            ceza_puan = s.gecikme_cezasi_tl * 10
            
            # Öncelik puanı
            oncelik_puan = (4 - s.oncelik) * 50
            
            # Temizlik maliyeti (az temizlik = yüksek puan)
            onceki = hat.mevcut_renk_grubu
            sonraki = s.renk_grubu
            temizlik_ek = TEMIZLIK_MATRISI.get((onceki, sonraki), 10)
            temizlik_puan = -temizlik_ek * 2
            
            return ceza_puan + oncelik_puan + temizlik_puan
        
        return sorted(liste, key=skor, reverse=True)
    
    # ----------------------------------------------------------
    # TEMİZLİK SÜRESİ HESAPLAMA
    # ----------------------------------------------------------
    
    def temizlik_suresi_hesapla(self, hat: MakineHat, 
                                 yeni_siparis: Siparis) -> int:
        """Hat geçmişine göre gerçek temizlik süresini hesapla"""
        onceki_grup = hat.mevcut_renk_grubu
        yeni_grup = yeni_siparis.renk_grubu
        
        ek_sure = TEMIZLIK_MATRISI.get((onceki_grup, yeni_grup), 0)
        temel_sure = yeni_siparis.temizlik_suresi
        
        toplam = temel_sure + ek_sure
        
        if toplam > 0:
            self._log(f"   🧹 {hat.hat_adi} Temizlik: {toplam}dk "
                      f"({onceki_grup} → {yeni_grup})")
        return toplam
    
    # ----------------------------------------------------------
    # SİPARİŞ İŞLEME (Simülasyon)
    # ----------------------------------------------------------
    
    def siparis_isle(self, siparis: Siparis, hat: MakineHat) -> dict:
        """Tek bir siparişi işle ve sonuç döndür"""
        
        # Temizlik süresi
        temizlik = self.temizlik_suresi_hesapla(hat, siparis)
        
        # Toplam işlem süresi
        toplam_sure = temizlik + siparis.boyama_suresi
        
        # Gecikme hesabı
        gecikme = max(0, toplam_sure - siparis.teslim_suresi_dk)
        ceza = gecikme * siparis.gecikme_cezasi_tl
        
        # Durum güncelle
        siparis.gercek_sure = toplam_sure
        siparis.gecikme_dk = gecikme
        siparis.ceza_tl = ceza
        siparis.durum = "TAMAMLANDI"
        siparis.bitis_zamani = time.time()
        
        # Hat durumu güncelle
        hat.mevcut_renk = siparis.renk
        hat.mevcut_renk_grubu = siparis.renk_grubu
        hat.toplam_uretim_kg += siparis.miktar_kg
        hat.toplam_gecikme_ceza += ceza
        hat.islem_sayisi += 1
        hat.mesgul = False
        
        sonuc = {
            "siparis_id": siparis.siparis_id,
            "hat": hat.hat_adi,
            "renk": siparis.renk,
            "miktar_kg": siparis.miktar_kg,
            "temizlik_dk": temizlik,
            "boyama_dk": siparis.boyama_suresi,
            "toplam_dk": toplam_sure,
            "teslim_suresi": siparis.teslim_suresi_dk,
            "gecikme_dk": gecikme,
            "ceza_tl": ceza,
            "durum": "✅" if gecikme == 0 else "⚠️ GECİKME"
        }
        
        self._log(f"   ✅ {siparis.siparis_id} tamamlandı | "
                  f"Süre:{toplam_sure}dk | "
                  f"Gecikme:{gecikme}dk | "
                  f"Ceza:{ceza:.0f}TL")
        
        return sonuc
    
    # ----------------------------------------------------------
    # PARALEL ÇALIŞMA (Ana Fonksiyon)
    # ----------------------------------------------------------
    
    def paralel_calistir(self) -> dict:
        """Hat A ve Hat B'yi aynı anda çalıştır"""
        
        self._log("\n" + "="*60)
        self._log("🚀 PARALEL ÇALIŞMA BAŞLIYOR")
        self._log("="*60)
        
        sonuclar_a = []
        sonuclar_b = []
        
        def hat_calistir(hat: MakineHat, 
                          kuyruk: deque, 
                          sonuc_listesi: list,
                          lock: threading.Lock):
            """Her hat için ayrı thread"""
            
            self._log(f"\n🔷 {hat.hat_adi} başlıyor "
                      f"({len(kuyruk)} sipariş)")
            
            hat.mesgul = True
            
            while kuyruk:
                # Optimal sıralama
                sirali = self.kuyruk_sirala(kuyruk, hat)
                kuyruk.clear()
                kuyruk.extend(sirali)
                
                # Sıradaki siparişi al
                with lock:
                    if not kuyruk:
                        break
                    siparis = kuyruk.popleft()
                
                self._log(f"\n   [{hat.hat_adi}] ▶ {siparis.siparis_id} "
                          f"işleniyor: {siparis.renk} {siparis.miktar_kg}kg")
                
                siparis.durum = "İŞLENİYOR"
                sonuc = self.siparis_isle(siparis, hat)
                
                with lock:
                    sonuc_listesi.append(sonuc)
                    self.tamamlanan.append(siparis)
            
            self._log(f"\n🏁 {hat.hat_adi} tamamlandı! "
                      f"({hat.islem_sayisi} sipariş, "
                      f"{hat.toplam_uretim_kg}kg)")
        
        # Thread'leri başlat
        thread_a = threading.Thread(
            target=hat_calistir,
            args=(self.hat_a, self.kuyruk_acik, 
                  sonuclar_a, self.lock_a),
            name="HAT-A-Thread"
        )
        
        thread_b = threading.Thread(
            target=hat_calistir,
            args=(self.hat_b, self.kuyruk_koyu, 
                  sonuclar_b, self.lock_b),
            name="HAT-B-Thread"
        )
        
        baslangic = time.time()
        thread_a.start()
        thread_b.start()
        
        # İkisi de bitene kadar bekle
        thread_a.join()
        thread_b.join()
        
        sure = time.time() - baslangic
        
        return self._rapor_olustur(sonuclar_a, sonuclar_b, sure)
    
    # ----------------------------------------------------------
    # RAPOR
    # ----------------------------------------------------------
    
    def _rapor_olustur(self, sonuclar_a, sonuclar_b, sure) -> dict:
        
        self._log("\n" + "="*60)
        self._log("📊 PERFORMANS RAPORU")
        self._log("="*60)
        
        # Hat A İstatistikleri
        toplam_gecikme_a = sum(s["gecikme_dk"] for s in sonuclar_a)
        toplam_ceza_a = sum(s["ceza_tl"] for s in sonuclar_a)
        
        # Hat B İstatistikleri
        toplam_gecikme_b = sum(s["gecikme_dk"] for s in sonuclar_b)
        toplam_ceza_b = sum(s["ceza_tl"] for s in sonuclar_b)
        
        self._log(f"\n🔵 HAT A (Açık Renk):")
        self._log(f"   Sipariş: {len(sonuclar_a)} adet")
        self._log(f"   Üretim: {self.hat_a.toplam_uretim_kg} kg")
        self._log(f"   Toplam Gecikme: {toplam_gecikme_a} dk")
        self._log(f"   Gecikme Cezası: {toplam_ceza_a:.0f} TL")
        
        self._log(f"\n🔴 HAT B (Koyu Renk):")
        self._log(f"   Sipariş: {len(sonuclar_b)} adet")
        self._log(f"   Üretim: {self.hat_b.toplam_uretim_kg} kg")
        self._log(f"   Toplam Gecikme: {toplam_gecikme_b} dk")
        self._log(f"   Gecikme Cezası: {toplam_ceza_b:.0f} TL")
        
        toplam_uretim = (self.hat_a.toplam_uretim_kg + 
                         self.hat_b.toplam_uretim_kg)
        toplam_ceza = toplam_ceza_a + toplam_ceza_b
        
        self._log(f"\n{'='*60}")
        self._log(f"📦 TOPLAM ÜRETİM: {toplam_uretim} kg")
        self._log(f"💸 TOPLAM CEZA: {toplam_ceza:.0f} TL")
        self._log(f"⏱️  İŞLEM SÜRESİ: {sure:.2f} saniye")
        self._log(f"✅ KİMYASAL İZOLASYON: Koyu→Açık bulaşma YOK")
        
        return {
            "hat_a": sonuclar_a,
            "hat_b": sonuclar_b,
            "hat_a_istatistik": {
                "siparis": len(sonuclar_a),
                "uretim_kg": self.hat_a.toplam_uretim_kg,
                "gecikme_dk": toplam_gecikme_a,
                "ceza_tl": toplam_ceza_a
            },
            "hat_b_istatistik": {
                "siparis": len(sonuclar_b),
                "uretim_kg": self.hat_b.toplam_uretim_kg,
                "gecikme_dk": toplam_gecikme_b,
                "ceza_tl": toplam_ceza_b
            },
            "toplam_uretim_kg": toplam_uretim,
            "toplam_ceza_tl": toplam_ceza
        }

# ============================================================
# KARŞILAŞTIRMA: TEK HAT vs ÇİFT HAT
# ============================================================

class KarsilastirmaAnalizi:
    
    @staticmethod
    def tek_hat_simule(siparisler: List[Siparis]) -> dict:
        """Eski sistem: FIFO, tek hat, sıralı işleme"""
        print("\n" + "="*60)
        print("📊 SENARYO 1: TEK HAT (Eski Sistem - FIFO)")
        print("="*60)
        
        toplam_sure = 0
        toplam_gecikme = 0
        toplam_ceza = 0
        onceki_grup = None
        
        for s in siparisler:
            if s.renk not in RENK_VERITABANI:
                continue
                
            veri = RENK_VERITABANI[s.renk]
            
            # Tek hatta her renk geçişinde temizlik lazım!
            ek_temizlik = TEMIZLIK_MATRISI.get(
                (onceki_grup, veri["grup"]), 0)
            
            sure = veri["temizlik"] + ek_temizlik + veri["boyama"]
            gecikme = max(0, sure - s.teslim_suresi_dk)
            ceza = gecikme * s.gecikme_cezasi_tl
            
            toplam_sure += sure
            toplam_gecikme += gecikme
            toplam_ceza += ceza
            onceki_grup = veri["grup"]
            
            print(f"   {s.siparis_id}: {s.renk} | "
                  f"Süre:{sure}dk | Gecikme:{gecikme}dk | "
                  f"Ceza:{ceza:.0f}TL")
        
        print(f"\n   Toplam Gecikme: {toplam_gecikme} dk")
        print(f"   Toplam Ceza: {toplam_ceza:.0f} TL")
        
        return {
            "gecikme_dk": toplam_gecikme,
            "ceza_tl": toplam_ceza,
            "toplam_sure": toplam_sure
        }
    
    @staticmethod
    def kar_analizi(tek_hat: dict, cift_hat: dict):
        """Net kâr karşılaştırması"""
        print("\n" + "="*60)
        print("💰 KÂR / ZARAR ANALİZİ")
        print("="*60)
        
        # Varsayımlar (görsellerden)
        gelir_per_kg = 18          # TL/kg
        maliyet_per_kg = 11        # TL/kg
        gunluk_uretim_kg = 515     # kg
        ikinci_makine_maliyet = 45 # TL/gün
        
        # Tek hat
        tek_gelir = gunluk_uretim_kg * gelir_per_kg
        tek_maliyet = gunluk_uretim_kg * maliyet_per_kg
        tek_net = tek_gelir - tek_maliyet - tek_hat["ceza_tl"]
        
        # Çift hat (2x üretim kapasitesi)
        cift_uretim = gunluk_uretim_kg * 2
        cift_gelir = cift_uretim * gelir_per_kg
        cift_maliyet = cift_uretim * maliyet_per_kg
        cift_net = (cift_gelir - cift_maliyet - 
                    cift_hat["ceza_tl"] - ikinci_makine_maliyet)
        
        kar_artisi = cift_net - tek_net
        
        print(f"\n{'Parametre':<30} {'Tek Hat':>12} {'Çift Hat':>12}")
        print("-" * 55)
        print(f"{'Günlük Üretim (kg)':<30} "
              f"{gunluk_uretim_kg:>12} {cift_uretim:>12}")
        print(f"{'Gelir (TL)':<30} "
              f"{tek_gelir:>12.0f} {cift_gelir:>12.0f}")
        print(f"{'Maliyet (TL)':<30} "
              f"{tek_maliyet:>12.0f} {cift_maliyet:>12.0f}")
        print(f"{'Gecikme Cezası (TL)':<30} "
              f"{tek_hat['ceza_tl']:>12.0f} {cift_hat['ceza_tl']:>12.0f}")
        print(f"{'2. Makine Maliyeti':<30} "
              f"{'0':>12} {ikinci_makine_maliyet:>12}")
        print("-" * 55)
        print(f"{'NET KÂR (TL)':<30} "
              f"{tek_net:>12.0f} {cift_net:>12.0f}")
        
        print(f"\n🎯 Kâr Artışı: +{kar_artisi:.0f} TL/gün")
        print(f"🎯 Kâr Marjı: "
              f"Tek:%{(tek_net/tek_gelir*100):.0f} → "
              f"Çift:%{(cift_net/cift_gelir*100):.0f}")
        
        amortiman_gun = 45000 / kar_artisi  # 45.000 TL makine
        print(f"📅 Amortisman: ~{amortiman_gun:.0f} gün "
              f"({amortiman_gun/30:.1f} ay)")


# ============================================================
# ANA PROGRAM
# ============================================================

def main():
    print("\n" + "🏭"*30)
    print("PARALEL ÜRETİM SİSTEMİ - 2 MAKİNE")
    print("🏭"*30)
    
    # Test siparişleri (görsellerden alınan verilerle)
    siparisler = [
        Siparis("SIP-001", "Beyaz",     "ACIK", 160, 1, 45,  5.0),
        Siparis("SIP-002", "Kirmizi",   "KOYU", 100, 1, 75,  8.0),
        Siparis("SIP-003", "Siyah",     "KOYU",  70, 2, 350, 3.0),
        Siparis("SIP-004", "Pamuk",     "ACIK",  90, 1, 45,  6.0),
        Siparis("SIP-005", "Yesil",     "KOYU",  25, 2, 115, 4.0),
        Siparis("SIP-006", "Polyester", "ACIK",  45, 3, 50,  2.0),
        Siparis("SIP-007", "Lacivert",  "KOYU",  55, 1, 70,  7.0),
        Siparis("SIP-008", "Beyaz",     "ACIK",  80, 2, 45,  5.0),
    ]
    
    # ---- ÇİFT HAT SİSTEMİ ----
    sistem = ParalelUretimSistemi()
    
    print("\n📋 Siparişler sisteme yükleniyor...")
    for s in siparisler:
        sistem.siparis_siniflandir(s)
    
    # Paralel çalıştır
    cift_hat_sonuc = sistem.paralel_calistir()
    
    # ---- TEK HAT KARŞILAŞTIRMASI ----
    # Siparişleri sıfırla
    for s in siparisler:
        s.durum = "BEKLIYOR"
    
    tek_hat_sonuc = KarsilastirmaAnalizi.tek_hat_simule(siparisler)
    
    # ---- KÂR ANALİZİ ----
    KarsilastirmaAnalizi.kar_analizi(
        tek_hat_sonuc,
        {
            "ceza_tl": cift_hat_sonuc["toplam_ceza_tl"],
            "uretim_kg": cift_hat_sonuc["toplam_uretim_kg"]
        }
    )
    
    print("\n" + "✅"*30)
    print("SİSTEM TAMAMLANDI")
    print("✅"*30 + "\n")


if __name__ == "__main__":
    main()