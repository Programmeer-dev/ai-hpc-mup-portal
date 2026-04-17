# 📋 MUP DMS Portal - Diplomski Rad
## Document Management System za MUP i Turističke Zahtjeve

---

## 🎯 Cilj Projekta

Kreiranje **Document Management System-a (DMS)** koji omogućava građanima da:
1. **Podnose zahtjeve** za MUP usluge (lična karta, pasoš, vozačka dozvola)
2. **Registruju kuće** za turističko izdavanje
3. **Prate status** kroz čitav workflow
4. **Izbjegavaju fizički odlazak** u MUP osim ako nije nužno

---

## 🏗️ Arhitektura Sistema

```
┌─────────────────────────────────────────────────────┐
│         FRONTEND - STREAMLIT APLIKACIJA              │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │   Login     │  │  Zahtjevi    │  │   Admin    │ │
│  │  (Auth)     │  │  (Submit)    │  │   Panel    │ │
│  └─────────────┘  └──────────────┘  └────────────┘ │
│                                                      │
└────────┬───────────────────────────────┬────────────┘
         │                               │
         ▼                               ▼
   ┌──────────────┐            ┌──────────────┐
   │  DMS Manager │            │  AI Assistant│
   │ (WorkFlow)   │            │  (DmsAI)     │
   └──────┬───────┘            └──────────────┘
          │
          ▼
   ┌─────────────────────────────────────┐
   │   BAZA PODATAKA - SQLAlchemy        │
   ├─────────────────────────────────────┤
   │ • dms_requests                      │
   │ • document_templates                │
   │ • request_status_history            │
   │ • request_comments                  │
   │ • tourism_properties                │
   │ • users (authentication)            │
   └─────────────────────────────────────┘
```

---

## 📊 Workflow Zahtjeva

```
1. DRAFT
   ↓
   Korisnik počinje ispunjavanje zahtjeva

2. SUBMITTED
   ↓
   Korisnik podnosi zahtjev sa dokumentima

3. UNDER_REVIEW
   ↓
   Radnik preuzima zahtjev i pregledava

4a. PENDING_USER → Čeka korisnika (treba dodatni dokument)
   ↓
   Korisnik učitava dodatne dokumente
   ↓
   [Nazad na UNDER_REVIEW]

4b. APPROVED
   ↓
   Zahtjev je odobren

5. COMPLETED
   ↓
   Zahtjev je obrađen i isporučen

REJECTED (bilo kada)
   ↓
   Zahtjev je odbijen sa razlogom
```

---

## 📁 Struktura Projekta

```
ai-hpc-gateway-prototype/
│
├── dms_core/                    ← DMS jezgra
│   ├── models.py               ← SQLAlchemy modeli
│   ├── manager.py              ← DMS Manager logika
│   ├── dms_ai.py               ← AI asistent za zahtjeve
│   ├── init_dms.py             ← Inicijalizacija baze
│   └── __init__.py
│
├── requirements_data/           ← Šabloni zahtjeva
│   ├── turizam_requirements.json
│   ├── mup_requirements.json    (će se učitati iz database/)
│   └── ...
│
├── pages/                       ← Streamlit stranice
│   ├── dms_requests.py         ← Podnošenje zahtjeva
│   ├── admin_panel.py          ← Admin panel za radnike
│   └── ...
│
├── database/                    ← Baza podataka
│   ├── mup_rules.json          ← MUP usluge
│   └── database.py             ← SQLAlchemy setup
│
├── app.py                       ← Glavna Streamlit aplikacija
├── requirements.txt             ← Python zavisnosti
└── README.md                    ← Dokumentacija
```

---

## 🛠️ Instalacija i Pokretanje

### Preduslov
- Python 3.9+
- SQLite (ili drugu bazu)
- pip

### Instalacija

```bash
# Kloniraj projekat
git clone <repo>
cd ai-hpc-gateway-prototype

# Kreiraj virtual environment
python -m venv .venv

# Aktiviraj (Windows)
.venv\Scripts\activate

# Instaliraj zavisnosti
pip install -r requirements.txt

# Inicijalizuj DMS bazu
python dms_core/init_dms.py

# Pokreni aplikaciju
streamlit run app.py
```

### URL-ovi
- **Glavna aplikacija:** http://localhost:8501
- **Admin panel:** http://localhost:8501/admin_panel
- **Moji zahtjevi:** http://localhost:8501/dms_requests

---

## 📚 Komponente Projekta

### 1. **DMS Models** (`dms_core/models.py`)
Baza podataka sa sledećim tabelama:

#### DmsRequest
- Centralni model za sve zahtjeve
- Linkovi na korisnika, status, prioritet
- Metadata za dokumente
- Vremenski žigovi

#### DocumentTemplate
- Šablon zahtjeva po tipu
- Potrebni/opcionalni dokumenti
- Procijenjeni vremenski rok
- Taksa

