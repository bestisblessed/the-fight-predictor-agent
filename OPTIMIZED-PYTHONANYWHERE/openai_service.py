import json
import re
from pathlib import Path
from typing import Any

import openai


LOCAL_FUZZY_NOTE = "I found this in local data after fuzzy lookup."
WEB_FALLBACK_NOTE = "Local dataset was missing/ambiguous, so I used web sources; confidence lower."
UNRESOLVED_NOTE = "Local dataset and web lookup were incomplete, so this is best-effort with lower confidence."

SYSTEM_PROMPT = """You are The Fight Agent, an expert MMA handicapper replying on X.

Write one direct fight prediction reply. If local MMA context is provided, anchor the answer in it.

For detailed matchup requests, include:
- Official pick
- Method and round/time
- Confidence
- Recent form
- Style matchup
- Finish profile
- Key uncertainty

Do not say the dataset is missing if any local context is provided. If a source note is provided, include it exactly once near the top. For detailed requests, do not compress the answer into a short tweet; write a full natural analysis with enough specifics to justify the pick. Use plain text; do not use markdown bold, markdown tables, or code fences.
"""

CODE_INTERPRETER_RESOLVER_PROMPT = """Use Python/pandas and the attached CSV files to resolve MMA fighter names from the request.

Rules:
- Inspect fighter_info.csv first, then event_data_sherdog.csv.
- Handle misspellings, alternate order, punctuation, nicknames, and common transliterations.
- Do not invent fighters that are not supported by the files.
- Return JSON only, with this schema:
{
  "matched_fighters": ["Canonical Fighter One", "Canonical Fighter Two"],
  "complete": true,
  "confidence": 0.0,
  "context_text": "compact local data context with records, finish profile, and recent fights",
  "notes": "brief explanation of fuzzy lookup"
}
- Set complete to true only when two matchup fighters are resolved from local files.

Request:
"""


