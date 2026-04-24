# 🚀 BRZI START - Document Management System v2.0

## ✨ Što je novo?

Sva odgovornost za MUP zahtjeve je sada prenešena na **Document Management System**.

- ✅ Podnošenje MUP zahtjeva (lična karta, pasoš, vozačka dozvola)
- ✅ **Nove: Turističke registracije** (izdavanje, licence, dozvole)
- ✅ Status praćenja u realnom vremenu
- ✅ Admin panel za radnike
- ✅ AI bot sa znanjem o zahtjevima

---

## 📥 Instalacija (PRVO!)

```bash
# 1. Instaliraj zavisnosti
pip install -r requirements.txt

# 2. Inicijalizuj DMS bazu (VAŽNO - samo prvi put!)
python dms_core/init_dms.py

# 3. Pokreni aplikaciju
streamlit run app.py
```

## ✅ Brza Validacija Nakon Pokretanja

```bash
run_smoke_test.bat
python -m pytest -q
```

Ako oba koraka prođu bez greške, osnovni i regresioni tokovi su stabilni.

**Trebalo bi vidjeti:**
```
✅ DMS baza podataka inicijalizirana
✓ MUP: Lična Karta
✓ MUP: Pasoš
✓ MUP: Vozačka Dozvola
... (ostale MUP usluge) ...
✓ Turizam: Registracija Turističke Nekretnine
✓ Turizam: Licenca za Javno Smještavanje
✓ Turizam: Dozvola za Adaptaciju/Rekonstrukciju
✅ DMS inicijalizacija završena! 13 šablona učitano.
```

---

## 🎯 Kako funkcionira?

### 👤 Za Korisnike (Građane)

1. **Prijava** → Uloguješ se na portal
2. **Podnošenje zahtjeva** → 📋 "Podnesi Zahtjev"
   - Odaberi tip zahtjeva (MUP ili Turizam)
   - Ispuni formu sa detaljima
   - Učitaj potrebne dokumente
   - Klikni "Podnesi"
3. **Praćenje** → 📥 "Moji Zahtjevi"
   - Vidiš sve svoje zahtjeve
   - Status se mijenja automatski
   - Čituš komentare od radnika
4. **Notifikacije** → Kada se nešto izmijeni

### 👨‍💼 Za Radnike (MUP/Turizam)

1. **Login kao admin** → admin username
2. **Admin Panel** → ⚙️ "Admin Panel"
3. **Dashboard** → Vidisć sve zahtjeve, statistiku
4. **Upravljanje** → 
   - Preuzmite zahtjev
   - Proverite dokumente
   - Tražite dodatne podatke
   - Odobrite ili odbijte
   - Dodajte komentare

---

## 📂 Datoteke koje Trebam Znati

| Datoteka | Opis |
|----------|------|
| `dms_core/models.py` | Database struktura |
| `dms_core/manager.py` | Logika za zahtjeve |
| `dms_core/dms_ai.py` | AI za zahtjeve |
| `pages/dms_requests.py` | Stranica za podnošenje |
| `pages/admin_panel.py` | Admin stranica |
| `DMS_DOCUMENTATION.md` | Detaljne napomene |
| `INTEGRATION_GUIDE.md` | Kako dodati u app.py |
| `requirements_data/turizam_requirements.json` | Turizam šabloni |

---

## 🤖 AI Bot - Nove Mogućnosti

Sada bot zna o svim zahtjevima! Isprobaj:

```
Korisnik: "Trebam pasoš"
Bot: [detaljne informacije sa dokumentima, rokom, takom]

Korisnik: "Kako da registrujem stan za turizam?"
Bot: [informacije o registraciji turističke nekretnine]

Korisnik: "Koji dokumenti trebaju?"
Bot: [lista dokumenata za odabrani zahtjev]
```

---

## 🔐 Admin Pristup

**Admin korisnici mogu pristupiti:**
- Dashboard sa statistikom
- Lista svih zahtjeva
- Detaljni pregled svakog zahtjeva
- Upravljanje statusom
- Dodavanje komentara
- Dodjela zahtjeva

**Za testiranje, koristi username:** `admin` 

---

## 🧪 Test Scenario

### Test 1: Običan korisnik
```
1. Login kao 'test@test.com'
2. Klikni "📋 Podnesi Zahtjev"
3. Odaberi "🏠 Registracija Nekretnine"
4. Ispuni formu:
   - Grad: Kotor
   - Tip: apartman
   - Kapacitet: 4
   - Cijena: 50 EUR/noć
5. Učitaj neku sliku kao PDF (demo)
6. Klikni "Podnesi"
7. Vidiš "✅ Zahtjev uspješno podnesen!"
```

### Test 2: Admin pregled
```
1. Login kao 'admin'
2. Klikni "⚙️ Admin Panel"
3. U Dashboard vidiš zahtjev
4. Klikni na zahtjev
5. Promijeni status u "under_review"
6. Dodaj komentar
7. Odobrij zahtjev
```

### Test 3: Praćenje
```
1. Login kao obični korisnik
2. Klikni "📥 Moji Zahtjevi"
3. Vidiš svoj zahtjev sa statusom "odobrena"
4. Vidiš nahat administratora
```

---

## ❌ Ako nešto ne radi?

### Problem: "ImportError: No module named 'dms_core'"
```bash
# Provjeri da li postoji dms_core/__init__.py
ls dms_core/__init__.py
# Ako ne, kreiraj ga (trebalo bi da postoji)
```

### Problem: Database greška
```bash
# Obriši staru bazu
rm instance/database.db

# Ponovno inicijalizuj
python dms_core/init_dms.py

# Pokreni app
streamlit run app.py
```

### Problem: Nema šablona
```bash
# Provjeri datoteke
python -c "from dms_core import DocumentTemplate; from database.database import SessionLocal; db = SessionLocal(); print(db.query(DocumentTemplate).count())"
# Trebalo bi pokazati broj > 0
```

---

## 📚 Dokumentacija

- **DMS_DOCUMENTATION.md** - Kompletna arhitektura
- **INTEGRATION_GUIDE.md** - Kako integrirati sa app.py
- **Kod komentari** - U samim datotekama

---

## 🎓 Za Diplomski Rad

### Što je core doprinosa?
1. **Document Management System** sa workflow funkcionalnostima
2. **Turističke registracije** - novi aspekt
3. **Admin panel** za radnike
4. **AI Bot svjestan zahtjeva**

### Kako to objasniti?
```
Originalno: MUP Portal → čista informacijska stranica
v2.0: MUP DMS Portal → Kompletan sistem za rukljanje zahtjevima
  - Korisnici podnose zahtjeve
  - Radnici upravljaju workflow-om
  - Obavijesti u realnom vremenu
  - Turizam je integrisana kao nova modularna funkcionalnost
```

---

## 🔄 Sljedeći Koraci (Future Enhancements)

- [ ] Email notifikacije
- [ ] SMS upozorenja
- [ ] Integracija sa e-Upravom
- [ ] Online plaćanja
- [ ] Mobilna aplikacija
- [ ] Live chat podrška
- [ ] Advanced analytics

---

## 📞 Pitanja?

Ako nešto nije jasno:
1. Čitaj **DMS_DOCUMENTATION.md**
2. Pogledaj **kod u dms_core/**
3. Provjeri **INTEGRATION_GUIDE.md**
4. Pregled **kod komentare**

---

**Sretno sa razvojem! 🚀**

v2.0 - Document Management System  
Crna Gora, 2026
