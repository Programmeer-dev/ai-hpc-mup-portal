"""
AI Chatbot za MUP portal - koristi OpenAI API za konverzaciju
"""
import openai
import os
from typing import List, Dict

def init_openai():
    """Inicijalizuj OpenAI API - postavi svoj API key"""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        openai.api_key = api_key
        return True
    return False

def create_system_prompt(rules: dict, centers: list) -> str:
    """Kreiraj system prompt sa kontekstom o MUP uslugama"""
    
    services_info = "\n".join([
        f"- {service}: Taksa {info['taksa_eur']}€, Rok {info['rok_izrade_dana']} dana, "
        f"Dokumenta: {', '.join(info['dokumenta'])}"
        for service, info in rules.items()
    ])
    
    centers_info = "\n".join([
        f"- {c['naziv']}: {c['radno_vrijeme']}"
        for c in centers[:5]
    ])
    
    return f"""Ti si AI asistent za MUP (Ministarstvo unutrašnjih poslova) portal u Crnoj Gori.

Tvoj zadatak je da pomogneš građanima sa informacijama o:
- Izdavanju dokumenata (lična karta, pasoš, vozačka dozvola)
- Procedurama i potrebnim dokumentima
- Taksama i rokovima
- Najbližim MUP centrima

DOSTUPNE USLUGE:
{services_info}

MUP CENTRI:
{centers_info}

PRAVILA KOMUNIKACIJE:
- Uvijek odgovori na crnogorskom/srpskom jeziku
- Budi ljubazan i profesionalan
- Daj konkretne informacije iz gornjeg konteksta
- Ako korisnik pita o usluzi koja nije navedena, ljubazno reci da trenutno podržavaš samo gore navedene usluge
- Predloži najbliži MUP centar ako je relevantno
- Ako nisi siguran, radije reci da će te proveriti nego izmišljaj informacije
"""

def chat_with_ai(messages: List[Dict[str, str]], rules: dict, centers: list, model: str = "gpt-3.5-turbo") -> str:
    """
    Pozovi OpenAI API za chat completion
    
    Args:
        messages: Lista poruka u formatu [{"role": "user/assistant", "content": "..."}]
        rules: Rječnik sa pravilima o uslugama
        centers: Lista MUP centara
        model: OpenAI model (default: gpt-3.5-turbo)
    
    Returns:
        Odgovor AI asistenta
    """
    try:
        # Dodaj system prompt na početak
        system_message = {
            "role": "system",
            "content": create_system_prompt(rules, centers)
        }
        
        full_messages = [system_message] + messages
        
        # Pozovi OpenAI API
        response = openai.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    except openai.AuthenticationError:
        return "⚠️ API key nije podešen. Molim konfiguriši OPENAI_API_KEY u .env fajlu."
    except openai.RateLimitError:
        return "⚠️ Dostignut limit API poziva. Pokušaj kasnije."
    except Exception as e:
        return f"⚠️ Greška pri komunikaciji sa AI: {str(e)}"

def normalize_text(text: str) -> str:
    """
    Normalizuj tekst - zamijeni specijalne karaktere sa običnim
    """
    replacements = {
        'š': 's', 'Š': 'S',
        'đ': 'd', 'Đ': 'D',
        'č': 'c', 'Č': 'C',
        'ć': 'c', 'Ć': 'C',
        'ž': 'z', 'Ž': 'Z'
    }
    normalized = text
    for special, normal in replacements.items():
        normalized = normalized.replace(special, normal)
    return normalized

def get_accusative_form(service: str) -> str:
    """
    Vrati akuzativ formu servisa (za 'uplatim', 'izvadim', 'obnovim'...)
    Akuzativ = odgovara na pitanje KOGA? ŠTA?
    """
    accusative_forms = {
        'lična karta': 'ličnu kartu',
        'pasoš': 'pasoš',
        'vozačka dozvola': 'vozačku dozvolu',
        'promjena prebivališta': 'promjenu prebivališta'
    }
    return accusative_forms.get(service, service)

