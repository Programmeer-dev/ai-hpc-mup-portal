"""
DMS AI chatbot

Hybrid assistant for the DMS portal:
- deterministic intent routing for stable FAQ answers
- retrieval from DMS templates and rules
- optional OpenAI generation when OPENAI_API_KEY is configured
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from dms_core import DocumentTemplate


logger = logging.getLogger("dms_portal.ai")
BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class TemplateKnowledge:
    request_type: str
    required: List
    optional: List
    days: Optional[int]
    fee: Optional[float]
    instructions: str
    keywords: List[str]


class DmsAiAssistant:
    """Chatbot that answers portal questions with DMS-aware context."""

    def __init__(self, db_session):
        self.db = db_session
        self.templates = self._load_templates()
        self.intent_keywords = {
            "required_docs": {"dokument", "dokumenti", "papiri", "sta", "treba", "potrebno"},
            "fee": {
                "taksa",
                "cijena",
                "cena",
                "koliko",
                "kosta",
                "placanje",
                "uplata",
                "uplatim",
                "uplatiti",
                "ziro",
                "racun",
            },
            "timeline": {"rok", "vrijeme", "vreme", "koliko", "traje", "dana"},
            "status_tracking": {"status", "pratim", "pracenje", "moji", "zahtjevi", "zahtev"},
            "submission": {"podnesi", "podnosenje", "kako", "gdje", "gde", "forma"},
        }

    def _normalize(self, text: str) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize("NFKD", text)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.lower()
        normalized = re.sub(r"[^a-z0-9\s_]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _title_from_request_type(self, request_type: str) -> str:
        return request_type.replace("_", " ").title()

    def _load_templates(self) -> Dict[str, TemplateKnowledge]:
        source_keywords = self._load_source_keywords()
        templates: Dict[str, TemplateKnowledge] = {}
        rows = self.db.query(DocumentTemplate).all()

        for row in rows:
            base_keywords = set()
            for kw in row.ai_keywords or []:
                normalized_kw = self._normalize(str(kw))
                if normalized_kw:
                    base_keywords.add(normalized_kw)

            request_name = self._normalize(row.request_type.replace("_", " "))
            if request_name:
                base_keywords.add(request_name)
                for token in request_name.split():
                    if len(token) > 2:
                        base_keywords.add(token)

            normalized_request_type = self._normalize(row.request_type)
            for source_key, keywords in source_keywords.items():
                if source_key in {
                    request_name,
                    normalized_request_type.replace("_", " "),
                }:
                    base_keywords.update(keywords)

            templates[row.request_type] = TemplateKnowledge(
                request_type=row.request_type,
                required=row.required_documents or [],
                optional=row.optional_documents or [],
                days=row.estimated_days,
                fee=row.processing_fee_eur,
                instructions=row.instructions or "",
                keywords=sorted(base_keywords),
            )

        return templates

    def _load_source_keywords(self) -> Dict[str, List[str]]:
        source_keywords: Dict[str, List[str]] = {}
        source_files = [
            BASE_DIR / "database" / "mup_rules.json",
            BASE_DIR / "requirements_data" / "turizam_requirements.json",
        ]

        for source_file in source_files:
            if not source_file.exists():
                continue

            try:
                with open(source_file, "r", encoding="utf-8") as file:
                    payload = json.load(file)
            except Exception:
                logger.exception("Failed to load source keywords from %s", source_file)
                continue

            if not isinstance(payload, dict):
                continue

            for raw_key, raw_value in payload.items():
                normalized_key = self._normalize(str(raw_key))
                keywords = source_keywords.setdefault(normalized_key, [])

                if isinstance(raw_value, dict):
                    aliases = raw_value.get("alias") or raw_value.get("ai_keywords") or []
                    for item in aliases:
                        normalized_item = self._normalize(str(item))
                        if normalized_item and normalized_item not in keywords:
                            keywords.append(normalized_item)

                    for token in normalized_key.split():
                        if len(token) > 2 and token not in keywords:
                            keywords.append(token)

        return source_keywords

    def _detect_intent(self, normalized_query: str) -> str:
        tokens = set(normalized_query.split())
        best_intent = "general"
        best_score = 0

        for intent, words in self.intent_keywords.items():
            score = len(tokens.intersection(words))
            if score > best_score:
                best_intent = intent
                best_score = score

        return best_intent

    def _detect_request_type(self, normalized_query: str) -> Tuple[Optional[str], float]:
        if not normalized_query:
            return None, 0.0

        query_tokens = set(normalized_query.split())
        best_match: Optional[str] = None
        best_score = 0.0

        for request_type, knowledge in self.templates.items():
            score = 0.0
            request_name = self._normalize(request_type.replace("_", " "))
            if request_name and request_name in normalized_query:
                score += 2.0

            for keyword in knowledge.keywords:
                if keyword and keyword in normalized_query:
                    score += min(2.0, 1.0 + len(keyword.split()) * 0.3)

            for token in query_tokens:
                if token in request_name.split():
                    score += 0.4

            if score > best_score:
                best_score = score
                best_match = request_type

        confidence = min(1.0, best_score / 4.0)
        return best_match, confidence

    def _extract_doc_names(self, docs: Sequence) -> List[str]:
        items: List[str] = []
        for item in docs or []:
            if isinstance(item, dict):
                items.append(str(item.get("naziv") or item.get("name") or item))
            else:
                items.append(str(item))
        return [item for item in items if item]

    def _build_context(self, request_type: Optional[str]) -> str:
        if not request_type or request_type not in self.templates:
            return ""

        template = self.templates[request_type]
        required = self._extract_doc_names(template.required)
        optional = self._extract_doc_names(template.optional)

        lines = [
            f"Tip zahtjeva: {self._title_from_request_type(request_type)}",
            f"Rok (dani): {template.days if template.days is not None else 'n/a'}",
            f"Taksa (EUR): {template.fee if template.fee is not None else 'n/a'}",
            "Obavezni dokumenti: " + (", ".join(required) if required else "n/a"),
            "Opcioni dokumenti: " + (", ".join(optional) if optional else "n/a"),
            "Uputstvo: " + (template.instructions.strip() or "n/a"),
        ]
        return "\n".join(lines)

    def _extract_payment_info(self, instructions: str) -> Optional[str]:
        if not instructions:
            return None
        match = re.search(r"uplata\s*:\s*(.+)", instructions, flags=re.IGNORECASE)
        if not match:
            return None
        payment = match.group(1).strip()
        return payment or None

    def _infer_request_type_from_history(
        self,
        chat_history: Optional[List[Dict[str, str]]],
    ) -> Tuple[Optional[str], float]:
        if not chat_history:
            return None, 0.0

        for item in reversed(chat_history[-6:]):
            if item.get("role") != "assistant":
                continue
            content = item.get("content", "")
            if not content:
                continue

            title_match = re.search(r"^###\s+([^\n]+)", content, flags=re.MULTILINE)
            if not title_match:
                continue

            normalized_title = self._normalize(title_match.group(1))
            for request_type in self.templates:
                normalized_request_name = self._normalize(request_type.replace("_", " "))
                if normalized_title == normalized_request_name:
                    return request_type, 1.0

        recent_text = []
        for item in chat_history[-6:]:
            role = item.get("role")
            content = item.get("content", "")
            if role in {"user", "assistant"} and content:
                recent_text.append(content)

        if not recent_text:
            return None, 0.0

        history_blob = self._normalize(" ".join(recent_text))
        return self._detect_request_type(history_blob)

    def _build_rule_response(self, intent: str, request_type: Optional[str], confidence: float) -> str:
        if request_type and confidence >= 0.25:
            template = self.templates[request_type]
            title = self._title_from_request_type(request_type)
            required = self._extract_doc_names(template.required)
            optional = self._extract_doc_names(template.optional)

            if intent == "fee":
                fee = f"{template.fee:.2f} EUR" if template.fee is not None else "nije definisana"
                payment_info = self._extract_payment_info(template.instructions)
                payment_line = f"- Uplata: {payment_info}\n" if payment_info else ""
                return (
                    f"### {title}\n"
                    f"- Taksa: {fee}\n"
                    f"- Procijenjeni rok: {template.days if template.days is not None else 'n/a'} dana\n"
                    f"{payment_line}"
                    "- Za podnosenje idite na sekciju 'Podnesi zahtjev'."
                )

            if intent == "timeline":
                return (
                    f"### {title}\n"
                    f"- Procijenjeni rok obrade: {template.days if template.days is not None else 'n/a'} dana\n"
                    "- Status pratite kroz sekciju 'Moji zahtjevi'."
                )

            response = [f"### {title}", "", "**Obavezni dokumenti:**"]
            response.extend([f"- {doc}" for doc in required] or ["- Nema definisanih stavki."])
            if optional:
                response.append("")
                response.append("**Opcioni dokumenti:**")
                response.extend([f"- {doc}" for doc in optional])
            response.append("")
            response.append(f"- Procijenjeni rok: {template.days if template.days is not None else 'n/a'} dana")
            if template.fee is not None:
                response.append(f"- Taksa: {template.fee:.2f} EUR")
            response.append("- Podnosenje: sekcija 'Podnesi zahtjev'.")
            return "\n".join(response)

        if intent == "status_tracking":
            return (
                "Status zahtjeva pratite u sekciji **Moji zahtjevi**.\n"
                "Tamo vidite tranzicije statusa, komentare službenika i audit trail."
            )

        return (
            "Mogu pomoći za ličnu kartu, pasoš, vozačku dozvolu i turizam.\n"
            "Pitaj me za dokumente, takse, rokove ili status zahtjeva.\n"
            "Primjer pitanja: 'Šta mi treba za pasoš?', 'Kolika je taksa za ličnu kartu?', "
            "'Kako pratim status zahtjeva?'."
        )

    def _build_llm_messages(
        self,
        user_query: str,
        intent: str,
        request_type: Optional[str],
        context_text: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        system_prompt = (
            "Ti si AI asistent za DMS portal javnih usluga. "
            "Odgovaraj kratko, jasno i praktično na jeziku korisnika. "
            "Ako podatak nije u kontekstu, reci da nije dostupan umjesto da izmišljaš. "
            "Uvijek navedi konkretan sljedeći korak u portalu."
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in (chat_history or [])[-6:]:
            role = item.get("role")
            content = item.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

        messages.append(
            {
                "role": "user",
                "content": (
                    f"Pitanje korisnika: {user_query}\n\n"
                    f"Intent: {intent}\n"
                    f"Detektovani tip zahtjeva: {request_type or 'nije detektovan'}\n"
                    f"Kontekst iz DMS sablona:\n{context_text or 'nema dodatnog konteksta'}"
                ),
            }
        )
        return messages

    def _generate_llm_answer(
        self,
        user_query: str,
        intent: str,
        request_type: Optional[str],
        context_text: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None

        try:
            from openai import OpenAI

            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            client = OpenAI(api_key=api_key)
            messages = self._build_llm_messages(
                user_query=user_query,
                intent=intent,
                request_type=request_type,
                context_text=context_text,
                chat_history=chat_history,
            )

            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2,
            )

            text = completion.choices[0].message.content if completion.choices else ""
            return (text or "").strip() or None
        except Exception:
            logger.exception("LLM response generation failed")
            return None

    def process_user_query(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        answer, _ = self.process_user_query_with_source(query, chat_history=chat_history)
        return answer

    def process_user_query_with_source(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, str]:
        normalized_query = self._normalize(query)
        intent = self._detect_intent(normalized_query)
        request_type, confidence = self._detect_request_type(normalized_query)

        if not request_type or confidence < 0.25:
            history_request_type, history_confidence = self._infer_request_type_from_history(chat_history)
            if history_request_type and history_confidence >= 0.25:
                request_type = history_request_type
                confidence = max(confidence, history_confidence)

        context_text = self._build_context(request_type)

        llm_answer = self._generate_llm_answer(
            user_query=query,
            intent=intent,
            request_type=request_type,
            context_text=context_text,
            chat_history=chat_history,
        )
        if llm_answer:
            return llm_answer, "llm"

        return self._build_rule_response(intent, request_type, confidence), "fallback"


def enhance_chatbot_with_dms(original_response: str, dms_context: str) -> str:
    if dms_context and len(dms_context) > 10:
        return f"{original_response}\n\n---\n\nDodatne informacije iz DMS sistema:\n{dms_context}"
    return original_response


def get_dms_aware_response(
    user_message: str,
    db_session,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    assistant = DmsAiAssistant(db_session)
    return assistant.process_user_query(user_message, chat_history=chat_history)


def get_dms_aware_response_with_source(
    user_message: str,
    db_session,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> Tuple[str, str]:
    assistant = DmsAiAssistant(db_session)
    return assistant.process_user_query_with_source(user_message, chat_history=chat_history)
