import os
import random
import time
import logging

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicService:

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("[AnthropicService] ANTHROPIC_API_KEY not set")

    def create_message(
        self,
        system,
        messages,
        tools=None,
        model="claude-sonnet-4-20250514",
        temperature=0.7,
        max_tokens=1024,
    ):
        """
        Call Anthropic Messages API with optional tool use.

        Returns the parsed JSON response dict.
        Retries up to 5 times on 429/5xx with exponential backoff (3s base).
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools

        max_retries = 5

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    ANTHROPIC_API_URL, headers=headers, json=payload, timeout=25
                )

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429 or response.status_code >= 500:
                    # Honor Retry-After when the API provides it (429 / 503).
                    # Otherwise use decorrelated jitter: random in [base, prev*3]
                    # capped at 60s. With many parallel Lambdas hitting the same
                    # rate limit, jitter desynchronizes retries instead of
                    # creating retry waves that all hit 429 again.
                    retry_after = response.headers.get("retry-after")
                    if retry_after:
                        try:
                            wait_time = min(float(retry_after), 60.0)
                        except ValueError:
                            wait_time = min(2.0 * (3 ** attempt), 60.0)
                    else:
                        base = 2.0
                        wait_time = min(random.uniform(base, base * (3 ** (attempt + 1))), 60.0)
                    logger.warning(
                        f"[AnthropicService] API error (status {response.status_code}), "
                        f"retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue

                logger.error(
                    f"[AnthropicService] API error {response.status_code}: {response.text[:500]}"
                )
                raise AnthropicError(
                    f"Anthropic API error {response.status_code}: {response.text[:200]}"
                )

            except requests.exceptions.Timeout:
                wait_time = min(random.uniform(2.0, 2.0 * (3 ** (attempt + 1))), 60.0)
                logger.warning(
                    f"[AnthropicService] Request timeout, retrying in {wait_time:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
            except AnthropicError:
                raise
            except requests.exceptions.RequestException as e:
                logger.error(f"[AnthropicService] Request exception: {e}")
                raise AnthropicError(f"Anthropic request failed: {e}")

        raise AnthropicError(
            f"Anthropic API failed after {max_retries} retries"
        )


class AnthropicError(Exception):
    pass
