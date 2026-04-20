import random
import math
import time
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Sequence, Tuple

# ============================================================
# 1. VERİ YAPISI
# ============================================================

@dataclass(frozen=True)
class TextileProblem:
    job_names: Sequence[str]
    processing_times: Sequence[int]
    due_dates: Sequence[int]
    weights: Sequence[int]
    setup_times: Sequence[Sequence[int]]

    @property
    def n_jobs(self) -> int:
        return len(self.job_names)

    def calculate_fitness(self, sequence: Sequence[int]) -> Tuple[float, int]:
        current_time = 0
        total_tardiness = 0.0
        for idx, job in enumerate(sequence):
            if idx > 0:
                current_time += self.setup_times[sequence[idx-1]][job]
            current_time += self.processing_times[job]
            tardiness = max(0, current_time - self.due_dates[job])
            total_tardiness += self.weights[job] * tardiness
        return total_tardiness, current_time

def get_problem():
    return TextileProblem(
        job_names=["Beyaz Pamuk", "Kırmızı Pamuk", "Lacivert Pamuk", "Beyaz Polyester", 
                   "Sarı Polyester", "Siyah İpek", "Kırmızı İpek", "Yeşil Yün"],
        processing_times=[45, 60, 55, 40, 50, 70, 65, 80],
        due_dates=[200, 300, 250, 180, 280, 400, 350, 450],
        weights=[3, 2, 2, 1, 2, 1, 3, 2],
        setup_times=[
            [0, 30, 35, 10, 25, 50, 45, 60], [45, 0, 15, 40, 20, 35, 10, 50],
            [55, 20, 0, 50, 30, 25, 30, 45], [10, 35, 40, 0, 15, 55, 50, 65],
            [30, 15, 25, 20, 0, 40, 20, 55], [60, 30, 20, 55, 35, 0, 15, 30],
            [50, 10, 25, 45, 20, 20, 0, 40], [65, 45, 35, 60, 50, 25, 35, 0]
        ]
    )

# ============================================================
# 2. SİMÜLASYON TAVLAMA (SA) - BASITLEŞTIRILMIŞ
# ============================================================

class SimulatedAnnealing:
    def __init__(self, problem: TextileProblem):
        self.problem = problem
        # Parametreler: Sabit ayarlar, garanti çalışır
        self.max_iterations = 10000  # Toplam deneme sayısı (SABİT)
        self.initial_temp = 5000.0
        
    def _get_neighbor(self, seq: List[int]) -> List[int]:
        # Rastgele bir hareket: Swap (yer değiştir) veya Insert (yerinden alıp koy)
        new_seq = seq[:]
        if random.random() < 0.5:
            # Swap
            i, j = random.sample(range(len(seq)), 2)
            new_seq[i], new_seq[j] = new_seq[j], new_seq[i]
        else:
            # Insert
            i = random.randint(0, len(seq)-1)
            j = random.randint(0, len(seq)-1)
            val = new_seq.pop(i)
            new_seq.insert(j, val)
        return new_seq

    def run(self):
        print("-" * 40)
        print("Algoritma Başlıyor... (Toplam 10.000 adım)")
        print("-" * 40)
        
        # Başlangıç
        current_sol = list(range(self.problem.n_jobs))
        random.shuffle(current_sol)
        current_fit, _ = self.problem.calculate_fitness(current_sol)
        
        best_sol = current_sol[:]
        best_fit = current_fit
        
        temp = self.initial_temp
        
        # ANA DÖNGÜ (FOR DÖNGÜSÜ - SONSUZ DÖNGÜ RİSKİ YOK)
        for i in range(self.max_iterations):
            # Soğutma
            temp *= 0.995
            
            # Komşu üret
            neighbor = self._get_neighbor(current_sol)
            neighbor_fit, _ = self.problem.calculate_fitness(neighbor)
            
            # Kabul et
            delta = neighbor_fit - current_fit
            if delta < 0 or random.random() < math.exp(-delta / max(temp, 0.01)):
                current_sol = neighbor
                current_fit = neighbor_fit
            
            # En iyiyi güncelle
            if current_fit < best_fit:
                best_fit = current_fit
                best_sol = current_sol[:]
            
            # Ekrana yazdırma (Sadece 5-6 satır olsun diye her 2000 adımda bir basıyoruz)
            if (i + 1) % 2000 == 0:
                print(f"Adım {i+1:5d} | Sıcaklık: {temp:7.1f} | En İyi Ceza: {best_fit:.0f}")

        print("-" * 40)
        print(f"Tamamlandı! En Düşük Ceza: {best_fit:.0f}")
        return best_sol, best_fit

# ============================================================
# 3. GÖRSELLİK VE ANA PROGRAM
# ============================================================

def show_results(problem, solution, score):
    # Tablo Başlığı
    print("\n" + "="*70)
    print(f"{'SIRA':<6}{'İŞ ADI':<20}{'KURULUM':<10}{'BİTİŞ':<10}{'SON TARİH':<12}{'DURUM':<10}")
    print("-" * 70)
    
    time = 0
    for idx, job in enumerate(solution):
        setup = problem.setup_times[solution[idx-1]][job] if idx > 0 else 0
        time += setup + problem.processing_times[job]
        due = problem.due_dates[job]
        late = time - due
        status = "GECİKTİ!" if late > 0 else "ZAMANINDA"
        print(f"{idx+1:<6}{problem.job_names[job]:<20}{setup:<10}{time:<10}{due:<12}{status:<10}")
    
    print("=" * 70)
    print(f"TOPLAM AĞIRLIKLI GECİKME: {score:.0f}")
    print("=" * 70)

    # Grafik
    plt.figure(figsize=(12, 5))
    
    # Gantt Şeması
    colors = plt.cm.get_cmap("Set3", problem.n_jobs)
    time = 0
    for idx, job in enumerate(solution):
        setup = problem.setup_times[solution[idx-1]][job] if idx > 0 else 0
        # Kurulum çubuğu (Gri)
        if setup > 0:
            plt.barh(0, setup, left=time, color='lightgray', edgecolor='black', height=0.4)
            time += setup
        # İşlem çubuğu (Renkli)
        proc = problem.processing_times[job]
        plt.barh(0, proc, left=time, color=colors(job), edgecolor='black', height=0.4)
        plt.text(time + proc/2, 0, str(job+1), ha='center', va='center', fontsize=9, fontweight='bold')
        time += proc

    plt.yticks([])
    plt.xlabel("Zaman (Dakika)")
    plt.title("En İyi Üretim Çizelgesi (Gantt)")
    plt.grid(axis='x', alpha=0.5)
    plt.tight_layout()
    plt.show()

# ============================================================
# 4. ÇALIŞTIR
# ============================================================

# Sabit tohum (her çalıştırmada aynı sonucu verir)
random.seed(42)

# Problemi ve Algoritmayı başlat
prob = get_problem()
sa = SimulatedAnnealing(prob)

# Çalıştır
sol, fit = sa.run()

# Sonuçları göster
show_results(prob, sol, fit)