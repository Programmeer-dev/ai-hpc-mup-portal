import random, math
from datetime import datetime, timedelta

def estimate_wait_minutes(arrival_rate_per_hour=18, service_rate_per_hour=20, current_queue=12):
    """Simple M/M/1-like approximation with finite queue.
    Returns an estimated wait time in minutes.
    """
    lam = arrival_rate_per_hour / 60.0
    mu = service_rate_per_hour / 60.0
    rho = lam / mu if mu > 0 else 0.95
    rho = min(max(rho, 0.1), 0.95)
    # Expected wait ~ current_queue / (mu - lam)
    denom = max(mu - lam, 0.05)
    base = current_queue / denom
    noise = random.uniform(-0.2, 0.2) * base
    est_minutes = max(3, int(base + noise))
    return est_minutes

def next_best_slot(now=None, est_minutes=30):
    if now is None:
        now = datetime.now()
    start = now + timedelta(minutes=est_minutes)
    # Round to next 10-minute slot
    rounded = start + timedelta(minutes=(10 - start.minute % 10)) if start.minute % 10 != 0 else start
    return rounded.replace(second=0, microsecond=0)

def parse_working_hours(working_hours):
    """Parsiraj string '08:00–15:00' u datetime.time objekte"""
    try:
        start_str, end_str = working_hours.replace("–", "-").split("-")
        start = datetime.strptime(start_str.strip(), "%H:%M").time()
        end = datetime.strptime(end_str.strip(), "%H:%M").time()
        return start, end
    except:
        return datetime.strptime("08:00", "%H:%M").time(), datetime.strptime("15:00", "%H:%M").time()

def next_best_slot_with_hours(now, est_minutes, center_hours):
    """Vraća naredni termin dolaska unutar radnog vremena centra"""
    slot = now + timedelta(minutes=est_minutes)
    start, end = parse_working_hours(center_hours)

    # Ako slot pada van radnog vremena, pomjeri na sledeći dan ujutro
    if slot.time() > end or slot.time() < start:
        next_day = (slot + timedelta(days=1)).replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
        return next_day
    return slot

