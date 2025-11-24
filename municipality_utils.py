"""
Pomoćne funkcije za rad sa opštinama u Crnoj Gori.
Sadrži listu svih opština i validacione funkcije.
"""

# Lista svih opština u Crnoj Gori (alfabetski)
MUNICIPALITIES = [
    "Andrijevica",
    "Bar",
    "Berane",
    "Bijelo Polje",
    "Budva",
    "Cetinje",
    "Danilovgrad",
    "Gusinje",
    "Herceg Novi",
    "Kolašin",
    "Kotor",
    "Mojkovac",
    "Nikšić",
    "Petnjica",
    "Plav",
    "Pljevlja",
    "Plužine",
    "Podgorica",
    "Rožaje",
    "Šavnik",
    "Tivat",
    "Ulcinj",
    "Žabljak",
]

def validate_id_card_number(id_number):
    """
    Validira format broja lične karte.
    NAPOMENA: Ne ekstraktuje opštinu jer broj lične karte ne sadrži tu informaciju!
    
    Validni formati:
    - 9 cifara: 123456789
    - Sa crticama: 123456-789 ili 12-345678-9
    
    Args:
        id_number (str): Broj lične karte
        
    Returns:
        dict: {'valid': bool, 'clean_id': str, 'format': str, 'error': str}
    """
    # Ukloni razmake i crtice
    clean_id = id_number.replace("-", "").replace(" ", "").strip()
    
    result = {
        'valid': False,
        'clean_id': clean_id,
        'format': 'unknown',
        'error': None
    }
    
    # Proveri da li je prazan
    if not clean_id:
        result['error'] = "Broj lične karte ne može biti prazan"
        return result
    
    # Proveri dužinu
    if len(clean_id) < 6:
        result['error'] = "Broj lične karte je prekratak (minimum 6 cifara)"
        return result
    
    if len(clean_id) > 13:
        result['error'] = "Broj lične karte je predugačak (maximum 13 cifara)"
        return result
    
    # Proveri da li sadrži samo cifre
    if not clean_id.isdigit():
        result['error'] = "Broj lične karte mora sadržati samo cifre"
        return result
    
    # Broj je validan
    result['valid'] = True
    result['error'] = None
    
    # Odredi format
    if len(clean_id) == 9:
        result['format'] = 'standard_9digit'
    elif len(clean_id) == 13:
        result['format'] = 'jmbg_13digit'
    else:
        result['format'] = f'{len(clean_id)}_digit'
    
    return result

def get_all_municipalities():
    """
    Vraća listu svih opština u Crnoj Gori.
    
    Returns:
        list: Alfabetski sortirana lista opština
    """
    return MUNICIPALITIES.copy()

def validate_municipality(municipality):
    """
    Proverava da li je uneta opština validna.
    
    Args:
        municipality (str): Naziv opštine
        
    Returns:
        bool: True ako je validna, False ako nije
    """
    return municipality in MUNICIPALITIES

# Test funkcija
if __name__ == "__main__":
    test_cases = [
        "123456789",         # 9-cifarni format
        "1234567890123",     # 13-cifarni JMBG
        "12-345678-9",       # Sa crticama
        "abc123",            # Invalidan
        "",                  # Prazan
        "12345",             # Prekratak
    ]
    
    print("="*60)
    print("TEST VALIDACIJE LIČNE KARTE")
    print("="*60)
    
    for test_id in test_cases:
        result = validate_id_card_number(test_id)
        print(f"\nBroj: '{test_id}'")
        print(f"Valid: {result['valid']}")
        print(f"Očišćen: {result['clean_id']}")
        print(f"Format: {result['format']}")
        if result['error']:
            print(f"Greška: {result['error']}")
    
    print("\n" + "="*60)
    print("LISTA OPŠTINA:")
    print("="*60)
    for municipality in get_all_municipalities():
        print(f"  - {municipality}")
    print("="*60)
