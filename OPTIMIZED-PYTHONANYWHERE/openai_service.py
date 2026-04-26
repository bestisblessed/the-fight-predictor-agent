import re
from typing import Any

import openai


SYSTEM_PROMPT = """You are The Fight Agent, a sharp MMA betting analyst replying on X.

Rules:
- Return one final reply only.
- Keep it decisive, concise, and under 260 characters.
- Use the provided MMA context when available.
- If the context is incomplete, say that briefly and do not invent facts.
- No markdown bullets, no hashtags unless the user used one, and no quoted wrapper text.
"""


class OpenAIResponder:
    def __init__(
        self,
        api_key: str,
        model: str,
        max_output_tokens: int,
        timeout_seconds: int,
        reply_char_limit: int,
    ):
        self.client = openai.OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.reply_char_limit = reply_char_limit

    def generate_reply(self, tweet_text: str, context_text: str) -> dict[str, Any]:
        user_prompt = (
            f"Incoming mention:\n{tweet_text}\n\n"
            f"Local MMA context:\n{context_text}\n\n"
            "Write the exact X reply text only."
        )
        response = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": user_prompt}],
            max_output_tokens=self.max_output_tokens,
            store=False,
        )
        raw_text = extract_text(response)
        final_text = trim_reply_text(raw_text, self.reply_char_limit)
        if not final_text:
            raise ValueError("OpenAI returned an empty reply")
        return {
            "text": final_text,
            "response_id": getattr(response, "id", None),
            "model": self.model,
        }


def extract_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return normalize_reply_text(output_text)

    for output_item in getattr(response, "output", []) or []:
        if getattr(output_item, "type", None) != "message":
            continue
        for content_block in getattr(output_item, "content", []) or []:
            text = getattr(content_block, "text", None)
            if text:
                return normalize_reply_text(text if isinstance(text, str) else str(text))
    return ""


def normalize_reply_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text or "").strip()
    return collapsed


def trim_reply_text(text: str, max_chars: int) -> str:
    normalized = normalize_reply_text(text)
    if len(normalized) <= max_chars:
        return normalized
    if max_chars <= 3:
        return normalized[:max_chars]
    trimmed = normalized[: max_chars - 3].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0].rstrip()
    if not trimmed:
        trimmed = normalized[: max_chars - 3]
    return trimmed + "..."
