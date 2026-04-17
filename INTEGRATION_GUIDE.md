# 🔗 Integration Guide - DMS sa Existing App

Kako integrisati novi **Document Management System** sa postojećom `app.py`.

---

## 📋 Checklist Integracije

- [ ] 1. Instaliraj nove zavisnosti
- [ ] 2. Ažuriraj database.py sa DMS modelima
- [ ] 3. Pokreni inicijalizaciju DMS-a
- [ ] 4. Dodaj DMS stranice u Streamlit navigaciju
- [ ] 5. Proširim AI bot sa DMS znanjem
- [ ] 6. Testiraj workflow-e

---

## 🔧 Korak-po-Korak Integracija

### 1️⃣ Ažuriranje dependencies

Dodaj u `requirements.txt`:
```
sqlalchemy>=2.0.0
pandas>=1.5.0
```

Pokreni:
```bash
pip install -r requirements.txt
```

---

### 2️⃣ Integracija sa bazom

**Ažuriraj `database/database.py`:**

```python
# --- DODAJ POČETAK ---
from dms_core.models import Base as DmsBase

# Kreiraj sve DMS tabele
def init_dms_tables():
    """Inicijalizuj DMS tabele"""
    DmsBase.metadata.create_all(engine)
    print("✅ DMS tabele kreirane")

# Pozovi pri startu aplikacije
init_dms_tables()
# --- DODAJ KRAJ ---
```

---

### 3️⃣ Inicijalizacija šablona zahtjeva

**Jedan put, tijekom prvog pokretanja:**

```bash
# Pokreni inicijalizaciju
python dms_core/init_dms.py

# Trebalo bi da vidisć:
# ✅ DMS baza podataka inicijalizirana
# ✓ MUP: Lična Karta
# ✓ MUP: Pasoš
# ... itd ...
# ✓ Turizam: Registracija Turističke Nekretnine
# ✅ DMS inicijalizacija završena! XX šablona učitano.
```

---

### 4️⃣ Dodaj DMS stranice u navigaciju

**U `app.py`, nakon login sekcije, dodaj:**

```python
# ========= NOVI DMS WORKFLOW =========
if st.session_state.page == "dms":
    from pages.dms_requests import dms_request_page, my_requests_page
    
    tab1, tab2 = st.tabs(["📋 Novi Zahtjev", "📥 Moji Zahtjevi"])
    with tab1:
        dms_request_page()
    with tab2:
        my_requests_page()

# Admin panel je dostupan kao odvojena stranica
elif st.session_state.page == "admin":
    from pages.admin_panel import admin_dashboard
    admin_dashboard()
```

**U sidebar (login sekcija), dodaj:**

```python
if st.session_state.user:
    st.markdown("---")
    st.subheader("📋 Document Management")
    
    if st.button("📤 Podnesi Zahtjev", use_container_width=True):
        st.session_state.page = "dms"
        st.rerun()
    
    if st.button("📥 Moji Zahtjevi", use_container_width=True):
        st.session_state.page = "dms"
        st.session_state.dms_tab = 1
        st.rerun()
    
    # Admin panel (samo za admin)
    if st.session_state.get('is_admin'):
        if st.button("⚙️ Admin Panel", use_container_width=True):
            st.session_state.page = "admin"
            st.rerun()
```

---

### 5️⃣ Proširenje AI Bota

**Ažuriraj `ai_chatbot.py` ili gdje god je chat logika:**

```python
# Dodaj na početak
from dms_core.dms_ai import get_dms_aware_response
from database.database import SessionLocal

# U chat_with_ai funkciji, prije nego što koristiš old AI:
def enhanced_chat(user_message):
    db = SessionLocal()
    
    # Prvo pokušaj sa DMS znanjem
    dms_response = get_dms_aware_response(user_message, db)
    
    # Ako je DMS dao odgovor, koristi ga
    if dms_response and "📋" in dms_response:
        return dms_response
    
    # Inače koristi originalni AI
    return chat_with_ai(user_message)
```

---

### 6️⃣ Update database.py sa admin flagom