class OpenAIResponder:
    def __init__(
        self,
        api_key: str,
        model: str,
        max_output_tokens: int,
        timeout_seconds: int,
        reply_char_limit: int,
        escalation_model: str | None = None,
        data_file_paths: list[Path] | None = None,
        file_cache_path: Path | None = None,
    ):
        self.client = openai.OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model
        self.escalation_model = escalation_model or model
        self.max_output_tokens = max_output_tokens
        self.reply_char_limit = reply_char_limit
        self.data_file_paths = data_file_paths or []
        self.file_cache_path = file_cache_path

    def generate_reply(
        self,
        tweet_text: str,
        context_text: str,
        context_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context_payload = context_payload or {}
        matched_fighters = context_payload.get("matched_fighters") or []
        effective_context = context_text
        source_note = ""
        model_used = self.model
        response_id = None
        resolution_source = context_payload.get("resolution_source") or "local"

        if len(matched_fighters) < 2:
            code_result = self._resolve_with_code_interpreter(tweet_text)
            if code_result and code_result.get("complete") and len(code_result.get("matched_fighters", [])) >= 2:
                effective_context = str(code_result.get("context_text") or context_text)
                matched_fighters = code_result.get("matched_fighters", matched_fighters)
                source_note = LOCAL_FUZZY_NOTE
                model_used = self.escalation_model
                resolution_source = "code_interpreter"
            else:
                web_result = self._generate_web_fallback(tweet_text, context_text, code_result)
                if web_result:
                    return web_result
                source_note = UNRESOLVED_NOTE
                resolution_source = "best_effort"

        response = self._create_text_response(
            tweet_text=tweet_text,
            context_text=effective_context,
            source_note=source_note,
            model=model_used,
        )
        response_id = getattr(response, "id", None)
        raw_text = extract_text(response)
        final_text = trim_reply_text(ensure_source_note(raw_text, source_note), self.reply_char_limit)
        if not final_text:
            raise ValueError("OpenAI returned an empty reply")
        return {
            "text": final_text,
            "response_id": response_id,
            "model": model_used,
            "matched_fighters": matched_fighters,
            "resolution_source": resolution_source,
        }

    def _create_text_response(
        self,
        tweet_text: str,
        context_text: str,
        source_note: str,
        model: str,
    ) -> Any:
        user_prompt = (
            f"Incoming mention/thread text:\n{tweet_text}\n\n"
            f"Local MMA context:\n{context_text}\n\n"
            f"Source note to include exactly once if non-empty:\n{source_note}\n\n"
            "Write the exact X reply text only."
        )
        return self.client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": user_prompt}],
            max_output_tokens=self.max_output_tokens,
            store=False,
        )

    def _resolve_with_code_interpreter(self, tweet_text: str) -> dict[str, Any] | None:
        file_ids = self._dataset_file_ids()
        if not file_ids:
            return None

        for _ in range(2):
            try:
                response = self.client.responses.create(
                    model=self.escalation_model,
                    instructions="You resolve MMA fighter names by inspecting local CSV data with Python. Return JSON only.",
                    input=CODE_INTERPRETER_RESOLVER_PROMPT + tweet_text,
                    tools=[
                        {
                            "type": "code_interpreter",
                            "container": {
                                "type": "auto",
                                "file_ids": file_ids,
                            },
                        }
                    ],
                    tool_choice="required",
                    max_output_tokens=min(self.max_output_tokens, 1200),
                    store=False,
                )
            except Exception:
                continue

            payload = parse_json_object(extract_text(response))
            if isinstance(payload, dict):
                return payload
        return None

    def _generate_web_fallback(
        self,
        tweet_text: str,
        context_text: str,
        code_result: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        prompt = (
            f"Incoming mention/thread text:\n{tweet_text}\n\n"
            f"Local MMA context attempt:\n{context_text}\n\n"
            f"Code Interpreter local resolver result:\n{json.dumps(code_result or {}, ensure_ascii=True)}\n\n"
            f"Use web search because local data was incomplete. Include this exact disclosure once: {WEB_FALLBACK_NOTE}\n"
            "Pick a specific relevant MMA matchup from current web results, cite sources, and include winner, method/round, confidence, and reasoning."
        )
        try:
            response = self.client.responses.create(
                model=self.escalation_model,
                instructions=SYSTEM_PROMPT,
                input=[{"role": "user", "content": prompt}],
                tools=[{"type": "web_search"}],
                tool_choice="required",
                max_output_tokens=self.max_output_tokens,
                store=False,
            )
        except Exception:
            return None

        text = extract_text(response)
        citations = extract_url_citations(response)
        final_text = format_web_fallback_reply(text, citations, self.reply_char_limit)
        if not final_text:
            return None
        return {
            "text": final_text,
            "response_id": getattr(response, "id", None),
            "model": self.escalation_model,
            "citations": citations,
            "resolution_source": "web",
        }

    def _dataset_file_ids(self) -> list[str]:
        cache = self._load_file_cache()
        file_ids: list[str] = []
        changed = False

        for path in self.data_file_paths:
            if not path.exists():
                continue
            stat = path.stat()
            cache_key = path.name
            cached = cache.get(cache_key) if isinstance(cache, dict) else None
            if (
                isinstance(cached, dict)
                and cached.get("size") == stat.st_size
                and cached.get("mtime_ns") == stat.st_mtime_ns
                and self._openai_file_exists(str(cached.get("file_id") or ""))
            ):
                file_ids.append(str(cached["file_id"]))
                continue

            try:
                with path.open("rb") as handle:
                    uploaded = self.client.files.create(file=handle, purpose="assistants")
            except Exception:
                continue

            file_id = str(getattr(uploaded, "id", "") or "").strip()
            if not file_id:
                continue
            file_ids.append(file_id)
            cache[cache_key] = {
                "file_id": file_id,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
            changed = True

        if changed:
            self._save_file_cache(cache)
        return file_ids

    def _openai_file_exists(self, file_id: str) -> bool:
        if not file_id:
            return False
        try:
            self.client.files.retrieve(file_id)
            return True
        except Exception:
            return False

    def _load_file_cache(self) -> dict[str, Any]:
        if not self.file_cache_path or not self.file_cache_path.exists():
            return {}
        try:
            return json.loads(self.file_cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_file_cache(self, cache: dict[str, Any]) -> None:
        if not self.file_cache_path:
            return
        try:
            self.file_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.file_cache_path.write_text(
                json.dumps(cache, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return


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


def ensure_source_note(text: str, source_note: str) -> str:
    normalized = normalize_reply_text(text)
    if not source_note or source_note in normalized:
        return normalized
    return f"{source_note} {normalized}".strip()


def format_web_fallback_reply(text: str, citations: list[str], max_chars: int) -> str:
    with_note = ensure_source_note(text, WEB_FALLBACK_NOTE)
    unique_citations = unique_urls(citations)
    if unique_citations:
        with_note = f"{with_note} Sources: {' '.join(unique_citations[:3])}"
    return trim_reply_text(with_note, max_chars)


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


def parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_url_citations(response: Any) -> list[str]:
    payload = response_to_plain_data(response)
    urls: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "url_citation":
                url = value.get("url") or (value.get("url_citation") or {}).get("url")
                if url:
                    urls.append(str(url))
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(payload)
    return unique_urls(urls)


def response_to_plain_data(response: Any) -> Any:
    if hasattr(response, "model_dump"):
        try:
            return response.model_dump()
        except Exception:
            pass
    if isinstance(response, (dict, list, str, int, float, bool)) or response is None:
        return response
    if hasattr(response, "__dict__"):
        return {
            key: response_to_plain_data(value)
            for key, value in vars(response).items()
            if not key.startswith("_")
        }
    return str(response)


def unique_urls(urls: list[str]) -> list[str]:
    unique = []
    seen = set()
    for url in urls:
        normalized = str(url).strip()
        if not normalized or normalized in seen:
            continue
        unique.append(normalized)
        seen.add(normalized)
    return unique