#### RequestStatusHistory
- Audit trail svih promjena statusa
- Ko je šta promijenio i kada

#### RequestComment
- Komunikacija između korisnika i radnika
- Interno vs javne napomene

#### TourismProperty
- Nekretnine registrovane za turizam
- Kapacitet, broj soba, lokacija
- Status licence

---

### 2. **DMS Manager** (`dms_core/manager.py`)
Logika za upravljanje zahtjevima:

```python
# Kreiranje zahtjeva
request = dms.create_request(
    request_type=RequestType.TURIZAM_REGISTRACIJA,
    user_id=user,
    description="Želim registrovati stan",
    reason="Izdavanje apartmana"
)

# Podnošenje zahtjeva
dms.submit_request(request.id)

# Upravljanje workflow-om
dms.start_review(request.id, assigned_to=worker)
dms.request_user_action(request.id, "Trebam dodatni dokument", worker)
dms.approve_request(request.id, approved_by=worker)
dms.complete_request(request.id, completed_by=worker)

# Pretraga
active = dms.get_active_requests()
my_requests = dms.get_user_requests(user_id)
overdue = dms.get_overdue_requests()
```

---

### 3. **AI Assistant** (`dms_core/dms_ai.py`)
Inteligentna pomoć korisnicima:

- **Detektovanje tipova zahtjeva** iz prirodnog jezika
- **Brzi odgovori** na česta pitanja
- **Informacije o dokumentima** potrebnim za zahtjev
- **Vremenski rokovi i naknade**

```python
# Primjer
ai = DmsAiAssistant(db)
response = ai.process_user_query("Trebam registrovati stan za turizam")
# Vraća: Listu potrebnih dokumenata, rok, taksu, itd.
```

---

### 4. **Streamlit Frontend**

#### 📋 `pages/dms_requests.py`
- **Tab 1:** Podnošenje MUP zahtjeva
- **Tab 2:** Podnošenje turističkih zahtjeva
- **Upload dokumenata**
- **Prikaz "Mojih zahtjeva"** sa statusom

#### ⚙️ `pages/admin_panel.py`
Za MUP/turizma radnike:
- **Dashboard** sa statistikom
- **Lista zahtjeva** sa filteriranjem
- **Detaljni pregled** svakog zahtjeva
- **Upravljanje statusom** (submit, review, approve, reject)
- **Dodavanje komentara** (javni/interni)
- **Statistika sistema**

---

## 📋 Tipovi Zahtjeva

### MUP Usluge
1. **Lična Karta** - 🆔
2. **Pasoš** - 🛂
3. **Vozačka Dozvola** - 🚗
4. **Krivični List** - 📜

### Turističke Registracije
1. **Registracija Kuće/Apartmana** - 🏠
   - Dokumenti: Dokaz vlasništva, lična karta, koordinate, fotografije
   - Rok: 15-45 dana
   - Polja: tip nekretnine, kapacitet, cijene, amenities

2. **Licenca za Javno Smještavanje** - 📜

3. **Dozvola za Adaptaciju/Rekonstrukciju** - 🏗️

---

## 🔐 Sigurnost

- **Autentifikacija:** bcrypt hash za lozinke
- **Kontrola pristupa:** Samo admini vide admin panel
- **Audit trail:** Sve promjene se čuvaju u istoriji
- **Privatnost:** Interni komentari skriveni od korisnika

---

## 📊 Planirana Proširenja

1. **Notifikacije**
   - Email obavijesti na promjenu statusa
   - SMS upozorenja za prekoračene rokove

2. **Integracija sa e-Upravom**
   - Direktna veza sa MUP sistemom
   - Automatska provjera podataka

3. **Plaćanja**
   - Online uplata taksa
   - Digitalni računi

4. **Mobilna Aplikacija**
   - React Native aplikacija
   - Push notifikacije

5. **Analitika**
   - Detaljne statistike po tipu zahtjeva
   - Vremenske serije za trend analizu
   - Geographic heatmaps

6. **Chat Podrška**
   - Live chat sa radnicima
   - Chatbot sa ML modelom

---

## 🐛 Testiranje

```bash
# Unit testovi
pytest tests/

# Integracija testovi
pytest tests/integration/

# Coverage
pytest --cov=.
```

---

## 📖 Korišćena Tehnologija

- **Frontend:** Streamlit
- **Backend:** Python, Flask (opciono za API)
- **Baza:** SQLAlchemy ORM, SQLite/PostgreSQL
- **Auth:** bcrypt
- **Email:** smtplib
- **Maps:** Folium, Google Maps API

---

## 👨‍💼 Autor
Studentski projekat - Diplomski rad  
Crna Gora, 2026

---

## 📞 Kontakt i Podrška

Za pitanja o sistemu kontaktirajte administratore MUP-a.

---

**Verzija:** 2.0 (DMS)  
**Posljednja ažuriranja:** Mart 2026
