import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from src.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Você é um classificador de intenções para uma clínica de estética.\n"
    "Responda SOMENTE com JSON válido, sem markdown.\n\n"
    "Intenções: schedule, reschedule, cancel, faq, human, greeting, price_inquiry, unknown\n\n"
    'JSON: {"intent":"...","confidence":"high|low","areas":[...],"faq_topic":"...","service":"..."}\n\n'
    '- "areas": áreas corporais mencionadas (ex: ["buço","rosto","axila"])\n'
    '- "faq_topic": pergunta do cliente se intent=faq ou price_inquiry\n'
    '- "price_inquiry": pergunta sobre valor/preço de área específica\n'
    '- Se não tiver certeza, use "unknown"'
)


@dataclass
class ClassificationResult:
    intent: str = "unknown"          # schedule | reschedule | cancel | faq | human | greeting | price_inquiry | unknown
    confidence: str = "low"          # high | low
    areas: List[str] = field(default_factory=list)
    faq_topic: str = ""
    service: str = ""


class IntentClassifier:

    def __init__(self, openai_service: OpenAIService):
        self.openai = openai_service

    def classify(self, text: str, current_state: str, available_button_labels: list) -> ClassificationResult:
        user_message = (
            f"Estado: {current_state}\n"
            f"Opções: {', '.join(available_button_labels)}\n"
            f'Mensagem: "{text}"'
        )

        try:
            response = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
                max_tokens=150,
            )

            content = response["choices"][0]["message"]["content"].strip()
            logger.info(f"[IntentClassifier] Raw response: {content}")

            data = json.loads(content)
            return ClassificationResult(
                intent=data.get("intent", "unknown"),
                confidence=data.get("confidence", "low"),
                areas=data.get("areas", []),
                faq_topic=data.get("faq_topic", ""),
                service=data.get("service", ""),
            )
        except Exception as e:
            logger.warning(f"[IntentClassifier] Classification failed: {e}")
            return ClassificationResult(intent="unknown")