def get_genitive_form(service: str) -> str:
    """
    Vrati genitiv formu servisa (za 'izrada', 'rok', 'cijena'...)
    Genitiv = odgovara na pitanje KOGA? ČEGA?
    """
    genitive_forms = {
        'lična karta': 'lične karte',
        'pasoš': 'pasoša',
        'vozačka dozvola': 'vozačke dozvole',
        'promjena prebivališta': 'promjene prebivališta'
    }
    return genitive_forms.get(service, service)

def get_locative_form(service: str) -> str:
    """
    Vrati lokativ formu servisa (za 'o', 'pri', 'na'...)
    Lokativ = odgovara na pitanje O KOME? O ČEMU?
    """
    locative_forms = {
        'lična karta': 'ličnoj karti',
        'pasoš': 'pašošu',
        'vozačka dozvola': 'vozačkoj dozvoli',
        'promjena prebivališta': 'promjeni prebivališta'
    }
    return locative_forms.get(service, service)

def get_smart_response(user_message: str, rules: dict, centers: list = None, context: dict = None, user_city: str = None) -> str:
    """
    Pametan odgovor sa kontekstom i personalizacijom
    """
    if context is None:
        context = {}
    
    user_lower = user_message.lower()
    user_normalized = normalize_text(user_lower)
    
    # Provjeri da li je ovo follow-up pitanje - ako je servis već poznat u kontekstu
    # i pitanje ne pominje eksplicitno drugi servis
    has_service_mention = any(word in user_normalized for word in ["licna", "karta", "pasos", "vozacka", "dozvola", "prebivalist"])
    
    if 'last_service' in context and not has_service_mention:
        # Follow-up pitanje se odnosi na prethodni servis
        service = context['last_service']
        if service in rules:
            info = rules[service]
            
            # Detektuj šta se pita - sa i bez znaka pitanja
            if any(word in user_normalized for word in ["kost", "cijen", "taksa", "plat", "placa"]):
                return f"💶 **{service.title()}** košta **{info['taksa_eur']} €**\n\n🏦 Uplata: {info['uplata']}"
            elif any(word in user_normalized for word in ["koliko", "rok", "dan", "traje", "dug", "izrad", "gotov", "ceka"]):
                return f"⏱️ **{service.title()}** se radi za **{info['rok_izrade_dana']} radnih dana**\n\n📅 Od podnošenja zahtjeva do preuzimanja: {info['rok_izrade_dana']} dana\n\n💡 Rok može biti duži u periodu gužve."
            elif any(word in user_normalized for word in ["dokument", "treba", "potrebn", "dokum"]):
                service_acc = get_accusative_form(service)
                return f"📄 **Dokumenta za {service_acc}:**\n\n" + "\n".join([f"• {doc}" for doc in info['dokumenta']])
    
    # Inače koristi standardnu detekciju
    return get_fallback_response(user_message, rules, centers, user_city)

