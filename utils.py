import json
from pathlib import Path
import unicodedata
import re

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Hardkodirani podaci za MUP usluge
MUP_RULES = {
    "lična karta": {
        "alias": ["licna karta", "ličnu kartu", "ličnoj karti", "ID card"],
        "dokumenta": [
            "Izvod iz matične knjige rođenih (original ili ovjerena kopija)",
            "Uvjerenje o prebivalištu",
            "Stara lična karta (ako postoji)"
        ],
        "taksa_eur": 5.0,
        "uplata": "Žiro račun MUP CG: 832-12345-99; svrha uplate: 'Izrada lične karte'",
        "rok_izrade_dana": 7
    },
    "pasoš": {
        "alias": ["pasos", "pasoš", "putna isprava", "passport"],
        "dokumenta": ["Lična karta", "Uplatnica za pasoš"],
        "taksa_eur": 33.0,
        "uplata": "Žiro račun MUP CG: 832-12345-00; svrha uplate: 'Izdavanje pasoša'",
        "rok_izrade_dana": 10
    },
    "vozačka dozvola": {
        "alias": ["vozacka dozvola", "vozačku", "driver license", "vozačka"],
        "dokumenta": [
            "Lična karta",
            "Ljekarsko uvjerenje (važeće)",
            "Fotografija (biometrijski format)"
        ],
        "taksa_eur": 20.0,
        "uplata": "Žiro račun MUP CG: 832-12345-77; svrha uplate: 'Vozačka dozvola'",
        "rok_izrade_dana": 7
    },
    "promjena prebivališta": {
        "alias": ["promjena prebivalista", "prijava prebivalista", "odjava prebivalista", "prijava adrese", "promjena adrese", "prebivaliste", "prebivalište"],
        "dokumenta": [
            "Lična karta",
            "Dokaz o vlasništvu stana/kuće (izvod iz lista nepokretnosti ili ugovor o kupoprodaji)",
            "Ugovor o zakupu (ako ste zakupac)",
            "Saglasnost vlasnika stana (ako niste vlasnik)"
        ],
        "taksa_eur": 0.0,
        "uplata": "Bez takse - usluga je besplatna",
        "rok_izrade_dana": 1
    }
}

