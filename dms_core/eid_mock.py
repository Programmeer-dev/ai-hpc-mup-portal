"""Mock eID provider za diplomski rad.

Simulira flow kakav bi imao CG eID / kvalifikovani sertifikat:
  1. Korisnik odabere sertifikat iz "čitača"
  2. Sistem dobije payload (JMBG, ime, prezime, email)
  3. Sistem auto-loginuje (ili kreira nalog) bez lozinke

Demo sertifikati su učitani iz `data/eid_certificates.json` ako postoji,
inače se koristi ugrađena lista.

OVAJ MODUL NIJE ZA PRODUKCIJU. Sve "sertifikate" generišemo na osnovu
unaprijed definisanih demo identiteta.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
CERT_FILE = BASE_DIR / "data" / "eid_certificates.json"


_DEFAULT_CERTIFICATES: List[Dict[str, str]] = [
    {
        "subject_name": "Marko Petrović",
        "username": "marko_petrovic",
        "email": "marko.petrovic@example.me",
        "city": "Podgorica",
        "id_card_number": "0101990123456",
    },
    {
        "subject_name": "Jelena Knežević",
        "username": "jelena_knezevic",
        "email": "jelena.knezevic@example.me",
        "city": "Bar",
        "id_card_number": "1505995765432",
    },
    {
        "subject_name": "Stefan Vukotić (službenik)",
        "username": "stefan_officer",
        "email": "stefan.vukotic@mup.gov.me",
        "city": "Podgorica",
        "id_card_number": "2003985112233",
        "role": "officer",
    },
]


def list_demo_certificates() -> List[Dict[str, str]]:
    """Vraća listu dostupnih demo sertifikata."""
    if CERT_FILE.exists():
        try:
            with open(CERT_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return _DEFAULT_CERTIFICATES


def issue_session_token(cert: Dict[str, str]) -> str:
    """Simulira potpis na zahtjev — vraća mock session token (hex)."""
    nonce = secrets.token_hex(8)
    serialized = json.dumps(cert, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256((nonce + serialized).encode("utf-8")).hexdigest()
    return digest


def find_certificate(username: str) -> Optional[Dict[str, str]]:
    for cert in list_demo_certificates():
        if cert.get("username") == username:
            return cert
    return None