def get_fallback_response(user_message: str, rules: dict, centers: list = None, user_city: str = None) -> str:
    """
    Fallback odgovor ako OpenAI nije dostupan - napredni keyword matching
    """
    user_lower = user_message.lower()
    user_normalized = normalize_text(user_lower)
    
    # Detektuj tip upita - prepoznaj i bez znaka pitanja, i sa normalizovanim slovima
    asking_about_payment = any(word in user_normalized for word in ["uplat", "plat", "taksa", "gdje", "gde", "kako", "kost", "cijen", "para", "placa"])
    asking_about_documents = any(word in user_normalized for word in ["dokument", "potrebn", "treba", "sta", "nosit", "donij", "dokum"])
    asking_about_time = any(word in user_normalized for word in ["koliko", "rok", "dugo", "dan", "brzo", "kada", "kad", "traje", "dug", "izrad", "gotov", "sprem", "ceka", "cekanj"])
    asking_about_location = any(word in user_normalized for word in ["gdje", "gde", "adres", "centar", "mup", "lokacij", "najbliz", "bliz", "lokacija"])
    
    # Keyword detection - koristi normalizovani tekst za bolje prepoznavanje
    service = None
    if any(word in user_normalized for word in ["pasos", "pasosh", "putni", "putna", "paso"]):
        service = "pasoš"
    elif any(word in user_normalized for word in ["licna", "karta", "identifikacija", "licn"]):
        service = "lična karta"
    elif any(word in user_normalized for word in ["vozacka", "dozvola", "vozac", "vozack"]):
        service = "vozačka dozvola"
    elif any(word in user_normalized for word in ["prebivaliste", "adresa", "promjena", "promena", "prebivalist"]):
        service = "promjena prebivališta"
    else:
        return "🤖 Pitaj me o: ličnoj karti, pasošu, vozačkoj dozvoli ili promjeni prebivališta.\n\n💡 Mogu ti reći:\n- Koliko košta?\n- Gdje da uplatim?\n- Koja dokumenta su potrebna?\n- Koliko traje izrada?\n- Gdje je najbliži MUP?"
    
    if service in rules:
        info = rules[service]
        
        # Specifičan odgovor na osnovu tipa pitanja
        if asking_about_payment:
            service_acc = get_accusative_form(service)
            return f"""💶 **Uplata za {service_acc}**

**Cijena:** {info['taksa_eur']} €

**Gdje i kako uplatiti:**
{info['uplata']}

💡 Uplatu možeš izvršiti na bilo kojem pošanskom šalteru ili banci sa ovim podacima."""
        
        elif asking_about_documents:
            service_acc = get_accusative_form(service)
            return f"""📄 **Potrebna dokumenta za {service_acc}**

Trebaće ti:
{chr(10).join([f'• {doc}' for doc in info['dokumenta']])}

💶 Cijena: {info['taksa_eur']} €
⏱️ Rok: {info['rok_izrade_dana']} dana

💡 Donesi sve dokumente u najbliži MUP centar!"""
        
        elif asking_about_time:
            service_gen = get_genitive_form(service)
            return f"""⏱️ **Rok izrade {service_gen}**

✅ **{service.title()} se radi za {info['rok_izrade_dana']} dana**

📅 Od dana podnošenja zahtjeva do preuzimanja dokumenta obično prođe **{info['rok_izrade_dana']} radnih dana**.

💶 Cijena: {info['taksa_eur']} €
📄 Potrebna dokumenta: {len(info['dokumenta'])} stavki

⚠️ Napomena: Rok može biti duži u periodu velike gužve (sezona, kraj godine)."""
        
        elif asking_about_location:
            # Personalizovani odgovor na osnovu grada korisnika
            service_acc = get_accusative_form(service)
            location_response = f"""📍 **MUP centri za {service_acc}**

Možeš se obratiti u bilo koji MUP centar u Crnoj Gori.\n\n"""
            
            if centers and len(centers) > 0:
                if user_city:
                    location_response += f"**Najbliži centri u {user_city}:**\n"
                else:
                    location_response += f"**Najbliži centri:**\n"
                
                for center in centers[:3]:
                    location_response += f"• {center['naziv']} ({center['radno_vrijeme']})\n"
            else:
                location_response += """**Glavni centri:**
• MUP Podgorica – Ulica Kralja Nikole 61 (08:00-15:00)
• MUP Nikšić – Trg Šaka Petrovića 2 (08:00-14:30)
• MUP Danilovgrad – Ulica Nikole Tesle 14 (08:00-14:30)"""
            
            location_response += "\n\n🗺️ **Mapa sa lokacijama prikazana ispod...**"
            return location_response
        
        else:
            # Opšti odgovor
            return f"""📋 **{service.title()}**

💶 **Taksa:** {info['taksa_eur']} €
⏱️ **Rok:** {info['rok_izrade_dana']} dana

📄 **Potrebna dokumenta:**
{chr(10).join([f'• {doc}' for doc in info['dokumenta']])}

🏦 **Uplata:**
{info['uplata']}

💡 Pitaj me specificnije:
• "Gdje da uplatim {get_accusative_form(service)}?"
• "Koliko košta {service}?"
• "Koja dokumenta trebaju?"
• "Gdje je najbliži MUP?"""
    
    return "🤖 Pitaj me o MUP uslugama!"