# Hardkodirani podaci za MUP centre
MUP_CENTERS = [
    {
        "naziv": "MUP Podgorica – Bulevar Svetog Petra Cetinjskog 92",
        "grad": "Podgorica",
        "lat": 42.4415,
        "lon": 19.2621,
        "radno_vrijeme": "08:00–15:00"
    },
    {
        "naziv": "MUP Nikšić – Trg Slobode bb",
        "grad": "Nikšić",
        "lat": 42.7731,
        "lon": 18.9447,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Bijelo Polje – Ulica Slobode bb",
        "grad": "Bijelo Polje",
        "lat": 43.0356,
        "lon": 19.7473,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Berane – Ulica Maksima Gorkog bb",
        "grad": "Berane",
        "lat": 42.8456,
        "lon": 19.8727,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Pljevlja – Ulica Kralja Petra I Karađorđevića bb",
        "grad": "Pljevlja",
        "lat": 43.3567,
        "lon": 19.3581,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Bar – Ulica Jovana Tomaševića bb",
        "grad": "Bar",
        "lat": 42.0973,
        "lon": 19.0886,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Budva – Ulica Mediteranska bb",
        "grad": "Budva",
        "lat": 42.2864,
        "lon": 18.8408,
        "radno_vrijeme": "08:00–15:00"
    },
    {
        "naziv": "MUP Herceg Novi – Ulica Njegoševa bb",
        "grad": "Herceg Novi",
        "lat": 42.4531,
        "lon": 18.5378,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Kotor – Stari grad bb",
        "grad": "Kotor",
        "lat": 42.4248,
        "lon": 18.7712,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Ulcinj – Ulica 26. Novembar bb",
        "grad": "Ulcinj",
        "lat": 41.9297,
        "lon": 19.2122,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Cetinje – Ulica Bajova bb",
        "grad": "Cetinje",
        "lat": 42.3931,
        "lon": 18.9238,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Danilovgrad – Ulica Nikole Tesle 14",
        "grad": "Danilovgrad",
        "lat": 42.5534,
        "lon": 19.1104,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Kolašin – Ulica Mojkovačka bb",
        "grad": "Kolašin",
        "lat": 42.8227,
        "lon": 19.5180,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Žabljak – Ulica Njegoševa bb",
        "grad": "Žabljak",
        "lat": 43.1556,
        "lon": 19.1231,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Plav – Ulica Sandžačka bb",
        "grad": "Plav",
        "lat": 42.5989,
        "lon": 19.9403,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Rožaje – Ulica Maršala Tita bb",
        "grad": "Rožaje",
        "lat": 42.8405,
        "lon": 20.1663,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Mojkovac – Ulica Ratnih Vojnih Invalida bb",
        "grad": "Mojkovac",
        "lat": 42.9604,
        "lon": 19.5828,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Tivat – Ulica Palih Boraca bb",
        "grad": "Tivat",
        "lat": 42.4304,
        "lon": 18.6948,
        "radno_vrijeme": "08:00–14:30"
    },
    {
        "naziv": "MUP Plužine – Centar bb",
        "grad": "Plužine",
        "lat": 43.1508,
        "lon": 18.8453,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Šavnik – Centar bb",
        "grad": "Šavnik",
        "lat": 42.9575,
        "lon": 19.0938,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Andrijevica – Ulica Trg Revolucije bb",
        "grad": "Andrijevica",
        "lat": 42.7357,
        "lon": 19.7856,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Gusinje – Ulica Djalovića Brdo bb",
        "grad": "Gusinje",
        "lat": 42.5561,
        "lon": 19.8311,
        "radno_vrijeme": "08:00–14:00"
    },
    {
        "naziv": "MUP Petnjica – Centar bb",
        "grad": "Petnjica",
        "lat": 42.9356,
        "lon": 20.0167,
        "radno_vrijeme": "08:00–14:00"
    }
]

# -- Akcent-insenzitivna normalizacija (šđčćž -> s d c c z), mala slova, 1 razmak
_MAP = str.maketrans({
    "š":"s","Š":"s","đ":"d","Đ":"d","č":"c","Č":"c","ć":"c","Ć":"c","ž":"z","Ž":"z"
})

def normalize_text(s: str) -> str:
    if not s:
        return ""
    # prvo transliteracija specifičnih slova, onda skidanje diakritika iz ostatka
    s = s.translate(_MAP)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def load_rules(path=None):
    """Vraća hardkodirane MUP pravila - path parametar se ignoriše"""
    return MUP_RULES

def load_centers(path=None, city=None):
    """
    Vraća hardkodirane MUP centre - path parametar se ignoriše.
    Ako je city proslijeđen, vraća samo centre iz tog grada.
    """
    if city:
        return [c for c in MUP_CENTERS if c["grad"].lower() == city.lower()]
    return MUP_CENTERS

def get_all_cities():
    """Vraća listu svih gradova koji imaju MUP centre"""
    cities = sorted(list(set(c["grad"] for c in MUP_CENTERS)))
    return cities

def detect_service(query: str, rules: dict):
    """Vraća ključ usluge (npr. 'lična karta') radeći akcent-insenzitivno poređenje."""
    nq = normalize_text(query)
    best = None
    best_len = 0

    for name, info in rules.items():
        nname = normalize_text(name)
        aliases = [normalize_text(a) for a in info.get("alias", [])] + [nname]
        # direktno 'contains' nad normalizovanim pojmovima
        for token in aliases:
            if token and token in nq:
                # biraj najduži pogodak (specifičniji)
                if len(token) > best_len:
                    best = name
                    best_len = len(token)
    return best

def google_maps_link(lat, lon, label='MUP centar'):
    return f"https://www.google.com/maps?q={lat},{lon}({label})"
