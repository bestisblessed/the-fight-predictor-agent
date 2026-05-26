import json
from pathlib import Path
from threading import Lock
from typing import Any, Iterable


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.lock = Lock()
        self.webhook_config_path = self.state_dir / "webhook_config.json"
        self.events_inbox_path = self.state_dir / "events_inbox.jsonl"
        self.processed_ids_path = self.state_dir / "processed_event_ids.jsonl"
        self.replies_path = self.state_dir / "replies.jsonl"
        self.failed_jobs_path = self.state_dir / "failed_jobs.jsonl"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        for path in [
            self.events_inbox_path,
            self.processed_ids_path,
            self.replies_path,
            self.failed_jobs_path,
        ]:
            path.touch(exist_ok=True)
        self.processed_ids = self._load_processed_ids()

    def _load_processed_ids(self) -> set[str]:
        processed = set()
        for record in read_jsonl(self.processed_ids_path):
            event_key = record.get("event_key")
            if event_key:
                processed.add(str(event_key))
        return processed

    def is_processed(self, event_key: str) -> bool:
        return event_key in self.processed_ids

    def mark_processed(self, event_key: str, tweet_id: str, reason: str) -> None:
        with self.lock:
            if event_key in self.processed_ids:
                return
            self.processed_ids.add(event_key)
            append_jsonl(
                self.processed_ids_path,
                {
                    "event_key": event_key,
                    "tweet_id": tweet_id,
                    "reason": reason,
                    "recorded_at": utc_now_iso(),
                },
            )

    def append_inbox_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "received_at": utc_now_iso(),
            "payload": payload,
        }
        with self.lock:
            append_jsonl(self.events_inbox_path, record)
        return record

    def record_reply(self, record: dict[str, Any]) -> None:
        with self.lock:
            append_jsonl(self.replies_path, record)

    def record_failure(self, record: dict[str, Any]) -> None:
        with self.lock:
            append_jsonl(self.failed_jobs_path, record)

    def load_webhook_config(self) -> dict[str, Any]:
        if not self.webhook_config_path.exists():
            return {}
        try:
            return json.loads(self.webhook_config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def save_webhook_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            current = self.load_webhook_config()
            current.update(updates)
            current["updated_at"] = utc_now_iso()
            self.webhook_config_path.write_text(
                json.dumps(current, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return current

    def iter_inbox_records(self) -> Iterable[dict[str, Any]]:
        return read_jsonl(self.events_inbox_path)

    def iter_failures(self) -> Iterable[dict[str, Any]]:
        return read_jsonl(self.failed_jobs_path)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError:
                continue
