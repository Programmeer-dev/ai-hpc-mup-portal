"""
Inicijalizacija DMS sistema
Popunjavanje baze sa šablonima zahtjeva (MUP + Turizam)
"""

import json
from datetime import datetime
from sqlalchemy.orm import Session
from dms_core.models import DocumentTemplate, Base, engine


def _normalize_request_type(value: str) -> str:
    """Normalizuj naziv usluge u ASCII request_type ključ."""
    replacements = {
        "č": "c",
        "ć": "c",
        "š": "s",
        "ž": "z",
        "đ": "dj",
    }
    normalized = value.lower().strip()
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    return normalized.replace("-", "_").replace(" ", "_")


def init_dms_templates(db: Session, mup_rules_path: str, turizam_path: str):
    """Popuni bazu sa svim šablonima zahtjeva"""
    
    # Učitaj MUP pravila
    with open(mup_rules_path, 'r', encoding='utf-8') as f:
        mup_rules = json.load(f)
    
    # Učitaj turističke zahtjeve
    with open(turizam_path, 'r', encoding='utf-8') as f:
        turizam = json.load(f)
    
    # Briši stare šablone
    db.query(DocumentTemplate).delete()
    
    print("[INFO] Inicijalizujem DMS sablone...")
    
    # ========== MUP ZAHTJEVI ==========
    for service_key, service_data in mup_rules.items():
        required_docs = service_data.get('dokumenta', [])
        
        template = DocumentTemplate(
            request_type=_normalize_request_type(service_key),
            required_documents=[{"naziv": doc, "obavezno": True} for doc in required_docs],
            estimated_days=service_data.get('rok_izrade_dana', 15),
            processing_fee_eur=service_data.get('taksa_eur', 0),
            instructions=f"Usluga: {service_key}\n\nUplata: {service_data.get('uplata', '')}",
            ai_keywords=[service_key.lower()] + service_key.lower().split()
        )
        
        db.add(template)
        print(f"  [OK] MUP: {service_key}")
    
    # ========== TURISTIČKE REGISTRACIJE ==========
    for turizam_type, turizam_data in turizam.items():
        required_docs = []
        if 'dokumenta_obavezna' in turizam_data:
            required_docs = [
                {
                    "naziv": doc.get('naziv'),
                    "opis": doc.get('opis'),
                    "format": doc.get('format', []),
                    "obavezno": True
                }
                for doc in turizam_data['dokumenta_obavezna']
            ]
        
        optional_docs = []
        if 'dokumenta_opciono' in turizam_data:
            optional_docs = [
                {
                    "naziv": doc.get('naziv'),
                    "opis": doc.get('opis'),
                    "format": doc.get('format', [])
                }
                for doc in turizam_data.get('dokumenta_opciono', [])
            ]
        
        # Izvuči taksu ako postoji
        taksa = turizam_data.get('taksa', {})
        fee = taksa.get('vrijednost', 0) if isinstance(taksa, dict) else 0
        
        template = DocumentTemplate(
            request_type=turizam_type,
            required_documents=required_docs,
            optional_documents=optional_docs,
            estimated_days=45,  # Default za turizam
            processing_fee_eur=fee,
            instructions=turizam_data.get('opis', ''),
            ai_keywords=turizam_data.get('ai_keywords', [])
        )
        
        db.add(template)
        print(f"  [OK] Turizam: {turizam_data.get('naziv', turizam_type)}")
    
    db.commit()
    print(f"\n[OK] DMS inicijalizacija zavrsena! {db.query(DocumentTemplate).count()} sablona ucitano.")


def init_dms_database(db_session: Session):
    """Kreira sve DMS tabele"""
    Base.metadata.create_all(engine)
    print("[OK] DMS baza podataka inicijalizirana")


if __name__ == "__main__":
    from dms_core.models import SessionLocal
    
    db = SessionLocal()
    
    # Kreiraj tabele
    init_dms_database(db)
    
    # Popuni šablone
    init_dms_templates(
        db,
        mup_rules_path='database/mup_rules.json',
        turizam_path='requirements_data/turizam_requirements.json'
    )
