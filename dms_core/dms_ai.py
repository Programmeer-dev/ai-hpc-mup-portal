"""
DMS AI Bot - Inteligentna pomoć za zahtjeve
Proširena verzija AI chatbota sa znanjem o DMS sistemu
"""

import json
from typing import Optional, Dict, List
from dms_core import DocumentTemplate


class DmsAiAssistant:
    """AI asistent za DMS zahtjeve"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """Učitaj sve šablone zahtjeva"""
        templates = {}
        
        all_templates = self.db.query(DocumentTemplate).all()
        for template in all_templates:
            templates[template.request_type] = {
                'required': template.required_documents,
                'optional': template.optional_documents,
                'days': template.estimated_days,
                'fee': template.processing_fee_eur,
                'keywords': template.ai_keywords
            }
        
        return templates
    
    def process_user_query(self, query: str) -> str:
        """Procesiraj upit korisnika i daj relevantan odgovor"""
        query_lower = query.lower()
        
        # Detektuj tip zahtjeva
        detected_type = self._detect_request_type(query_lower)
        
        if detected_type:
            return self._generate_request_help(detected_type, query)
        
        # Opšta pomoć
        if any(word in query_lower for word in ['kako', 'što trebam', 'šta trebam', 'koji dokumenti', 'koji papiri']):
            return self._generate_general_help(query)
        
        return self._generate_default_response()
    
    def _detect_request_type(self, query: str) -> Optional[str]:
        """Detektuj tip zahtjeva iz upita"""
        
        for req_type, template in self.templates.items():
            keywords = template.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() in query:
                    return req_type
        
        return None
    
    def _generate_request_help(self, request_type: str, user_query: str) -> str:
        """Generiši pomoć za specifičan zahtjev"""
        
        template = self.templates.get(request_type)
        if not template:
            return "❓ Izvinjavam se, nisam pronašao informacije o tom zahtjevu."
        
        response = f"📋 **{request_type.replace('_', ' ').title()}**\n\n"
        
        # Potrebni dokumenti
        response += "**📄 Potrebni Dokumenti:**\n"
        if template.get('required'):
            for doc in template['required']:
                if isinstance(doc, dict):
                    response += f"• ✓ {doc.get('naziv', doc)}\n"
                else:
                    response += f"• ✓ {doc}\n"
        
        # Opcionalni dokumenti
        if template.get('optional'):
            response += "\n**📎 Opcionalni Dokumenti:**\n"
            for doc in template['optional']:
                if isinstance(doc, dict):
                    response += f"• ⚪ {doc.get('naziv', doc)}\n"
                else:
                    response += f"• ⚪ {doc}\n"
        
        # Vremenski rok
        if template.get('days'):
            response += f"\n**⏱️ Procijenjeni rok:** oko {template['days']} dana\n"
        
        # Taksa
        if template.get('fee'):
            response += f"**💶 Taksa:** {template['fee']:.2f} EUR\n"
        
        # Akcija
        response += f"\n🎯 **Sljedeći korak:** Možete podnijeti zahtjev preko '📋 Podnošenje Zahtjeva' odjeljka."
        
        return response
    
    def _generate_general_help(self, query: str) -> str:
        """Generiši opštu pomoć"""
        
        response = "👋 **Kako Vam mogu pomoći?**\n\n"
        
        response += "Mogu Vam pružiti informacije o:\n"
        response += "• 🏛️ **MUP Usluge** - Lična karta, pasoš, vozačka dozvola\n"
        response += "• 🏖️ **Turističke Registracije** - Registracija nekretnine, licence\n"
        response += "• 📄 **Potrebni Dokumenti** - Koje dokumente trebate\n"
        response += "• ⏱️ **Vremenski Rokovi** - Koliko traje procedura\n"
        response += "• 💶 **Naknade** - Koje su takse potrebne\n\n"
        
        response += "Napišite što vas zanima, npr:\n"
        response += "- 'Trebam pasoš'\n"
        response += "- 'Kako da registrujem stan za turizam'\n"
        response += "- 'Što trebam za licnu kartu'\n"
        
        return response
    
    def _generate_default_response(self) -> str:
        """Podrazumevani odgovor"""
        return """
        Izvinjavam se, nisam sigurna što ste pitali. 🤔
        
        Mogu Vam pomoći sa informacijama o:
        • MUP uslugama (lična karta, pasoš, vozačka dozvola)
        • Turističkim registracijama (izdavanje apartmana, smještaja)
        • Potrebnim dokumentima
        • Vremenskim rokovama
        
        Pokušajte sa: "Trebam pasoš" ili "Registracija turističke nekretnine"
        """
    
    def get_quick_answers(self) -> Dict[str, str]:
        """Brzi odgovori na česta pitanja"""
        
        return {
            "koliko traje pasos": "🛂 Pasoš se obično izdaje u roku od 10-15 dana.",
            "koliko traje licna karta": "🆔 Lična karta se obično izdaje u roku od 5-7 dana.",
            "koliko traje vozacka dozvola": "🚗 Vozačka dozvola se obično izdaje u roku od 15 dana.",
            "koliko je taksa za pasos": "💶 Taksa za pasoš je oko 25 EUR.",
            "koliko je taksa za licnu kartu": "💶 Taksa za lična karta je oko 15 EUR.",
            "kako registrujem stan": "🏖️ Trebate podnijeti zahtjev sa dokumentima o vlasništvu i fotkama.",
            "koji dokumenti trebaju za stan": "📄 Dokumenti vlasništva, lična karta, dokazani adresa, fotografije.",
            "da li postoji aplikacija": "📱 Da, koristite ovaj portal za sve zahtjeve.",
            "kako pratim svoj zahtjev": "📋 Provjeri 'Moji Zahtjevi' odjeljak za status.",
            "koliko stoji registracija stana": "💶 Taksa je oko 50 EUR, ali zavisi od tipa.",
        }


def enhance_chatbot_with_dms(original_response: str, dms_context: str) -> str:
    """Kombinuj originalni odgovor chatbota sa DMS kontekstom"""
    
    if dms_context and len(dms_context) > 10:
        return f"{original_response}\n\n---\n\n💡 **Dodatne Informacije iz DMS Sistema:**\n{dms_context}"
    
    return original_response


# Integracija sa postojećim AI botom
def get_dms_aware_response(user_message: str, db_session) -> str:
    """Dohvata odgovor koji je svjestan DMS sistema"""
    
    dms_ai = DmsAiAssistant(db_session)
    
    # Prvo provjeri DMS
    dms_response = dms_ai.process_user_query(user_message)
    
    # Ako je detektovan zahtjev, vrati DMS odgovor
    if dms_response and "📋" in dms_response:
        return dms_response
    
    # Ako nije, vrati iz baze brziih odgovora
    quick_answers = dms_ai.get_quick_answers()
    
    for question, answer in quick_answers.items():
        if question in user_message.lower():
            return answer
    
    # Fallback na generalan odgovor
    return dms_ai._generate_general_help(user_message)