**U `authenticate_user` funkciji:**

```python
def authenticate_user(username, password, db_session=None):
    # ... postojeći kod ...
    
    # Dodaj admin check
    is_admin = username in ['admin', 'rapoz', 'inspector1']  # Prilagodi po potrebi
    
    return {
        'user': username,
        'is_admin': is_admin,
        'auth_time': datetime.now()
    }
```

**U Streamlit session state:**

```python
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
```

---

## 🧪 Testiranje Integracije

### Test 1: Podnošenje zahtjeva
1. Login kao user
2. Klikni "📤 Podnesi Zahtjev"
3. Odaberi tip zahtjeva (npr. Turizam)
4. Ispuni formu
5. Klikni "Podnesi" ✅

### Test 2: Provjera statusa
1. Klikni "📥 Moji Zahtjevi"
2. Trebalo bi vidjeti podnesen zahtjev
3. Status: "submitted" ✅

### Test 3: Admin panel
1. Login kao admin
2. Klikni "⚙️ Admin Panel"
3. Trebalo bi vidjeti zahtjev u listi
4. Želim ga i promije status u "under_review" ✅

### Test 4: AI bot
1. U chat, napiši: "Trebam pasoš"
2. Bot bi trebao dati informacije o pasošu ✅
3. Napiši: "Kako da registrujem stan"
4. Bot bi trebao dati info o turističkim zahtjevima ✅

---

## 📁 Datoteke koje trebaju biti izmijenjene

```
app.py
├─ Dodaj DMS imports
├─ Dodaj DMS page logiku
└─ Ažuriraj sidebar sa DMS opcijama

database/database.py
├─ Import DMS Base
└─ init_dms_tables()

ai_chatbot.py
├─ Import DMS AI
└─ Proširiti chat sa DMS znanjem

(Nove datoteke koje će biti kreirane:)
dms_core/*
pages/dms_requests.py
pages/admin_panel.py
requirements_data/turizam_requirements.json
```

---

## ⚠️ Česti Problemi

### Problem: "ImportError: No module named 'dms_core'"
**Rješenje:** Kreiraj `dms_core/__init__.py` fajl (trebalo bi da postoji)

### Problem: Database greške
**Rješenje:** Obriši `instance/database.db` i pokreni ponovo
```bash
rm instance/database.db
python dms_core/init_dms.py
streamlit run app.py
```

### Problem: Admin panel nedostaje
**Rješenje:** Provjeri da li je `is_admin=True` u session state

### Problem: Šabloni zahtjeva nisu učitani
**Rješenje:**
```bash
# Opet inicijalizuj
python dms_core/init_dms.py

# Provjeri SQL
sqlite3 instance/database.db "SELECT COUNT(*) FROM document_templates;"
# Trebalo bi pokazati broj > 0
```

---

## 📊 Očekivani Rezultat nakon Integracije

**Sidebar:**
```
├─ 🔐 Login/Logout
├─ 📊 Moji Profil
├─ 📜 MUP Usluge
├─ 💬 Chat sa AI
├─ **📋 Document Management** ← NOVO
│  ├─ 📤 Podnesi Zahtjev
│  └─ 📥 Moji Zahtjevi
└─ **⚙️ Admin Panel** ← NOVO (samo za admin)
```

**Chat Bot:**
```
Korisnik: "Trebam pasoš"
Bot: "🛂 Pasoš
     📄 Potrebna Dokumenta:
     • Lična karta
     • Privremeni boravak
     ...
     ⏱️ Procijenjeni rok: 10 dana
     💶 Taksa: 25.00 EUR"
```

---

## 📞 Support

Za probleme sa integracijom, provjeri:
1. `DMS_DOCUMENTATION.md` - Detaljnija dokumentacija
2. `dms_core/` - Komenari u kodu
3. `pages/` - Primjeri implementacije

---

**Napomena:** Sve ove izmjene trebaju biti urađene sa pažnjom. Ako nešto ne radi, korak-po-korak vraćaj originalne datoteke.

**Verzija Guide:** 1.0  
**Kompatibilnost:** v2.0 DMS sistema
