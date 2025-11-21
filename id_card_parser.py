"""
Parser za crnogorsku ličnu kartu - automatski detektuje opštinu iz broja lične karte
"""

# Mapiranje koda opštine na naziv grada (prema crnogorskom sistemu)
MUNICIPALITY_CODES = {
    "01": "Andrijevica",
    "02": "Bar",
    "03": "Berane",
    "04": "Bijelo Polje",
    "05": "Budva",
    "06": "Cetinje",
    "07": "Danilovgrad",
    "08": "Herceg Novi",
    "09": "Kolašin",
    "10": "Kotor",
    "11": "Mojkovac",
    "12": "Nikšić",
    "13": "Plav",
    "14": "Pljevlja",
    "15": "Plužine",
    "16": "Podgorica",
    "17": "Rožaje",
    "18": "Šavnik",
    "19": "Tivat",
    "20": "Ulcinj",
    "21": "Žabljak",
    "22": "Gusinje",
    "23": "Petnjica",
}

def parse_id_card_number(id_number):
    """
    Parsira broj lične karte i izvlači opštinu.
    
    Format crnogorske lične karte je obično: DDMMYY-RRRRR-XX
    ili novi format: 9 cifara gdje prve 2 cifre mogu biti kod opštine
    
    Args:
        id_number (str): Broj lične karte
        
    Returns:
        dict: {'valid': bool, 'municipality': str, 'municipality_code': str, 'format': str}
    """
    # Ukloni razmake i crtice
    clean_id = id_number.replace("-", "").replace(" ", "").strip()
    
    result = {
        'valid': False,
        'municipality': None,
        'municipality_code': None,
        'format': 'unknown',
        'error': None
    }
    
    # Proveri dužinu
    if len(clean_id) < 6:
        result['error'] = "Broj lične karte je prekratak"
        return result
    
    # Pokušaj različite formate
    
    # Format 1: Novi format - 9 cifara, opština možda u poziciji 5-6 ili na drugom mjestu
    if clean_id.isdigit() and len(clean_id) == 9:
        # Pokušaj ekstraktovati kod opštine iz različitih pozicija
        possible_codes = [
            clean_id[0:2],   # Početak
            clean_id[5:7],   # Sredina
            clean_id[7:9],   # Kraj
        ]
        
        for code in possible_codes:
            if code in MUNICIPALITY_CODES:
                result['valid'] = True
                result['municipality'] = MUNICIPALITY_CODES[code]
                result['municipality_code'] = code
                result['format'] = 'new_9digit'
                return result
    
    # Format 2: Stariji format sa datumom - DDMMYY na početku
    if len(clean_id) >= 11:
        # Pokušaj kod opštine nakon datuma (pozicija 6-7)
        if clean_id[6:8] in MUNICIPALITY_CODES:
            result['valid'] = True
            result['municipality'] = MUNICIPALITY_CODES[clean_id[6:8]]
            result['municipality_code'] = clean_id[6:8]
            result['format'] = 'old_ddmmyy'
            return result
    
    # Format 3: Bilo koji format - traži 2 uzastopne cifre koje su kod opštine
    for i in range(len(clean_id) - 1):
        code = clean_id[i:i+2]
        if code in MUNICIPALITY_CODES:
            result['valid'] = True
            result['municipality'] = MUNICIPALITY_CODES[code]
            result['municipality_code'] = code
            result['format'] = 'detected'
            return result
    
    result['error'] = "Nije pronađen validan kod opštine u broju lične karte"
    return result

def get_municipality_from_id(id_number):
    """
    Brzo vraća samo naziv opštine iz broja lične karte.
    
    Args:
        id_number (str): Broj lične karte
        
    Returns:
        str or None: Naziv opštine ili None ako nije pronađeno
    """
    result = parse_id_card_number(id_number)
    return result['municipality'] if result['valid'] else None

# Test funkcija
if __name__ == "__main__":
    test_cases = [
        "010203-12345-16",  # Podgorica (16)
        "123456789",         # 9-cifarni format
        "25031990-16023",    # Stari format sa Podgoricom
        "12345678902",       # Test sa Bar (02)
    ]
    
    print("="*60)
    print("TEST PARSIRANJA LIČNE KARTE")
    print("="*60)
    
    for test_id in test_cases:
        result = parse_id_card_number(test_id)
        print(f"\nBroj: {test_id}")
        print(f"Valid: {result['valid']}")
        if result['valid']:
            print(f"Opština: {result['municipality']} (kod: {result['municipality_code']})")
            print(f"Format: {result['format']}")
        else:
            print(f"Greška: {result['error']}")
    
    print("\n" + "="*60)
