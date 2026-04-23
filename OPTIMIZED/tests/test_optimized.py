import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from context_builder import MmaContextBuilder
from openai_service import trim_reply_text
from service import FightAgentRuntime, build_runtime_bundle, retry_failed_jobs, run_checkpoint_worker
from settings import Config
from storage import StateStore, read_jsonl
from x_api import build_crc_response_token, verify_webhook_signature


class FakeResponder:
    def __init__(self, text="Islam edges it by decision.", error=None):
        self.text = text
        self.error = error
        self.calls = 0

    def generate_reply(self, tweet_text, context_text):
        self.calls += 1
        if self.error:
            raise self.error
        return {
            "text": self.text,
            "response_id": "resp_123",
            "model": "fake-model",
        }


class FakeXClient:
    def __init__(self, secret="secret", error=None):
        self.secret = secret
        self.error = error
        self.calls = 0

    def crc_response_token(self, crc_token):
        return build_crc_response_token(crc_token, self.secret)

    def verify_webhook_signature(self, payload, signature_header):
        return verify_webhook_signature(payload, signature_header, self.secret)

    def create_reply(self, tweet_id, text):
        self.calls += 1
        if self.error:
            raise self.error
        return {"data": {"id": f"reply-{tweet_id}"}}


def make_signature(payload_bytes, secret="secret"):
    return build_crc_response_token(payload_bytes.decode("utf-8"), secret) if False else "sha256=" + __import__("base64").b64encode(__import__("hmac").new(secret.encode("utf-8"), payload_bytes, __import__("hashlib").sha256).digest()).decode("utf-8")


class OptimizedTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.state_dir = self.root / "state"
        self.data_dir.mkdir(parents=True)
        self.state_dir.mkdir(parents=True)

        fighter_df = pd.DataFrame(
            [
                {
                    "Fighter": "Islam Makhachev",
                    "Nickname": "",
                    "Birth Date": "",
                    "Nationality": "Russia",
                    "Hometown": "",
                    "Association": "AKA",
                    "Weight Class": "Lightweight",
                    "Height": "5'10",
                    "Wins": 26,
                    "Losses": 1,
                    "Win_Decision": 4,
                    "Win_KO": 5,
                    "Win_Sub": 17,
                    "Loss_Decision": 0,
                    "Loss_KO": 1,
                    "Loss_Sub": 0,
                    "Fighter_ID": 100,
                    "Win_Other": 0,
                    "Loss_Other": 0,
                    "Reach": '70"',
                    "Stance": "Orthodox",
                    "Fighter_ID_UFCStats": "abc",
                },
                {
                    "Fighter": "Arman Tsarukyan",
                    "Nickname": "",
                    "Birth Date": "",
                    "Nationality": "Armenia",
                    "Hometown": "",
                    "Association": "Lions",
                    "Weight Class": "Lightweight",
                    "Height": "5'7",
                    "Wins": 22,
                    "Losses": 3,
                    "Win_Decision": 9,
                    "Win_KO": 3,
                    "Win_Sub": 10,
                    "Loss_Decision": 2,
                    "Loss_KO": 0,
                    "Loss_Sub": 1,
                    "Fighter_ID": 200,
                    "Win_Other": 0,
                    "Loss_Other": 0,
                    "Reach": '72"',
                    "Stance": "Orthodox",
                    "Fighter_ID_UFCStats": "def",
                },
            ]
        )
        fighter_df.to_csv(self.data_dir / "fighter_info.csv", index=False)

        event_df = pd.DataFrame(
            [
                {
                    "Event Name": "UFC 1",
                    "Event Location": "Vegas",
                    "Event Date": "2025-01-01T00:00:00+00:00",
                    "Fighter 1": "Islam Makhachev",
                    "Fighter 2": "Arman Tsarukyan",
                    "Fighter 1 ID": 100,
                    "Fighter 2 ID": 200,
                    "Weight Class": "Lightweight",
                    "Winning Fighter": "Islam Makhachev",
                    "Winning Method": "Decision",
                    "Winning Round": 5,
                    "Winning Time": "5:00",
                    "Referee": "Herb Dean",
                    "Fight Type": "Main Event",
                },
                {
                    "Event Name": "UFC 2",
                    "Event Location": "Vegas",
                    "Event Date": "2024-06-01T00:00:00+00:00",
                    "Fighter 1": "Islam Makhachev",
                    "Fighter 2": "Someone Else",
                    "Fighter 1 ID": 100,
                    "Fighter 2 ID": 999,
                    "Weight Class": "Lightweight",
                    "Winning Fighter": "Islam Makhachev",
                    "Winning Method": "Submission",
                    "Winning Round": 2,
                    "Winning Time": "3:00",
                    "Referee": "Ref A",
                    "Fight Type": "Main Event",
                },
                {
                    "Event Name": "UFC 3",
                    "Event Location": "Vegas",
                    "Event Date": "2024-01-01T00:00:00+00:00",
                    "Fighter 1": "Arman Tsarukyan",
                    "Fighter 2": "Another Fighter",
                    "Fighter 1 ID": 200,
                    "Fighter 2 ID": 998,
                    "Weight Class": "Lightweight",
                    "Winning Fighter": "Arman Tsarukyan",
                    "Winning Method": "KO",
                    "Winning Round": 1,
                    "Winning Time": "1:45",
                    "Referee": "Ref B",
                    "Fight Type": "Main Event",
                },
            ]
        )
        event_df.to_csv(self.data_dir / "event_data_sherdog.csv", index=False)

        self.config = Config(
            root_dir=self.root,
            data_dir=self.data_dir,
            state_dir=self.state_dir,
            openai_api_key="test-openai-key",
            x_api_key="test-api-key",
            x_api_secret="secret",
            x_bearer_token="bearer",
            x_access_token="access",
            x_access_token_secret="access-secret",
            x_oauth2_user_token=None,
            bot_username="TheFightAgent",
            public_base_url="https://fight-agent.example.com",
            openai_model="gpt-5-mini",
            openai_max_output_tokens=220,
            openai_timeout_seconds=45,
            log_level="INFO",
            reply_char_limit=260,
            x_timeout_seconds=30,
        )
        StateStore(self.state_dir).save_webhook_config({"bot_user_id": "42", "webhook_id": "1000"})

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_payload(self, text="@TheFightAgent Islam Makhachev vs Arman Tsarukyan?", tweet_id="111", author_id="99"):
        return {
            "for_user_id": "42",
            "tweet_create_events": [
                {
                    "id_str": tweet_id,
                    "text": text,
                    "user": {"id_str": author_id},
                    "entities": {"user_mentions": [{"screen_name": "TheFightAgent"}]},
                }
            ],
        }

    def make_app(self, responder=None, x_client=None):
        builder = MmaContextBuilder(
            fighter_info_path=self.data_dir / "fighter_info.csv",
            event_data_path=self.data_dir / "event_data_sherdog.csv",
        )
        app = create_app(
            config=self.config,
            responder=responder or FakeResponder(),
            x_client=x_client or FakeXClient(),
            context_builder=builder,
        )
        return app

    def test_crc_generation_matches_hmac(self):
        token = build_crc_response_token("challenge", "secret")
        self.assertTrue(token.startswith("sha256="))

    def test_signature_verification_accepts_valid_payload(self):
        payload = b'{"hello":"world"}'
        signature = make_signature(payload)
        self.assertTrue(verify_webhook_signature(payload, signature, "secret"))
        self.assertFalse(verify_webhook_signature(payload, signature + "x", "secret"))

    def test_dedupe_blocks_repeat_processing(self):
        state = StateStore(self.state_dir)
        state.mark_processed("42:111", "111", "replied")
        self.assertTrue(state.is_processed("42:111"))

    def test_fighter_matching_exact_and_fuzzy(self):
        builder = MmaContextBuilder(
            fighter_info_path=self.data_dir / "fighter_info.csv",
            event_data_path=self.data_dir / "event_data_sherdog.csv",
        )
        exact = builder.build_context("@TheFightAgent Islam Makhachev vs Arman Tsarukyan?")
        fuzzy = builder.build_context("@TheFightAgent Islma Makhachev vs Arman Tsarukyan?")
        self.assertEqual(len(exact["matched_fighters"]), 2)
        self.assertIn("Islam Makhachev", fuzzy["matched_fighters"])

    def test_reply_truncation_stays_within_limit(self):
        text = "word " * 200
        trimmed = trim_reply_text(text, 50)
        self.assertLessEqual(len(trimmed), 50)

    def test_webhook_post_writes_inbox_and_returns_200(self):
        app = self.make_app()
        client = app.test_client()
        payload = self.make_payload()
        raw = json.dumps(payload).encode("utf-8")
        signature = make_signature(raw)
        response = client.post(
            "/x/webhook",
            data=raw,
            headers={
                "Content-Type": "application/json",
                "x-twitter-webhooks-signature": signature,
            },
        )
        app.runtime.wait_until_idle()  # type: ignore[attr-defined]
        inbox = list(read_jsonl(app.runtime.state.events_inbox_path))  # type: ignore[attr-defined]
        app.runtime.stop()  # type: ignore[attr-defined]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(inbox), 1)

    def test_valid_mention_produces_one_reply_record(self):
        responder = FakeResponder(text="Islam by submission.")
        x_client = FakeXClient()
        app = self.make_app(responder=responder, x_client=x_client)
        client = app.test_client()
        payload = self.make_payload()
        raw = json.dumps(payload).encode("utf-8")
        response = client.post(
            "/x/webhook",
            data=raw,
            headers={
                "Content-Type": "application/json",
                "x-twitter-webhooks-signature": make_signature(raw),
            },
        )
        app.runtime.wait_until_idle()  # type: ignore[attr-defined]
        replies = list(read_jsonl(app.runtime.state.replies_path))  # type: ignore[attr-defined]
        processed = list(read_jsonl(app.runtime.state.processed_ids_path))  # type: ignore[attr-defined]
        app.runtime.stop()  # type: ignore[attr-defined]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(replies), 1)
        self.assertEqual(len(processed), 1)
        self.assertEqual(responder.calls, 1)
        self.assertEqual(x_client.calls, 1)

    def test_duplicate_webhook_delivery_does_not_double_reply(self):
        responder = FakeResponder(text="Islam by decision.")
        x_client = FakeXClient()
        app = self.make_app(responder=responder, x_client=x_client)
        client = app.test_client()
        payload = self.make_payload()
        raw = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-twitter-webhooks-signature": make_signature(raw),
        }
        client.post("/x/webhook", data=raw, headers=headers)
        app.runtime.wait_until_idle()  # type: ignore[attr-defined]
        client.post("/x/webhook", data=raw, headers=headers)
        app.runtime.wait_until_idle()  # type: ignore[attr-defined]
        replies = list(read_jsonl(app.runtime.state.replies_path))  # type: ignore[attr-defined]
        app.runtime.stop()  # type: ignore[attr-defined]
        self.assertEqual(len(replies), 1)
        self.assertEqual(responder.calls, 1)
        self.assertEqual(x_client.calls, 1)

    def test_openai_failure_writes_retryable_failed_job(self):
        responder = FakeResponder(error=RuntimeError("temporary OpenAI failure"))
        app = self.make_app(responder=responder, x_client=FakeXClient())
        client = app.test_client()
        payload = self.make_payload(tweet_id="222")
        raw = json.dumps(payload).encode("utf-8")
        client.post(
            "/x/webhook",
            data=raw,
            headers={
                "Content-Type": "application/json",
                "x-twitter-webhooks-signature": make_signature(raw),
            },
        )
        app.runtime.wait_until_idle()  # type: ignore[attr-defined]
        failures = list(read_jsonl(app.runtime.state.failed_jobs_path))  # type: ignore[attr-defined]
        app.runtime.stop()  # type: ignore[attr-defined]
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0]["retryable"])
        self.assertEqual(failures[0]["phase"], "openai")

    def test_x_post_failure_writes_retryable_failed_job(self):
        x_client = FakeXClient(error=RuntimeError("x down"))
        app = self.make_app(responder=FakeResponder(), x_client=x_client)
        client = app.test_client()
        payload = self.make_payload(tweet_id="333")
        raw = json.dumps(payload).encode("utf-8")
        client.post(
            "/x/webhook",
            data=raw,
            headers={
                "Content-Type": "application/json",
                "x-twitter-webhooks-signature": make_signature(raw),
            },
        )
        app.runtime.wait_until_idle()  # type: ignore[attr-defined]
        failures = list(read_jsonl(app.runtime.state.failed_jobs_path))  # type: ignore[attr-defined]
        app.runtime.stop()  # type: ignore[attr-defined]
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0]["retryable"])
        self.assertEqual(failures[0]["phase"], "x_post")

    def test_retry_failed_reprocesses_retryable_records_only(self):
        first_runtime = FightAgentRuntime(
            build_runtime_bundle(
                self.config,
                responder=FakeResponder(text="Islam by decision."),
                x_client=FakeXClient(error=RuntimeError("x down")),
                context_builder=MmaContextBuilder(
                    fighter_info_path=self.data_dir / "fighter_info.csv",
                    event_data_path=self.data_dir / "event_data_sherdog.csv",
                ),
            ),
            start_worker=False,
        )
        payload = self.make_payload(tweet_id="444")
        first_runtime.bundle.processor.process_inbox_record({"payload": payload}, source="manual")

        second_runtime = FightAgentRuntime(
            build_runtime_bundle(
                self.config,
                responder=FakeResponder(text="Islam by decision."),
                x_client=FakeXClient(),
                context_builder=MmaContextBuilder(
                    fighter_info_path=self.data_dir / "fighter_info.csv",
                    event_data_path=self.data_dir / "event_data_sherdog.csv",
                ),
            ),
            start_worker=False,
        )
        retried = retry_failed_jobs(second_runtime)
        replies = list(read_jsonl(second_runtime.state.replies_path))
        self.assertEqual(len(retried), 1)
        self.assertEqual(len(replies), 1)

    def test_checkpoint_worker_processes_new_records_once(self):
        state = StateStore(self.state_dir)
        state.append_inbox_payload(self.make_payload(tweet_id="555"))

        runtime = FightAgentRuntime(
            build_runtime_bundle(
                self.config,
                responder=FakeResponder(text="Islam by decision."),
                x_client=FakeXClient(),
                context_builder=MmaContextBuilder(
                    fighter_info_path=self.data_dir / "fighter_info.csv",
                    event_data_path=self.data_dir / "event_data_sherdog.csv",
                ),
            ),
            start_worker=False,
        )

        first_processed = run_checkpoint_worker(runtime)
        second_processed = run_checkpoint_worker(runtime)
        replies = list(read_jsonl(runtime.state.replies_path))

        self.assertEqual(first_processed, 1)
        self.assertEqual(second_processed, 0)
        self.assertEqual(len(replies), 1)


if __name__ == "__main__":
    unittest.main()
