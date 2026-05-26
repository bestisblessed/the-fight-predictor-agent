import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

from context_builder import MmaContextBuilder, normalize_text
from mention_scope import SCOPE_REPLY_ACTION, SCOPE_REPLY_TEXT, classify_mention_scope
from openai_service import OpenAIResponder
from settings import Config
from storage import StateStore, utc_now_iso
from x_api import XApiClient


FOLLOW_UP_RE = re.compile(
    r"\b(originally|you have access|find it|proceed|what i asked|same fight|same matchup|"
    r"that fight|this fight|that matchup|this matchup|in your datasets|somewhere in your data)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class RuntimeBundle:
    config: Config
    state: StateStore
    context_builder: MmaContextBuilder
    responder: Any
    x_client: Any
    processor: "EventProcessor"


class EventProcessor:
    def __init__(
        self,
        config: Config,
        state: StateStore,
        context_builder: MmaContextBuilder,
        responder: Any,
        x_client: Any,
    ):
        self.config = config
        self.state = state
        self.context_builder = context_builder
        self.responder = responder
        self.x_client = x_client
        webhook_config = self.state.load_webhook_config()
        self.bot_user_id = str(webhook_config.get("bot_user_id", "")).strip()
        self.bot_handle = config.bot_handle.lower()

    def process_inbox_record(self, record: dict[str, Any], source: str = "webhook") -> None:
        payload = record.get("payload", {})
        for event in payload.get("tweet_create_events", []) or []:
            self.process_tweet_event(payload, event, source=source)

    def extract_unprocessed_event_keys(self, record: dict[str, Any]) -> list[str]:
        payload = record.get("payload", {})
        event_keys = []
        for event in payload.get("tweet_create_events", []) or []:
            tweet_id = self._tweet_id(event)
            if not tweet_id:
                continue
            event_key = self._event_key(payload, tweet_id)
            if not self.state.is_processed(event_key):
                event_keys.append(event_key)
        return event_keys

    def process_tweet_event(self, payload: dict[str, Any], event: dict[str, Any], source: str) -> None:
        tweet_id = self._tweet_id(event)
        if not tweet_id:
            return

        event_key = self._event_key(payload, tweet_id)
        if self.state.is_processed(event_key):
            return

        author_id = self._author_id(payload, event)
        tweet_text = self._tweet_text(event)

        if self.bot_user_id and author_id == self.bot_user_id:
            self.state.mark_processed(event_key, tweet_id, "self_authored")
            return

        if not self._is_directed_at_bot(event, tweet_text):
            self.state.mark_processed(event_key, tweet_id, "not_directed_at_bot")
            return

        analysis_text = self._analysis_text(payload, event, tweet_text)
        scope_matches = self.context_builder.match_fighters(analysis_text, limit=2)
        scope_decision = classify_mention_scope(
            analysis_text,
            matched_fighters=[match.fighter_name for match in scope_matches],
        )
        if scope_decision.action == SCOPE_REPLY_ACTION:
            self._send_scope_reply(
                event_key=event_key,
                tweet_id=tweet_id,
                payload=payload,
                scope_reason=scope_decision.reason,
                scope_signals=scope_decision.signals,
                source=source,
            )
            return

        context_payload = self.context_builder.build_context(analysis_text)

        try:
            openai_result = self.responder.generate_reply(
                tweet_text=analysis_text,
                context_text=context_payload["context_text"],
                context_payload=context_payload,
            )
        except ValueError as exc:
            self._record_failure(
                event_key=event_key,
                tweet_id=tweet_id,
                payload=payload,
                phase="openai",
                error=str(exc),
                retryable=False,
                source=source,
            )
            self.state.mark_processed(event_key, tweet_id, "openai_non_retryable")
            return
        except Exception as exc:
            self._record_failure(
                event_key=event_key,
                tweet_id=tweet_id,
                payload=payload,
                phase="openai",
                error=str(exc),
                retryable=True,
                source=source,
            )
            return

        try:
            reply_response = self.x_client.create_reply(tweet_id=tweet_id, text=openai_result["text"])
        except Exception as exc:
            self._record_failure(
                event_key=event_key,
                tweet_id=tweet_id,
                payload=payload,
                phase="x_post",
                error=str(exc),
                retryable=True,
                source=source,
            )
            return

        reply_id = (
            reply_response.get("data", {}).get("id")
            if isinstance(reply_response, dict)
            else None
        )

        self.state.record_reply(
            {
                "recorded_at": utc_now_iso(),
                "event_key": event_key,
                "tweet_id": tweet_id,
                "reply_id": str(reply_id) if reply_id else "",
                "reply_text": openai_result["text"],
                "matched_fighters": openai_result.get("matched_fighters")
                or context_payload["matched_fighters"],
                "resolution_source": openai_result.get("resolution_source")
                or context_payload.get("resolution_source", "local"),
                "openai_response_id": openai_result.get("response_id"),
                "model": openai_result.get("model"),
                "source": source,
            }
        )
        self.state.mark_processed(event_key, tweet_id, "replied")

    def _send_scope_reply(
        self,
        event_key: str,
        tweet_id: str,
        payload: dict[str, Any],
        scope_reason: str,
        scope_signals: list[str],
        source: str,
    ) -> None:
        try:
            reply_response = self.x_client.create_reply(tweet_id=tweet_id, text=SCOPE_REPLY_TEXT)
        except Exception as exc:
            self._record_failure(
                event_key=event_key,
                tweet_id=tweet_id,
                payload=payload,
                phase="scope_x_post",
                error=str(exc),
                retryable=False,
                source=source,
            )
            self.state.mark_processed(event_key, tweet_id, "scope_reply_failed")
            return

        reply_id = (
            reply_response.get("data", {}).get("id")
            if isinstance(reply_response, dict)
            else None
        )

        self.state.record_reply(
            {
                "recorded_at": utc_now_iso(),
                "event_key": event_key,
                "tweet_id": tweet_id,
                "reply_id": str(reply_id) if reply_id else "",
                "reply_text": SCOPE_REPLY_TEXT,
                "matched_fighters": [],
                "resolution_source": "scope_filter",
                "openai_response_id": None,
                "model": None,
                "scope_reason": scope_reason,
                "scope_signals": scope_signals,
                "source": source,
            }
        )
        self.state.mark_processed(event_key, tweet_id, "scope_replied")

    def _record_failure(
        self,
        event_key: str,
        tweet_id: str,
        payload: dict[str, Any],
        phase: str,
        error: str,
        retryable: bool,
        source: str,
    ) -> None:
        self.state.record_failure(
            {
                "recorded_at": utc_now_iso(),
                "event_key": event_key,
                "tweet_id": tweet_id,
                "phase": phase,
                "error": error,
                "retryable": retryable,
                "source": source,
                "payload": payload,
            }
        )

    def _event_key(self, payload: dict[str, Any], tweet_id: str) -> str:
        for_user_id = str(payload.get("for_user_id") or self.bot_user_id or "unknown").strip()
        return f"{for_user_id}:{tweet_id}"

    @staticmethod
    def _tweet_id(event: dict[str, Any]) -> str:
        value = event.get("id_str") or event.get("id")
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _tweet_text(event: dict[str, Any]) -> str:
        extended = event.get("extended_tweet") or {}
        return (
            str(extended.get("full_text") or event.get("full_text") or event.get("text") or "").strip()
        )

    @staticmethod
    def _author_id(payload: dict[str, Any], event: dict[str, Any]) -> str:
        user = event.get("user") or {}
        candidates = [
            user.get("id_str"),
            user.get("id"),
            event.get("user_id"),
            event.get("user", {}).get("id_str") if isinstance(event.get("user"), dict) else None,
        ]
        for candidate in candidates:
            if candidate is not None and str(candidate).strip():
                return str(candidate).strip()

        payload_users = payload.get("users") or {}
        if isinstance(payload_users, dict):
            user_id = str(event.get("user_id") or "").strip()
            if user_id and user_id in payload_users:
                nested = payload_users[user_id]
                nested_id = nested.get("id_str") or nested.get("id")
                if nested_id:
                    return str(nested_id).strip()
        return ""

    def _is_directed_at_bot(self, event: dict[str, Any], tweet_text: str) -> bool:
        if not self.bot_handle:
            return False

        mentions = (event.get("entities") or {}).get("user_mentions") or []
        for mention in mentions:
            username = str(mention.get("screen_name") or mention.get("username") or "").lower()
            if username == self.bot_handle:
                return True

        normalized_text = normalize_text(tweet_text)
        return f" {self.bot_handle.lower()} " in f" {normalized_text} "

    def _analysis_text(self, payload: dict[str, Any], event: dict[str, Any], tweet_text: str) -> str:
        current_context = self.context_builder.build_context(tweet_text)
        needs_parent = len(current_context.get("matched_fighters", [])) < 2 or self._looks_like_follow_up(tweet_text)
        if not needs_parent:
            return tweet_text

        parent_text = self._parent_tweet_text(payload, event)
        if not parent_text:
            return tweet_text
        return f"Original thread tweet:\n{parent_text}\n\nFollow-up mention:\n{tweet_text}"

    @staticmethod
    def _looks_like_follow_up(tweet_text: str) -> bool:
        return bool(FOLLOW_UP_RE.search(tweet_text or ""))

    def _parent_tweet_text(self, payload: dict[str, Any], event: dict[str, Any]) -> str:
        parent_id = self._parent_tweet_id(event)
        if not parent_id:
            return ""

        embedded_text = self._embedded_tweet_text(payload, parent_id)
        if embedded_text:
            return embedded_text

        get_tweet_text = getattr(self.x_client, "get_tweet_text", None)
        if not callable(get_tweet_text):
            return ""
        try:
            return str(get_tweet_text(parent_id) or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _parent_tweet_id(event: dict[str, Any]) -> str:
        candidates = [
            event.get("in_reply_to_status_id_str"),
            event.get("in_reply_to_status_id"),
            event.get("quoted_status_id_str"),
            event.get("quoted_status_id"),
        ]
        for referenced in event.get("referenced_tweets", []) or []:
            if not isinstance(referenced, dict):
                continue
            if referenced.get("type") in {"replied_to", "quoted"}:
                candidates.append(referenced.get("id"))
        for candidate in candidates:
            if candidate is not None and str(candidate).strip():
                return str(candidate).strip()
        return ""

    @classmethod
    def _embedded_tweet_text(cls, payload: dict[str, Any], tweet_id: str) -> str:
        for key in ("tweets", "included_tweets"):
            tweets = payload.get(key) or {}
            if isinstance(tweets, dict) and tweet_id in tweets:
                text = cls._tweet_text(tweets[tweet_id])
                if text:
                    return text
            if isinstance(tweets, list):
                for tweet in tweets:
                    if not isinstance(tweet, dict):
                        continue
                    if str(tweet.get("id_str") or tweet.get("id") or "").strip() == tweet_id:
                        text = cls._tweet_text(tweet)
                        if text:
                            return text
        return ""


class BackgroundWorker:
    def __init__(self, processor: EventProcessor):
        self.processor = processor
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="optimized-webhook-worker")

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def enqueue(self, record: dict[str, Any]) -> None:
        self._queue.put(record)

    def wait_until_idle(self, timeout: float = 5.0) -> None:
        done = threading.Event()

        def waiter() -> None:
            self._queue.join()
            done.set()

        threading.Thread(target=waiter, daemon=True).start()
        done.wait(timeout=timeout)

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                record = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                self.processor.process_inbox_record(record)
            finally:
                self._queue.task_done()


class FightAgentRuntime:
    def __init__(self, bundle: RuntimeBundle, start_worker: bool = True):
        self.bundle = bundle
        self.worker = BackgroundWorker(bundle.processor)
        if start_worker:
            self.worker.start()
            self.requeue_unprocessed_inbox()

    @property
    def state(self) -> StateStore:
        return self.bundle.state

    def enqueue_record(self, record: dict[str, Any]) -> None:
        self.worker.enqueue(record)

    def requeue_unprocessed_inbox(self) -> None:
        for record in self.state.iter_inbox_records():
            if self.bundle.processor.extract_unprocessed_event_keys(record):
                self.worker.enqueue(record)

    def health_payload(self) -> dict[str, Any]:
        config = self.bundle.state.load_webhook_config()
        return {
            "status": "ok",
            "worker_alive": self.worker.alive,
            "queue_size": self.worker.queue_size,
            "processed_count": len(self.state.processed_ids),
            "bot_user_id": config.get("bot_user_id"),
            "webhook_id": config.get("webhook_id"),
        }

    def wait_until_idle(self, timeout: float = 5.0) -> None:
        self.worker.wait_until_idle(timeout=timeout)

    def stop(self) -> None:
        self.worker.stop()


def build_runtime_bundle(
    config: Config,
    responder: Any | None = None,
    x_client: Any | None = None,
    context_builder: MmaContextBuilder | None = None,
) -> RuntimeBundle:
    config.ensure_directories()
    state = StateStore(config.state_dir)
    builder = context_builder or MmaContextBuilder(
        fighter_info_path=config.data_dir / "fighter_info.csv",
        event_data_path=config.data_dir / "event_data_sherdog.csv",
        fighter_career_dir=config.data_dir / "fighters",
        fighter_career_zip_path=config.data_dir / "fighters.zip",
    )
    openai_data_file_paths = [
        config.data_dir / "fighter_info.csv",
        config.data_dir / "event_data_sherdog.csv",
    ]
    fighters_zip_path = config.data_dir / "fighters.zip"
    if fighters_zip_path.exists():
        openai_data_file_paths.append(fighters_zip_path)
    runtime_x_client = x_client or XApiClient(config)
    runtime_responder = responder or OpenAIResponder(
        api_key=config.openai_api_key or "",
        model=config.openai_model,
        escalation_model=config.openai_escalation_model or config.openai_model,
        timeout_seconds=config.openai_timeout_seconds,
        data_file_paths=openai_data_file_paths,
        file_cache_path=config.state_dir / "openai_file_ids.json",
    )
    processor = EventProcessor(
        config=config,
        state=state,
        context_builder=builder,
        responder=runtime_responder,
        x_client=runtime_x_client,
    )
    return RuntimeBundle(
        config=config,
        state=state,
        context_builder=builder,
        responder=runtime_responder,
        x_client=runtime_x_client,
        processor=processor,
    )


def retry_failed_jobs(runtime: FightAgentRuntime, limit: int | None = None) -> list[str]:
    retried: list[str] = []
    seen = set()
    for failure in runtime.state.iter_failures():
        if not failure.get("retryable"):
            continue
        event_key = str(failure.get("event_key") or "").strip()
        if not event_key or event_key in seen or runtime.state.is_processed(event_key):
            continue
        payload = failure.get("payload")
        if not isinstance(payload, dict):
            continue
        runtime.bundle.processor.process_inbox_record({"payload": payload}, source="retry-failed")
        retried.append(event_key)
        seen.add(event_key)
        if limit is not None and len(retried) >= limit:
            break
    return retried


def run_checkpoint_worker(runtime: FightAgentRuntime) -> int:
    start_offset = runtime.state.load_worker_checkpoint()
    records, new_offset = runtime.state.read_inbox_records_from_offset(start_offset)
    processed_count = 0
    for record in records:
        if not runtime.bundle.processor.extract_unprocessed_event_keys(record):
            continue
        runtime.bundle.processor.process_inbox_record(record, source="always-on-task")
        processed_count += 1
    runtime.state.save_worker_checkpoint(new_offset)
    return processed_count


def run_worker_forever(runtime: FightAgentRuntime, sleep_seconds: float = 2.0) -> None:
    while True:
        processed_count = run_checkpoint_worker(runtime)
        if processed_count == 0:
            time.sleep(sleep_seconds)
