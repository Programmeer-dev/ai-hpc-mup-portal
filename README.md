#  AI-HPC Gateway  MUP Portal Asistent

Inteligentni asistent za MUP (Ministarstvo unutrašnjih poslova) Crne Gore sa naprednim funkcijama za građane.

##  Funkcionalnosti

###  Autentifikacija i Personalizacija
- **Registracija/Login** sa sigurnim hash-ovanjem lozinki (bcrypt)
- **Izbor opštine** pri registraciji (23 opštine Crne Gore)
- Personalizovani prikaz MUP centara po opštini
- Čuvanje istorije upita korisnika

###  AI Chatbot Mod
- **Napredni keyword matching sistem** - radi bez OpenAI API-ja
- Pametno prepoznavanje konteksta razgovora
- Podrška za follow-up pitanja
- Normalizacija ćiriličnih karaktera (š, đ, č, ć, ž)

###  Klasična Pretraga
- Pretraga MUP usluga po ključnim riječima
- Prikaz svih informacija o uslugama

###  Mapa MUP Centara
- **Interaktivna mapa** sa Folium bibliotekom
- Automatski prikaz centara za opštinu korisnika

###  HPC Queue Simulator
- **Predviđanje čekanja** u redu
- Simulacija queue teorije

##  Pokretanje

```bash
pip install -r requirements.txt
streamlit run app.py
```

**Verzija:** 1.0.0
