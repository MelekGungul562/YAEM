import random
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from copy import deepcopy

# ============================================================
# PROBLEM PARAMETRELERİ - TEKSTİL ÖRNEK VERİSİ
# ============================================================

class TextileProblem:
    """
    Tekstil üretiminde sıra bağımlı hazırlık süreli çizelgeleme
    
    İşler: Farklı renk/kumaş türleri
    Makine: Boyama/dokuma makinesi
    Sıra bağımlı kurulum: Renk değişimi veya kumaş türü değişimi
    """
    
    def __init__(self):
        # İş isimleri (tekstil örneği)
        self.job_names = [
            "Beyaz Pamuk", "Kırmızı Pamuk", "Lacivert Pamuk",
            "Beyaz Polyester", "Sarı Polyester", "Siyah İpek",
            "Kırmızı İpek", "Yeşil Yün"
        ]
        self.n_jobs = len(self.job_names)
        
        # İşlem süreleri (dakika)
        self.processing_times = [45, 60, 55, 40, 50, 70, 65, 80]
        
        # Teslim tarihleri (dakika)
        self.due_dates = [200, 300, 250, 180, 280, 400, 350, 450]
        
        # Ağırlıklar (öncelik)
        self.weights = [3, 2, 2, 1, 2, 1, 3, 2]
        
        # Sıra bağımlı hazırlık süreleri matrisi (dakika)
        # setup[i][j] = i'den sonra j geldiğinde hazırlık süresi
        self.setup_times = self._generate_textile_setup_matrix()
        
    def _generate_textile_setup_matrix(self):
        """
        Tekstil gerçekçi kurulum matrisi:
        - Aynı renk grubu -> düşük kurulum
        - Farklı kumaş türü -> yüksek kurulum
        - Koyu renkten açığa geçiş -> çok yüksek kurulum
        """
        n = self.n_jobs
        # Temel matris
        setup = [
            # BeyazP  KırP  LacP  BeyazPoly  SarıPoly  Siyahİpek  Kırİpek  YeşilYün
            [0,   30,  35,  10,   25,   50,   45,   60],   # Beyaz Pamuk
            [45,   0,  15,  40,   20,   35,   10,   50],   # Kırmızı Pamuk
            [55,  20,   0,  50,   30,   25,   30,   45],   # Lacivert Pamuk
            [10,  35,  40,   0,   15,   55,   50,   65],   # Beyaz Polyester
            [30,  15,  25,  20,    0,   40,   20,   55],   # Sarı Polyester
            [60,  30,  20,  55,   35,    0,   15,   30],   # Siyah İpek
            [50,  10,  25,  45,   20,   20,    0,   40],   # Kırmızı İpek
            [65,  45,  35,  60,   50,   25,   35,    0],   # Yeşil Yün
        ]
        return setup
    
    def calculate_fitness(self, sequence):
        """
        Çizelge değerlendirme - Toplam ağırlıklı gecikme (TWT) hesaplama
        """
        current_time = 0
        total_weighted_tardiness = 0
        total_completion = 0
        
        for idx, job in enumerate(sequence):
            # Kurulum süresi ekle (ilk iş hariç)
            if idx > 0:
                prev_job = sequence[idx - 1]
                current_time += self.setup_times[prev_job][job]
            
            # İşlem süresini ekle
            current_time += self.processing_times[job]
            
            # Gecikme hesapla
            tardiness = max(0, current_time - self.due_dates[job])
            total_weighted_tardiness += self.weights[job] * tardiness
            total_completion += current_time
        
        return total_weighted_tardiness, total_completion
    
    def calculate_makespan(self, sequence):
        """Toplam span hesapla"""
        current_time = 0
        for idx, job in enumerate(sequence):
            if idx > 0:
                prev_job = sequence[idx - 1]
                current_time += self.setup_times[prev_job][job]
            current_time += self.processing_times[job]
        return current_time


# ============================================================
# GENETİK ALGORİTMA
# ============================================================

