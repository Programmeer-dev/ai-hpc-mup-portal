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

def get_smart_response(user_message: str, rules: dict, centers: list = None, context: dict = None, user_city: str = None) -> str:
    """
    Pametan odgovor sa kontekstom i personalizacijom
    """
    if context is None:
        context = {}
    
    user_lower = user_message.lower()
    user_normalized = normalize_text(user_lower)
    
    # Provjeri da li je ovo follow-up pitanje (npr. "a koliko košta?")
    if any(word in user_normalized for word in ["a ", "i ", "to", "onda", "jos"]):
        if 'last_service' in context:
            # Odnosi se na prethodni servis
            service = context['last_service']
            if service in rules:
                info = rules[service]
                
                # Detektuj šta se pita
                if any(word in user_normalized for word in ["kost", "cijen", "taksa", "plat"]):
                    return f"💶 **{service.title()}** košta **{info['taksa_eur']} €**\n\n🏦 Uplata: {info['uplata']}"
                elif any(word in user_normalized for word in ["koliko", "rok", "dan", "traje"]):
                    return f"⏱️ **{service.title()}** se radi oko **{info['rok_izrade_dana']} dana**"
                elif any(word in user_normalized for word in ["dokument", "treba", "potrebn"]):
                    return f"📄 **Dokumenta za {service}:**\n\n" + "\n".join([f"• {doc}" for doc in info['dokumenta']])
    
    # Inače koristi standardnu detekciju
    return get_fallback_response(user_message, rules, centers, user_city)

def get_fallback_response(user_message: str, rules: dict, centers: list = None, user_city: str = None) -> str:
    """
    Fallback odgovor ako OpenAI nije dostupan - napredni keyword matching
    """
    user_lower = user_message.lower()
    user_normalized = normalize_text(user_lower)
    
    # Detektuj tip upita - provjeri cijelu poruku, ne samo pitanja
    asking_about_payment = any(word in user_normalized for word in ["uplat", "plat", "taksa", "gdje", "gde", "kako", "kost", "cijen", "cijena", "para"])
    asking_about_documents = any(word in user_normalized for word in ["dokument", "potrebn", "treba", "sta", "šta", "nosit", "donij"])
    asking_about_time = any(word in user_normalized for word in ["koliko", "rok", "dugo", "dan", "brzo", "kada", "kad", "traje"])
    asking_about_location = any(word in user_normalized for word in ["gdje", "gde", "adres", "centar", "mup", "lokacij", "najbliz", "bliz"])
    
    # Keyword detection - provjeri i originalni i normalizovani tekst
    service = None
    if any(word in user_lower for word in ["pasoš", "pasosh", "putni", "putna"]) or \
       any(word in user_normalized for word in ["pasos", "pasosh", "putni", "putna"]):
        service = "pasoš"
    elif any(word in user_lower for word in ["lična", "licna", "karta", "identifikacija"]) or \
         any(word in user_normalized for word in ["licna", "karta", "identifikacija"]):
        service = "lična karta"
    elif any(word in user_lower for word in ["vozačka", "vozacka", "dozvola", "vozač", "vozac"]) or \
         any(word in user_normalized for word in ["vozacka", "dozvola", "vozac"]):
        service = "vozačka dozvola"
    elif any(word in user_lower for word in ["prebivalište", "prebivaliste", "adresa", "promjena", "promjena"]) or \
         any(word in user_normalized for word in ["prebivaliste", "adresa", "promjena", "promena"]):
        service = "promjena prebivališta"
    else:
        return "🤖 Pitaj me o: ličnoj karti, pašošu, vozačkoj dozvoli ili promjeni prebivališta.\n\n💡 Mogu ti reći:\n- Koliko košta?\n- Gdje da uplatim?\n- Koja dokumenta su potrebna?\n- Koliko traje izrada?\n- Gdje je najbliži MUP?"
    
    if service in rules:
        info = rules[service]
        
        # Specifičan odgovor na osnovu tipa pitanja
        if asking_about_payment:
            return f"""💶 **Uplata za {service}**

**Cijena:** {info['taksa_eur']} €

**Gdje i kako uplatiti:**
{info['uplata']}

💡 Uplatu možeš izvršiti na bilo kojem pošanskom šalteru ili banci sa ovim podacima."""
        
        elif asking_about_documents:
            return f"""📄 **Potrebna dokumenta za {service}**

Trebaće ti:
{chr(10).join([f'• {doc}' for doc in info['dokumenta']])}

💶 Cijena: {info['taksa_eur']} €
⏱️ Rok: {info['rok_izrade_dana']} dana

💡 Donesi sve dokumente u najbliži MUP centar!"""
        
        elif asking_about_time:
            return f"""⏱️ **Rok izrade - {service}**

**Vrijeme izrade:** {info['rok_izrade_dana']} dana

💶 Cijena: {info['taksa_eur']} €
📄 Dokumenta: {len(info['dokumenta'])} stavki

💡 Rok može biti duži u periodu gužvi."""
        
        elif asking_about_location:
            # Personalizovani odgovor na osnovu grada korisnika
            location_response = f"""📍 **MUP centri za {service}**

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
            
            location_response += "\n\n💡 Koristi dugme '📍 Vidi na mapi' da vidiš tačne lokacije!"
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
• "Gdje da uplatim {service}?"
• "Koliko košta {service}?"
• "Koja dokumenta trebaju?"
• "Gdje je najbliži MUP?"""
    
    return "🤖 Pitaj me o MUP uslugama!"
