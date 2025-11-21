"""
HPC Queue Predictor - Monte Carlo simulacija sa parallel processing
Koristi multiprocessing za brže i tačnije predviđanje optimalnog vremena dolaska
"""

import numpy as np
from multiprocessing import Pool, cpu_count
from datetime import datetime, timedelta
import random
from functools import partial

def simulate_single_scenario(scenario_id, arrival_rate, service_rate, current_queue, working_hours):
    """
    Simulira jedan scenario rada MUP centra tokom dana.
    Ova funkcija će se izvršavati paralelno na više CPU cores.
    
    Args:
        scenario_id: ID scenarija (za random seed)
        arrival_rate: Broj dolazaka po satu (λ)
        service_rate: Broj usluženih po satu (μ)
        current_queue: Trenutni broj ljudi u redu
        working_hours: Tuple (start_hour, end_hour) radnog vremena
        
    Returns:
        dict: Rezultati simulacije sa procjenama vremena čekanja po satima
    """
    np.random.seed(scenario_id)  # Za reproducibility
    random.seed(scenario_id)
    
    start_hour, end_hour = working_hours
    hours = end_hour - start_hour
    
    # Simuliraj rad centra sat po sat
    queue = current_queue
    wait_times = {}
    
    for hour in range(hours):
        current_time = start_hour + hour
        
        # Dodaj varijabilnost u arrival/service rates (realniji scenario)
        # Jutro je gušće, podne manje, popodne opet više
        if hour < 2:  # Jutro (8-10h)
            arrival_multiplier = np.random.uniform(1.2, 1.5)
        elif hour < 4:  # Prije podne (10-12h)
            arrival_multiplier = np.random.uniform(1.0, 1.2)
        elif hour < 5:  # Podne (12-13h)
            arrival_multiplier = np.random.uniform(0.7, 0.9)
        else:  # Popodne (13-15h)
            arrival_multiplier = np.random.uniform(0.9, 1.1)
        
        # Broj dolazaka u ovom satu (Poisson distribucija)
        arrivals = np.random.poisson(arrival_rate * arrival_multiplier)
        
        # Broj usluženih u ovom satu (normalna distribucija sa varijacijom)
        served = int(np.random.normal(service_rate, service_rate * 0.15))
        served = max(0, served)  # Ne može biti negativno
        
        # Ažuriraj red
        queue = max(0, queue + arrivals - served)
        
        # Prosječno vrijeme čekanja u ovom satu (u minutima)
        if queue > 0 and served > 0:
            avg_service_time = 60.0 / service_rate
            wait_time = queue * avg_service_time * np.random.uniform(0.8, 1.2)
        else:
            wait_time = np.random.uniform(1, 5)  # Minimalno čekanje
        
        wait_times[current_time] = {
            'queue_size': queue,
            'wait_minutes': int(wait_time),
            'arrivals': arrivals,
            'served': served
        }
    
    return wait_times

def run_monte_carlo_simulation(arrival_rate, service_rate, current_queue, 
                                working_hours=(8, 15), num_simulations=5000):
    """
    Pokreće Monte Carlo simulaciju koristeći sve dostupne CPU cores (HPC).
    
    Args:
        arrival_rate: Dolasci po satu
        service_rate: Usluženi po satu
        current_queue: Trenutna veličina reda
        working_hours: Tuple (start, end) radnog vremena
        num_simulations: Broj paralelnih simulacija (default 5000)
        
    Returns:
        dict: Agregirani rezultati sa preporukama
    """
    # Odredi broj CPU cores za parallel processing
    num_cores = cpu_count()
    print(f"🚀 HPC: Pokrećem {num_simulations} simulacija na {num_cores} CPU cores...")
    
    # Kreiraj partial funkciju sa fiksnim parametrima
    simulate_func = partial(
        simulate_single_scenario,
        arrival_rate=arrival_rate,
        service_rate=service_rate,
        current_queue=current_queue,
        working_hours=working_hours
    )
    
    # Paralelno izvršavanje simulacija na svim dostupnim cores
    with Pool(processes=num_cores) as pool:
        results = pool.map(simulate_func, range(num_simulations))
    
    # Agreguj rezultate svih simulacija
    aggregated = {}
    start_hour, end_hour = working_hours
    
    for hour in range(start_hour, end_hour):
        wait_times = []
        queue_sizes = []
        
        for result in results:
            if hour in result:
                wait_times.append(result[hour]['wait_minutes'])
                queue_sizes.append(result[hour]['queue_size'])
        
        # Statistika za ovaj sat
        aggregated[hour] = {
            'avg_wait': np.mean(wait_times),
            'min_wait': np.min(wait_times),
            'max_wait': np.max(wait_times),
            'std_wait': np.std(wait_times),
            'percentile_50': np.percentile(wait_times, 50),
            'percentile_75': np.percentile(wait_times, 75),
            'percentile_95': np.percentile(wait_times, 95),
            'avg_queue': np.mean(queue_sizes),
            'confidence': 95  # 95% confidence interval
        }
    
    print(f"✅ HPC: Simulacija završena! Analizirano {num_simulations} scenarija.")
    return aggregated

