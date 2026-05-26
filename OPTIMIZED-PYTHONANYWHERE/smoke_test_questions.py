import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from context_builder import MmaContextBuilder
from openai_service import OpenAIResponder
from settings import ROOT_DIR


QUESTIONS = [
    (
        "local_reversed_typo",
        "@TheFightAgent Research and analyze Song Yadong vs Deiveson Figuieredo in depth. "
        "Then generate a detailed prediction with method and time of victory.",
        "local",
    ),
    (
        "local_typo",
        "@TheFightAgent Research and analyze Conor McGregor vs Mac Holloway in depth. "
        "Then generate a detailed prediction with method and time of victory.",
        "local",
    ),
    (
        "code_interpreter_forced",
        "@TheFightAgent Song Yadong vs Deiveson Figuieredo prediction?",
        "code_interpreter",
    ),
    (
        "web_forced",
        "@TheFightAgent Give me a prediction for a current MMA matchup that is not fully present in my local data.",
        "web",
    ),
]

def build_responder(data_paths: list[Path]) -> OpenAIResponder | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    return OpenAIResponder(
        api_key=api_key,
        model=model,
        escalation_model=os.getenv("OPENAI_ESCALATION_MODEL") or model,
        timeout_seconds=int(os.getenv("OPENAI_TIMEOUT_SECONDS", "45")),
        data_file_paths=data_paths,
        file_cache_path=ROOT_DIR / "state" / "openai_file_ids.json",
    )


def print_context(label: str, question: str, context_payload: dict) -> None:
    print("=" * 80)
    print(f"CASE: {label}")
    print(f"QUESTION: {question}")
    print(f"MATCHED: {context_payload.get('matched_fighters')}")
    print(f"RESOLUTION_SOURCE: {context_payload.get('resolution_source')}")
    print(f"CONTEXT_CHARS: {len(context_payload.get('context_text') or '')}")
    print("MATCH_DETAILS:")
    for detail in context_payload.get("match_details") or []:
        print(f"  - {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="No-post smoke checks for The Fight Agent")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only run deterministic local matching; do not call OpenAI even if OPENAI_API_KEY is set.",
    )
    parser.add_argument("--case", help="Run only one case label from QUESTIONS.")
    args = parser.parse_args()

    load_dotenv(ROOT_DIR / ".env", override=True)
    load_dotenv(override=True)

    data_paths = [
        ROOT_DIR / "data" / "fighter_info.csv",
        ROOT_DIR / "data" / "event_data_sherdog.csv",
    ]
    fighters_zip_path = ROOT_DIR / "data" / "fighters.zip"
    if fighters_zip_path.exists():
        data_paths.append(fighters_zip_path)
    builder = MmaContextBuilder(data_paths[0], data_paths[1])
    responder = None if args.local_only else build_responder(data_paths)
    web_only_responder = None if args.local_only else build_responder([])

    if responder is None:
        print("OpenAI calls disabled or OPENAI_API_KEY is not set. Running local matching checks only.")

    for label, question, mode in QUESTIONS:
        if args.case and args.case != label:
            continue
        context_payload = builder.build_context(question)
        if mode == "code_interpreter":
            context_payload = {
                "matched_fighters": [],
                "context_text": "Forced smoke test: skip local context so Code Interpreter must inspect CSVs.",
                "resolution_source": "forced_code_interpreter",
                "resolution_complete": False,
                "match_details": [],
            }
        elif mode == "web":
            context_payload = {
                "matched_fighters": [],
                "context_text": "Forced smoke test: no local dataset context available.",
                "resolution_source": "forced_web",
                "resolution_complete": False,
                "match_details": [],
            }

        print_context(label, question, context_payload)

        active_responder = web_only_responder if mode == "web" else responder
        if active_responder is None:
            print("REPLY: skipped because OPENAI_API_KEY is not set.")
            continue

        result = active_responder.generate_reply(
            tweet_text=question,
            context_text=context_payload["context_text"],
            context_payload=context_payload,
        )
        print(f"MODEL: {result.get('model')}")
        print(f"REPLY_CHARS: {len(result.get('text') or '')}")
        print(f"CITATIONS: {result.get('citations') or []}")
        print("REPLY:")
        print(result["text"])


if __name__ == "__main__":
    main()
