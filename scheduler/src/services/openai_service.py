import os
import time
import logging

import requests

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIService:

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("[OpenAIService] OPENAI_API_KEY not set")

    def chat_completion(
        self,
        messages: list,
        tools: list = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> dict:
        """
        Call OpenAI chat completions API with optional function calling (tools).

        Returns the parsed JSON response dict.
        Retries up to 3 times on 429/5xx with exponential backoff.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    OPENAI_API_URL, headers=headers, json=payload, timeout=30
                )

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429 or response.status_code >= 500:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        f"[OpenAIService] API error (status {response.status_code}), "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue

                # Client error (4xx, not 429) — don't retry
                logger.error(
                    f"[OpenAIService] API error {response.status_code}: {response.text[:500]}"
                )
                raise OpenAIError(
                    f"OpenAI API error {response.status_code}: {response.text[:200]}"
                )

            except requests.exceptions.Timeout:
                wait_time = 2 ** (attempt + 1)
                logger.warning(
                    f"[OpenAIService] Request timeout, retrying in {wait_time}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
            except OpenAIError:
                raise
            except requests.exceptions.RequestException as e:
                logger.error(f"[OpenAIService] Request exception: {e}")
                raise OpenAIError(f"OpenAI request failed: {e}")

        raise OpenAIError(
            f"OpenAI API failed after {max_retries} retries"
        )


class OpenAIError(Exception):
    pass
