import argparse
import json

from settings import Config
from storage import StateStore
from service import FightAgentRuntime, build_runtime_bundle, retry_failed_jobs
from x_api import XApiClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Admin CLI for the OPTIMIZED webhook agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("resolve-bot-user", help="Resolve BOT_USERNAME to a user id and persist it")
    subparsers.add_parser("create-webhook", help="Create a webhook using PUBLIC_BASE_URL/x/webhook")
    subparsers.add_parser("validate-webhook", help="Trigger a CRC validation for the persisted webhook")
    subparsers.add_parser("subscribe", help="Subscribe the user to account activity for the persisted webhook")
    subparsers.add_parser("check-subscription", help="Check the persisted webhook subscription")
    subparsers.add_parser("list-subscriptions", help="List all subscriptions for the persisted webhook")

    replay_parser = subparsers.add_parser("replay", help="Request a webhook replay job")
    replay_parser.add_argument("--from-date", required=True, help="UTC start in yyyymmddhhmm")
    replay_parser.add_argument("--to-date", required=True, help="UTC end in yyyymmddhhmm")

    retry_parser = subparsers.add_parser("retry-failed", help="Retry failed retryable jobs from state/failed_jobs.jsonl")
    retry_parser.add_argument("--limit", type=int, default=None, help="Optional retry cap")
    return parser


def load_webhook_id(config: Config) -> str:
    webhook_id = str((StateStore(config.state_dir).load_webhook_config().get("webhook_id") or "")).strip()
    if not webhook_id:
        raise RuntimeError("webhook_id is not set. Run create-webhook first.")
    return webhook_id


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = Config.from_env()
    config.ensure_directories()

    if args.command == "retry-failed":
        config.require_runtime()
        runtime = FightAgentRuntime(build_runtime_bundle(config), start_worker=False)
        retried = retry_failed_jobs(runtime, limit=args.limit)
        print(json.dumps({"retried_event_keys": retried}, indent=2))
        return

    config.require_x_admin()
    state = StateStore(config.state_dir)
    x_client = XApiClient(config)

    if args.command == "resolve-bot-user":
        response = x_client.get_user_by_username(config.bot_handle)
        user = response.get("data", {})
        persisted = state.save_webhook_config(
            {
                "bot_username": user.get("username") or config.bot_handle,
                "bot_user_id": str(user.get("id", "")),
            }
        )
        print(json.dumps({"response": response, "persisted": persisted}, indent=2))
        return

    if args.command == "create-webhook":
        response = x_client.create_webhook(config.webhook_url)
        data = response.get("data", {})
        persisted = state.save_webhook_config(
            {
                "webhook_id": str(data.get("id", "")),
                "webhook_url": data.get("url") or config.webhook_url,
            }
        )
        print(json.dumps({"response": response, "persisted": persisted}, indent=2))
        return

    webhook_id = load_webhook_id(config)

    if args.command == "validate-webhook":
        print(json.dumps(x_client.validate_webhook(webhook_id), indent=2))
        return

    if args.command == "subscribe":
        print(json.dumps(x_client.subscribe(webhook_id), indent=2))
        return

    if args.command == "check-subscription":
        print(json.dumps(x_client.check_subscription(webhook_id), indent=2))
        return

    if args.command == "list-subscriptions":
        print(json.dumps(x_client.list_subscriptions(webhook_id), indent=2))
        return

    if args.command == "replay":
        print(json.dumps(x_client.replay(webhook_id, args.from_date, args.to_date), indent=2))
        return

    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