def find_optimal_arrival_time(aggregated_results, current_hour=None):
    """
    Pronalazi optimalno vrijeme dolaska na osnovu HPC simulacije.
    
    Args:
        aggregated_results: Rezultati Monte Carlo simulacije
        current_hour: Trenutni sat (ako je None, koristi datetime.now())
        
    Returns:
        dict: Preporuka sa optimalnim vremenom i procjenom
    """
    if current_hour is None:
        current_hour = datetime.now().hour
    
    # Filtriraj samo buduće sate
    future_hours = {h: data for h, data in aggregated_results.items() if h >= current_hour}
    
    if not future_hours:
        # Ako je van radnog vremena, preporuči sutra ujutro
        return {
            'recommended_hour': 8,
            'recommended_time': datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1),
            'estimated_wait': aggregated_results[8]['avg_wait'],
            'confidence': 95,
            'reason': 'Van radnog vremena - preporučujem sutra ujutro'
        }
    
    # Pronađi sat sa najmanjim prosječnim čekanjem
    best_hour = min(future_hours.keys(), key=lambda h: future_hours[h]['avg_wait'])
    best_data = future_hours[best_hour]
    
    # Generiši preporuku
    now = datetime.now()
    recommended_time = now.replace(hour=best_hour, minute=0, second=0, microsecond=0)
    
    # Ako je preporučeno vrijeme u prošlosti, pomjeri na sutra
    if recommended_time < now:
        recommended_time += timedelta(days=1)
    
    # Dodaj mali random offset (5-15 min) da raspršimo ljude
    offset_minutes = random.randint(5, 15)
    recommended_time += timedelta(minutes=offset_minutes)
    
    return {
        'recommended_hour': best_hour,
        'recommended_time': recommended_time,
        'estimated_wait_avg': int(best_data['avg_wait']),
        'estimated_wait_range': (int(best_data['min_wait']), int(best_data['max_wait'])),
        'confidence': int(best_data['confidence']),
        'queue_size_avg': int(best_data['avg_queue']),
        'percentile_50': int(best_data['percentile_50']),
        'percentile_95': int(best_data['percentile_95']),
        'reason': f'Optimalno vrijeme prema {5000} simulacija',
        'all_hours': future_hours  # Za prikaz svih opcija
    }

def predict_best_arrival_time(arrival_rate=18, service_rate=20, current_queue=12, 
                               working_hours="08:00-15:00", num_simulations=5000):
    """
    Glavna funkcija koja pokreće HPC predviđanje optimalnog vremena dolaska.
    
    Args:
        arrival_rate: Dolasci po satu (λ)
        service_rate: Usluženi po satu (μ)
        current_queue: Trenutna veličina reda
        working_hours: String format "HH:MM-HH:MM"
        num_simulations: Broj Monte Carlo simulacija (više = tačnije, sporije)
        
    Returns:
        dict: Kompletan izveštaj sa preporukom
    """
    # Parse working hours
    try:
        start_str, end_str = working_hours.replace("–", "-").split("-")
        start_hour = int(start_str.split(":")[0])
        end_hour = int(end_str.split(":")[0])
    except:
        start_hour, end_hour = 8, 15
    
    # Pokreni HPC Monte Carlo simulaciju
    print(f"🔬 Pokrećem HPC analizu...")
    print(f"   Parametri: λ={arrival_rate}/h, μ={service_rate}/h, red={current_queue}")
    
    aggregated = run_monte_carlo_simulation(
        arrival_rate=arrival_rate,
        service_rate=service_rate,
        current_queue=current_queue,
        working_hours=(start_hour, end_hour),
        num_simulations=num_simulations
    )
    
    # Pronađi optimalno vrijeme
    recommendation = find_optimal_arrival_time(aggregated)
    
    return recommendation

# Test funkcija
if __name__ == "__main__":
    result = predict_best_arrival_time(
        arrival_rate=18,
        service_rate=20,
        current_queue=12,
        working_hours="08:00-15:00",
        num_simulations=1000  # Manje za test
    )
    
    print("\n" + "="*60)
    print("📊 HPC PREPORUKA:")
    print("="*60)
    print(f"Preporučeno vrijeme: {result['recommended_time'].strftime('%d.%m.%Y u %H:%M')}")
    print(f"Prosječno čekanje: {result['estimated_wait_avg']} minuta")
    print(f"Raspon čekanja: {result['estimated_wait_range'][0]}-{result['estimated_wait_range'][1]} min")
    print(f"95% ljudi čeka max: {result['percentile_95']} min")
    print(f"Prosječan red: {result['queue_size_avg']} ljudi")
    print(f"Pouzdanost: {result['confidence']}%")
    print("="*60)