class GeneticAlgorithm:
    """
    Sıra bağımlı çizelgeleme için Genetik Algoritma
    
    Kromozom: İş sırası permütasyonu
    Fitness: Toplam ağırlıklı gecikme (minimize)
    """
    
    def __init__(self, problem, pop_size=100, max_gen=200, 
                 crossover_rate=0.85, mutation_rate=0.15,
                 elite_size=5, tournament_size=5):
        
        self.problem = problem
        self.pop_size = pop_size
        self.max_gen = max_gen
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size
        self.tournament_size = tournament_size
        
        self.n_jobs = problem.n_jobs
        self.best_solution = None
        self.best_fitness = float('inf')
        self.fitness_history = []
        self.avg_fitness_history = []
        
    # ----------------------------------------------------------
    # POPÜLASYON BAŞLATMA
    # ----------------------------------------------------------
    
    def initialize_population(self):
        """
        Karma başlangıç: Rastgele + Sezgisel (NEH benzeri)
        """
        population = []
        
        # %20 sezgisel çözüm
        heuristic_count = max(2, self.pop_size // 5)
        for _ in range(heuristic_count):
            chromosome = self._nearest_neighbor_heuristic()
            population.append(chromosome)
        
        # %80 rastgele
        while len(population) < self.pop_size:
            chromosome = list(range(self.n_jobs))
            random.shuffle(chromosome)
            population.append(chromosome)
        
        return population
    
    def _nearest_neighbor_heuristic(self):
        """
        En yakın komşu sezgiği:
        En kısa kurulum süreli işi seç
        """
        unscheduled = list(range(self.n_jobs))
        
        # Rastgele başlangıç işi
        start = random.choice(unscheduled)
        sequence = [start]
        unscheduled.remove(start)
        
        while unscheduled:
            last = sequence[-1]
            # Minimum kurulum + işlem süreli işi seç
            best_next = min(unscheduled, 
                          key=lambda j: self.problem.setup_times[last][j] + 
                                       self.problem.processing_times[j])
            sequence.append(best_next)
            unscheduled.remove(best_next)
        
        return sequence
    
    # ----------------------------------------------------------
    # FITNESS HESAPLAMA
    # ----------------------------------------------------------
    
    def evaluate_population(self, population):
        """Tüm popülasyonu değerlendir"""
        fitness_values = []
        for chromosome in population:
            twt, _ = self.problem.calculate_fitness(chromosome)
            fitness_values.append(twt)
        return fitness_values
    
    # ----------------------------------------------------------
    # SEÇİLİM - TURNUVA
    # ----------------------------------------------------------
    
    def tournament_selection(self, population, fitness_values):
        """Turnuva seçimi"""
        tournament_indices = random.sample(range(len(population)), 
                                          self.tournament_size)
        best_idx = min(tournament_indices, key=lambda i: fitness_values[i])
        return deepcopy(population[best_idx])
    
    # ----------------------------------------------------------
    # ÇAPRAZLAMA OPERATÖRLERİ
    # ----------------------------------------------------------
    
    def order_crossover_OX(self, parent1, parent2):
        """
        OX (Order Crossover) - Permütasyon için standart
        """
        n = len(parent1)
        child = [-1] * n
        
        # Kesim noktaları
        start, end = sorted(random.sample(range(n), 2))
        
        # Ebeveyn 1'den segment kopyala
        child[start:end+1] = parent1[start:end+1]
        
        # Ebeveyn 2'den kalan genleri doldur
        remaining = [gene for gene in parent2 if gene not in child]
        pos = 0
        for i in range(n):
            if child[i] == -1:
                child[i] = remaining[pos]
                pos += 1
        
        return child
    
    def pmx_crossover(self, parent1, parent2):
        """
        PMX (Partially Mapped Crossover)
        """
        n = len(parent1)
        child = [-1] * n
        
        start, end = sorted(random.sample(range(n), 2))
        
        # Segment kopyala
        child[start:end+1] = parent1[start:end+1]
        
        # Eşleme
        for i in range(start, end+1):
            if parent2[i] not in child:
                val = parent2[i]
                pos = i
                while child[pos] != -1:
                    pos = parent2.index(parent1[pos])
                child[pos] = val
        
        # Kalanları doldur
        for i in range(n):
            if child[i] == -1:
                child[i] = parent2[i]
        
        return child
    
    # ----------------------------------------------------------
    # MUTASYON OPERATÖRLERİ
    # ----------------------------------------------------------
    
    def swap_mutation(self, chromosome):
        """İki işi yer değiştir"""
        chrom = deepcopy(chromosome)
        i, j = random.sample(range(len(chrom)), 2)
        chrom[i], chrom[j] = chrom[j], chrom[i]
        return chrom
    
    def insertion_mutation(self, chromosome):
        """Bir işi farklı pozisyona yerleştir"""
        chrom = deepcopy(chromosome)
        i = random.randint(0, len(chrom)-1)
        j = random.randint(0, len(chrom)-1)
        gene = chrom.pop(i)
        chrom.insert(j, gene)
        return chrom
    
    def reverse_mutation(self, chromosome):
        """Segment tersine çevir (2-opt benzeri)"""
        chrom = deepcopy(chromosome)
        i, j = sorted(random.sample(range(len(chrom)), 2))
        chrom[i:j+1] = reversed(chrom[i:j+1])
        return chrom
    
    def apply_mutation(self, chromosome):
        """Rastgele mutasyon operatörü seç"""
        operators = [self.swap_mutation, 
                    self.insertion_mutation, 
                    self.reverse_mutation]
        op = random.choice(operators)
        return op(chromosome)
    
    # ----------------------------------------------------------
    # LOCAL SEARCH - 2-OPT
    # ----------------------------------------------------------
    
    def local_search_2opt(self, chromosome):
        """
        2-opt yerel arama: En iyi geliştirici hamle
        """
        best = deepcopy(chromosome)
        best_fit, _ = self.problem.calculate_fitness(best)
        improved = True
        
        while improved:
            improved = False
            for i in range(len(best) - 1):
                for j in range(i + 2, len(best)):
                    # Swap
                    new_chrom = deepcopy(best)
                    new_chrom[i], new_chrom[j] = new_chrom[j], new_chrom[i]
                    new_fit, _ = self.problem.calculate_fitness(new_chrom)
                    
                    if new_fit < best_fit:
                        best = new_chrom
                        best_fit = new_fit
                        improved = True
        
        return best
    
    # ----------------------------------------------------------
    # ANA GA DÖNGÜSÜ
    # ----------------------------------------------------------
    
    def run(self, verbose=True):
        """Genetik Algoritmayı çalıştır"""
        print("=" * 60)
        print("   TEKSTİL SDST ÇİZELGELEME - GENETİK ALGORİTMA")
        print("=" * 60)
        print(f"İş sayısı    : {self.n_jobs}")
        print(f"Popülasyon   : {self.pop_size}")
        print(f"Nesil sayısı : {self.max_gen}")
        print(f"Çaprazlama   : {self.crossover_rate}")
        print(f"Mutasyon     : {self.mutation_rate}")
        print("=" * 60)
        
        # Başlat
        population = self.initialize_population()
        fitness_values = self.evaluate_population(population)
        
        # En iyi bul
        best_idx = np.argmin(fitness_values)
        self.best_solution = deepcopy(population[best_idx])
        self.best_fitness = fitness_values[best_idx]
        
        # GA Döngüsü
        for gen in range(self.max_gen):
            new_population = []
            
            # ---- Elitizm ----
            sorted_indices = np.argsort(fitness_values)
            for i in range(self.elite_size):
                elite = deepcopy(population[sorted_indices[i]])
                new_population.append(elite)
            
            # ---- Yeni bireyler üret ----
            while len(new_population) < self.pop_size:
                # Seçim
                parent1 = self.tournament_selection(population, fitness_values)
                parent2 = self.tournament_selection(population, fitness_values)
                
                # Çaprazlama
                if random.random() < self.crossover_rate:
                    if random.random() < 0.5:
                        child = self.order_crossover_OX(parent1, parent2)
                    else:
                        child = self.pmx_crossover(parent1, parent2)
                else:
                    child = deepcopy(parent1)
                
                # Mutasyon
                if random.random() < self.mutation_rate:
                    child = self.apply_mutation(child)
                
                new_population.append(child)
            
            # Popülasyonu güncelle
            population = new_population
            fitness_values = self.evaluate_population(population)
            
            # En iyiyi güncelle
            gen_best_idx = np.argmin(fitness_values)
            gen_best_fit = fitness_values[gen_best_idx]
            
            if gen_best_fit < self.best_fitness:
                self.best_fitness = gen_best_fit
                self.best_solution = deepcopy(population[gen_best_idx])
            
            # İstatistikler
            self.fitness_history.append(self.best_fitness)
            self.avg_fitness_history.append(np.mean(fitness_values))
            
            # Ekrana yaz
            if verbose and (gen + 1) % 20 == 0:
                print(f"Nesil {gen+1:4d} | En İyi: {self.best_fitness:8.2f} | "
                      f"Ortalama: {np.mean(fitness_values):8.2f}")
        
        # ---- Son yerel arama ----
        print("\n[Yerel Arama Uygulanıyor...]")
        improved_solution = self.local_search_2opt(self.best_solution)
        improved_fitness, _ = self.problem.calculate_fitness(improved_solution)
        
        if improved_fitness < self.best_fitness:
            self.best_solution = improved_solution
            self.best_fitness = improved_fitness
            print(f"Yerel arama iyileştirdi: {improved_fitness:.2f}")
        
        return self.best_solution, self.best_fitness


# ============================================================
# SONUÇLARI GÖSTER
# ============================================================

def print_schedule(problem, solution):
    """Çizelgeyi detaylı göster"""
    print("\n" + "=" * 70)
    print("                     ÇİZELGELEME SONUCU")
    print("=" * 70)
    print(f"{'Sıra':^5} {'İş Adı':^20} {'Kurulum':^10} {'İşlem':^10} "
          f"{'Bitiş':^10} {'Son Tarih':^10} {'Gecikme':^10}")
    print("-" * 70)
    
    current_time = 0
    total_twt = 0
    
    for idx, job in enumerate(solution):
        setup = 0
        if idx > 0:
            prev_job = solution[idx - 1]
            setup = problem.setup_times[prev_job][job]
            current_time += setup
        
        current_time += problem.processing_times[job]
        due = problem.due_dates[job]
        tardiness = max(0, current_time - due)
        weighted_tard = problem.weights[job] * tardiness
        total_twt += weighted_tard
        
        status = "✓" if tardiness == 0 else "✗ GECİKME"
        
        print(f"{idx+1:^5} {problem.job_names[job]:^20} {setup:^10} "
              f"{problem.processing_times[job]:^10} {current_time:^10} "
              f"{due:^10} {tardiness:^10} {status}")
    
    print("-" * 70)
    print(f"TOPLAM AĞIRLIKLI GECİKME (TWT) : {total_twt:.2f}")
    print(f"MAKESPAN (Toplam Süre)          : {current_time} dakika")
    print(f"İş Sırası                       : {[problem.job_names[j] for j in solution]}")
    print("=" * 70)


def compare_with_random(problem, ga_solution, ga_fitness, n_trials=1000):
    """GA'yı rastgele çözümlerle karşılaştır"""
    print("\n[Rastgele Çözümlerle Karşılaştırma...]")
    
    random_fitnesses = []
    for _ in range(n_trials):
        random_seq = list(range(problem.n_jobs))
        random.shuffle(random_seq)
        twt, _ = problem.calculate_fitness(random_seq)
        random_fitnesses.append(twt)
    
    avg_random = np.mean(random_fitnesses)
    best_random = np.min(random_fitnesses)
    improvement = (avg_random - ga_fitness) / avg_random * 100
    
    print(f"\nRastgele Ortalama TWT : {avg_random:.2f}")
    print(f"Rastgele En İyi TWT   : {best_random:.2f}")
    print(f"GA Çözümü TWT         : {ga_fitness:.2f}")
    print(f"İyileştirme (Ort.)    : %{improvement:.1f}")
    
    return random_fitnesses


# ============================================================
# GORSELLEŞTİRME
# ============================================================

def visualize_results(problem, solution, ga, random_fitnesses):
    """Kapsamlı görselleştirme"""
    
    fig = plt.figure(figsize=(18, 14))
    fig.suptitle('Tekstil SDST Çizelgeleme - Genetik Algoritma Sonuçları', 
                 fontsize=16, fontweight='bold')
    
    colors = plt.cm.Set3(np.linspace(0, 1, problem.n_jobs))
    
    # ---- 1. Gantt Şeması ----
    ax1 = fig.add_subplot(3, 2, (1, 2))
    
    current_time = 0
    y_pos = 0.5
    
    for idx, job in enumerate(solution):
        setup = 0
        if idx > 0:
            prev_job = solution[idx - 1]
            setup = problem.setup_times[prev_job][job]
            # Kurulum bloğu
            ax1.barh(y_pos, setup, left=current_time, height=0.4,
                    color='lightgray', edgecolor='black', linewidth=0.5,
                    hatch='///')
            current_time += setup
        
        # İşlem bloğu
        proc = problem.processing_times[job]
        ax1.barh(y_pos, proc, left=current_time, height=0.4,
                color=colors[job], edgecolor='black', linewidth=0.8)
        
        # Etiket
        ax1.text(current_time + proc/2, y_pos, 
                f'İş{job+1}\n({proc}dk)', 
                ha='center', va='center', fontsize=8, fontweight='bold')
        
        # Due date işareti
        ax1.axvline(x=problem.due_dates[job], color='red', 
                   alpha=0.3, linestyle='--', linewidth=0.8)
        
        current_time += proc
    
    ax1.set_xlabel('Zaman (Dakika)', fontsize=12)
    ax1.set_title('Gantt Şeması (Gri: Kurulum | Renkli: İşlem)', fontsize=12)
    ax1.set_yticks([0.5])
    ax1.set_yticklabels(['Makine'])
    ax1.set_xlim(0, current_time * 1.05)
    
    setup_patch = mpatches.Patch(facecolor='lightgray', hatch='///', label='Kurulum Süresi')
    ax1.legend(handles=[setup_patch], loc='upper left')
    ax1.grid(axis='x', alpha=0.3)
    
    # ---- 2. Fitness Evrimi ----
    ax2 = fig.add_subplot(3, 2, 3)
    generations = range(1, len(ga.fitness_history) + 1)
    ax2.plot(generations, ga.fitness_history, 'b-', linewidth=2, label='En İyi TWT')
    ax2.plot(generations, ga.avg_fitness_history, 'r--', linewidth=1.5, 
             alpha=0.7, label='Ortalama TWT')
    ax2.fill_between(generations, ga.fitness_history, 
                    ga.avg_fitness_history, alpha=0.1, color='blue')
    ax2.set_xlabel('Nesil', fontsize=11)
    ax2.set_ylabel('TWT', fontsize=11)
    ax2.set_title('GA Fitness Evrimi', fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # ---- 3. Kurulum Matrisi Isı Haritası ----
    ax3 = fig.add_subplot(3, 2, 4)
    setup_array = np.array(problem.setup_times)
    im = ax3.imshow(setup_array, cmap='YlOrRd', aspect='auto')
    plt.colorbar(im, ax=ax3, label='Kurulum Süresi (dk)')
    
    short_names = [n.split()[0][:6] for n in problem.job_names]
    ax3.set_xticks(range(problem.n_jobs))
    ax3.set_yticks(range(problem.n_jobs))
    ax3.set_xticklabels(short_names, rotation=45, fontsize=8)
    ax3.set_yticklabels(short_names, fontsize=8)
    ax3.set_title('Sıra Bağımlı Kurulum Matrisi', fontsize=12)
    
    # Değerleri göster
    for i in range(problem.n_jobs):
        for j in range(problem.n_jobs):
            ax3.text(j, i, str(setup_array[i, j]), 
                    ha='center', va='center', fontsize=7, color='black')
    
    # ---- 4. GA vs Rastgele Karşılaştırma ----
    ax4 = fig.add_subplot(3, 2, 5)
    ax4.hist(random_fitnesses, bins=30, color='steelblue', 
             alpha=0.7, label='Rastgele Çözümler')
    ax4.axvline(x=ga.best_fitness, color='red', linewidth=3, 
               linestyle='-', label=f'GA Çözümü: {ga.best_fitness:.0f}')
    ax4.axvline(x=np.mean(random_fitnesses), color='orange', linewidth=2,
               linestyle='--', label=f'Rastgele Ort: {np.mean(random_fitnesses):.0f}')
    ax4.set_xlabel('TWT Değeri', fontsize=11)
    ax4.set_ylabel('Frekans', fontsize=11)
    ax4.set_title('GA vs Rastgele Çözüm Dağılımı', fontsize=12)
    ax4.legend(fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    # ---- 5. İş Bazlı Analiz ----
    ax5 = fig.add_subplot(3, 2, 6)
    
    current_time = 0
    completion_times = []
    tardiness_values = []
    
    for idx, job in enumerate(solution):
        if idx > 0:
            prev_job = solution[idx - 1]
            current_time += problem.setup_times[prev_job][job]
        current_time += problem.processing_times[job]
        completion_times.append(current_time)
        tardiness_values.append(max(0, current_time - problem.due_dates[job]))
    
    x = range(len(solution))
    job_labels = [f"İş{solution[i]+1}" for i in x]
    
    bars = ax5.bar(x, tardiness_values, color=['red' if t > 0 else 'green' 
                                                for t in tardiness_values])
    ax5.set_xticks(x)
    ax5.set_xticklabels(job_labels, rotation=45, fontsize=9)
    ax5.set_ylabel('Gecikme (Dakika)', fontsize=11)
    ax5.set_title('İş Bazlı Gecikme Analizi', fontsize=12)
    ax5.grid(axis='y', alpha=0.3)
    
    late_patch = mpatches.Patch(color='red', label='Gecikmeli')
    ontime_patch = mpatches.Patch(color='green', label='Zamanında')
    ax5.legend(handles=[late_patch, ontime_patch])
    
    plt.tight_layout()
    plt.savefig('tekstil_sdst_ga_sonuclari.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("\nGrafik 'tekstil_sdst_ga_sonuclari.png' olarak kaydedildi.")


# ============================================================
# ANA PROGRAM
# ============================================================

def main():
    # Tekrarlanabilirlik için seed
    random.seed(42)
    np.random.seed(42)
    
    # Problem oluştur
    problem = TextileProblem()
    
    print("\nTEKSTİL PROBLEMİ BİLGİLERİ:")
    print(f"İşler: {problem.job_names}")
    print(f"İşlem Süreleri: {problem.processing_times}")
    print(f"Teslim Tarihleri: {problem.due_dates}")
    
    # GA Parametreleri
    ga = GeneticAlgorithm(
        problem=problem,
        pop_size=100,        # Popülasyon boyutu
        max_gen=200,         # Nesil sayısı
        crossover_rate=0.85, # Çaprazlama oranı
        mutation_rate=0.15,  # Mutasyon oranı
        elite_size=5,        # Elit birey sayısı
        tournament_size=5    # Turnuva boyutu
    )
    
    # GA'yı çalıştır
    best_solution, best_fitness = ga.run(verbose=True)
    
    # Sonuçları göster
    print_schedule(problem, best_solution)
    
    # Karşılaştırma
    random_fitnesses = compare_with_random(problem, best_solution, best_fitness)
    
    # Görselleştir
    visualize_results(problem, best_solution, ga, random_fitnesses)
    
    return best_solution, best_fitness


if __name__ == "__main__":
    best_sol, best_fit = main()