import argparse
import json
from pathlib import Path
from typing import Any

from service import FightAgentRuntime, RuntimeBundle, build_runtime_bundle
from settings import Config


POLL_STATE_FILENAME = "poll_state.json"


def load_poll_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_poll_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mention_to_event_payload(
    mention: dict[str, Any],
    bot_user_id: str,
    includes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tweet_id = str(mention.get("id") or "").strip()
    author_id = str(mention.get("author_id") or "").strip()
    text = str(mention.get("text") or "").strip()
    entities = mention.get("entities") if isinstance(mention.get("entities"), dict) else {}

    user_mentions = []
    for item in entities.get("mentions", []) or []:
        if not isinstance(item, dict):
            continue
        username = item.get("username") or item.get("screen_name")
        if username:
            user_mentions.append({"screen_name": str(username)})

    event = {
        "id": tweet_id,
        "id_str": tweet_id,
        "text": text,
        "full_text": text,
        "created_at": mention.get("created_at"),
        "user": {
            "id": author_id,
            "id_str": author_id,
        },
        "entities": {
            "user_mentions": user_mentions,
        },
        "referenced_tweets": mention.get("referenced_tweets") or [],
    }

    payload: dict[str, Any] = {
        "for_user_id": str(bot_user_id),
        "tweet_create_events": [event],
    }

    included_tweets = (includes or {}).get("tweets") or []
    tweets_by_id = {}
    for tweet in included_tweets:
        if not isinstance(tweet, dict):
            continue
        included_id = str(tweet.get("id") or tweet.get("id_str") or "").strip()
        if included_id:
            tweets_by_id[included_id] = tweet
    if tweets_by_id:
        payload["tweets"] = tweets_by_id

    return payload


def poll_once(
    config: Config,
    runtime: RuntimeBundle | FightAgentRuntime | None = None,
    max_results: int = 100,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    runtime_bundle = _runtime_bundle(config, runtime)
    state = runtime_bundle.state
    x_client = runtime_bundle.x_client
    bot_user_id = _resolve_bot_user_id(config, runtime_bundle)

    state_path = config.logs_dir / POLL_STATE_FILENAME
    poll_state = load_poll_state(state_path)
    since_id = str(poll_state.get("since_id") or "").strip() or None

    mentions, newest_id = _fetch_mentions(
        x_client=x_client,
        bot_user_id=bot_user_id,
        since_id=since_id,
        max_results=max_results,
        fetch_limit=limit,
    )
    mentions = _oldest_first(mentions)
    if limit is not None:
        mentions = mentions[: max(0, int(limit))]

    processed_count = 0
    processed_ids = []
    for mention, includes in mentions:
        tweet_id = str(mention.get("id") or "").strip()
        if not tweet_id:
            continue
        event_key = f"{bot_user_id}:{tweet_id}"
        if state.is_processed(event_key):
            continue
        if str(mention.get("author_id") or "").strip() == bot_user_id:
            if not dry_run:
                payload = mention_to_event_payload(mention, bot_user_id, includes)
                runtime_bundle.processor.process_inbox_record({"payload": payload}, source="poll-mentions")
            continue

        if not dry_run:
            payload = mention_to_event_payload(mention, bot_user_id, includes)
            runtime_bundle.processor.process_inbox_record({"payload": payload}, source="poll-mentions")
            if not state.is_processed(event_key):
                raise RuntimeError(f"Mention {tweet_id} was not fully processed; leaving since_id unchanged")
        processed_count += 1
        processed_ids.append(tweet_id)

    if not dry_run:
        next_since_id = _max_tweet_id(processed_ids) or newest_id
        if next_since_id:
            save_poll_state(state_path, {"since_id": next_since_id})

    return {
        "bot_user_id": bot_user_id,
        "since_id": since_id,
        "newest_id": newest_id,
        "fetched_mentions": len(mentions),
        "processed_mentions": processed_count,
        "dry_run": dry_run,
    }


def _runtime_bundle(
    config: Config,
    runtime: RuntimeBundle | FightAgentRuntime | None,
) -> RuntimeBundle:
    if runtime is None:
        return build_runtime_bundle(config)
    if isinstance(runtime, RuntimeBundle):
        return runtime
    return runtime.bundle


def _resolve_bot_user_id(config: Config, runtime: RuntimeBundle) -> str:
    webhook_config = runtime.state.load_webhook_config()
    bot_user_id = str(webhook_config.get("bot_user_id") or "").strip()
    if not bot_user_id:
        response = runtime.x_client.get_user_by_username(config.bot_handle)
        user = response.get("data", {}) if isinstance(response, dict) else {}
        bot_user_id = str(user.get("id") or "").strip()
        if not bot_user_id:
            raise RuntimeError(f"Could not resolve bot user id for @{config.bot_handle}")
        runtime.state.save_webhook_config(
            {
                "bot_username": user.get("username") or config.bot_handle,
                "bot_user_id": bot_user_id,
            }
        )
    runtime.processor.bot_user_id = bot_user_id
    return bot_user_id


def _fetch_mentions(
    x_client: Any,
    bot_user_id: str,
    since_id: str | None,
    max_results: int,
    fetch_limit: int | None = None,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], str | None]:
    mentions = []
    newest_id = None
    pagination_token = None

    while True:
        response = x_client.get_mentions(
            bot_user_id,
            since_id=since_id,
            pagination_token=pagination_token,
            max_results=max_results,
        )
        meta = response.get("meta", {}) if isinstance(response, dict) else {}
        if meta.get("newest_id"):
            newest_id = _max_tweet_id([newest_id, str(meta["newest_id"])])
        includes = response.get("includes", {}) if isinstance(response, dict) else {}
        for mention in response.get("data", []) or []:
            if isinstance(mention, dict):
                mentions.append((mention, includes))
        if fetch_limit is not None and len(mentions) >= fetch_limit:
            break
        pagination_token = meta.get("next_token")
        if not pagination_token:
            break

    return mentions, newest_id


def _oldest_first(
    mentions: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return sorted(mentions, key=lambda item: int(str(item[0].get("id") or "0")))


def _max_tweet_id(tweet_ids: list[str | None]) -> str | None:
    values = [str(tweet_id).strip() for tweet_id in tweet_ids if tweet_id]
    if not values:
        return None
    return max(values, key=lambda value: int(value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll X mentions and reply to new requests")
    parser.add_argument("--dry-run", action="store_true", help="Fetch mentions without replying or updating poll state")
    parser.add_argument("--limit", type=int, default=None, help="Maximum mentions to process this run")
    parser.add_argument("--max-results", type=int, default=100, help="X mentions page size, 5-100")
    args = parser.parse_args()

    config = Config.from_env()
    config.require_runtime()
    summary = poll_once(
        config,
        max_results=args.max_results,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
