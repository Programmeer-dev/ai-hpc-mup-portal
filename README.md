
# AI-HPC Gateway – MUP asistent (Prototip)

Ovo je minimalni MVP za demonstraciju:
- Chatbot koji odgovara na česta pitanja: šta je potrebno za ličnu kartu/pasoš/vozačku, takse i uplate.
- Lista najbližih MUP centara uz linkove za mape.
- *HPC light* simulacija reda (procjena čekanja i predlog vremena dolaska).

## Pokretanje lokalno
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment (brzo)
- **Streamlit Community Cloud** (besplatno): repo → *New app* → `app.py`
- **Hugging Face Spaces**: izaberi *Streamlit* template, uploduj fajlove

## Struktura
```
ai-hpc-gateway-prototype/
├── app.py
├── queue_sim.py
├── utils.py
├── requirements.txt
└── data/
    ├── mup_rules.json
    └── centers.json
```

## Ideje za naredne iteracije (prezentabilno do 5. decembra)
1. Dodati 6–10 usluga (boravišna dozvola, prebivalište, promjena adrese...).
2. Uvesti jednostavnu rezervaciju termina (virtuelni broj + e-mail podsjetnik).
3. Logovanje upita (CSV) i osnovna analitika u sidebaru.
4. Opcioni *Ray/Dask* modul za simulacije po gradovima.
5. UI poliranje (logo, boje, potvrde).

> Napomena: Svi podaci u `data/` su demo. Provjeru i ažuriranje taksi/pravila vršiti prema zvaničnim izvorima.
