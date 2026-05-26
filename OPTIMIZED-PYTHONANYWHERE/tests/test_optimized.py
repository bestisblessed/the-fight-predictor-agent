import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from context_builder import MmaContextBuilder
from openai_service import SYSTEM_PROMPT, format_web_fallback_reply, normalize_reply_text
from service import FightAgentRuntime, build_runtime_bundle, retry_failed_jobs, run_checkpoint_worker
from settings import Config
from storage import StateStore, read_jsonl
from x_api import XApiClient, build_crc_response_token, verify_webhook_signature


class FakeResponder:
    def __init__(self, text="Islam edges it by decision.", error=None):
        self.text = text
        self.error = error
        self.calls = 0
        self.last_tweet_text = None
        self.last_context_text = None
        self.last_context_payload = None

    def generate_reply(self, tweet_text, context_text, context_payload=None):
        self.calls += 1
        self.last_tweet_text = tweet_text
        self.last_context_text = context_text
        self.last_context_payload = context_payload
        if self.error:
            raise self.error
        return {
            "text": self.text,
            "response_id": "resp_123",
            "model": "fake-model",
        }


class FakeXClient:
    def __init__(self, secret="secret", error=None, parent_texts=None):
        self.secret = secret
        self.error = error
        self.calls = 0
        self.replies = []
        self.parent_texts = parent_texts or {}

    def crc_response_token(self, crc_token):
        return build_crc_response_token(crc_token, self.secret)

    def verify_webhook_signature(self, payload, signature_header):
        return verify_webhook_signature(payload, signature_header, self.secret)

    def create_reply(self, tweet_id, text):
        self.calls += 1
        self.replies.append({"tweet_id": str(tweet_id), "text": text})
        if self.error:
            raise self.error
        return {"data": {"id": f"reply-{tweet_id}"}}

    def get_tweet_text(self, tweet_id):
        return self.parent_texts.get(str(tweet_id), "")


class FakeHttpResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.ok = 200 <= status_code < 300
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


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
                {
                    "Fighter": "Yadong Song",
                    "Nickname": "",
                    "Birth Date": "",
                    "Nationality": "China",
                    "Hometown": "",
                    "Association": "Team Alpha Male",
                    "Weight Class": "Bantamweight",
                    "Height": "5'8",
                    "Wins": 22,
                    "Losses": 8,
                    "Win_Decision": 8,
                    "Win_KO": 9,
                    "Win_Sub": 5,
                    "Loss_Decision": 5,
                    "Loss_KO": 2,
                    "Loss_Sub": 1,
                    "Fighter_ID": 300,
                    "Win_Other": 0,
                    "Loss_Other": 0,
                    "Reach": '67"',
                    "Stance": "Orthodox",
                    "Fighter_ID_UFCStats": "ghi",
                },
                {
                    "Fighter": "Deiveson Figueiredo",
                    "Nickname": "",
                    "Birth Date": "",
                    "Nationality": "Brazil",
                    "Hometown": "",
                    "Association": "Team Figueiredo",
                    "Weight Class": "Bantamweight",
                    "Height": "5'5",
                    "Wins": 25,
                    "Losses": 6,
                    "Win_Decision": 7,
                    "Win_KO": 9,
                    "Win_Sub": 9,
                    "Loss_Decision": 3,
                    "Loss_KO": 2,
                    "Loss_Sub": 1,
                    "Fighter_ID": 400,
                    "Win_Other": 0,
                    "Loss_Other": 0,
                    "Reach": '68"',
                    "Stance": "Orthodox",
                    "Fighter_ID_UFCStats": "jkl",
                },
                {
                    "Fighter": "Conor McGregor",
                    "Nickname": "",
                    "Birth Date": "",
                    "Nationality": "Ireland",
                    "Hometown": "",
                    "Association": "SBG Ireland",
                    "Weight Class": "Lightweight",
                    "Height": "5'9",
                    "Wins": 22,
                    "Losses": 6,
                    "Win_Decision": 2,
                    "Win_KO": 19,
                    "Win_Sub": 1,
                    "Loss_Decision": 0,
                    "Loss_KO": 2,
                    "Loss_Sub": 4,
                    "Fighter_ID": 500,
                    "Win_Other": 0,
                    "Loss_Other": 0,
                    "Reach": '74"',
                    "Stance": "Southpaw",
                    "Fighter_ID_UFCStats": "mno",
                },
                {
                    "Fighter": "Max Holloway",
                    "Nickname": "",
                    "Birth Date": "",
                    "Nationality": "United States",
                    "Hometown": "",
                    "Association": "Gracie Technics",
                    "Weight Class": "Lightweight",
                    "Height": "5'11",
                    "Wins": 27,
                    "Losses": 9,
                    "Win_Decision": 13,
                    "Win_KO": 12,
                    "Win_Sub": 2,
                    "Loss_Decision": 7,
                    "Loss_KO": 1,
                    "Loss_Sub": 1,
                    "Fighter_ID": 600,
                    "Win_Other": 0,
                    "Loss_Other": 0,
                    "Reach": '69"',
                    "Stance": "Orthodox",
                    "Fighter_ID_UFCStats": "pqr",
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
                {
                    "Event Name": "UFC 4",
                    "Event Location": "Vegas",
                    "Event Date": "2025-02-22T00:00:00+00:00",
                    "Fighter 1": "Yadong Song",
                    "Fighter 2": "Henry Cejudo",
                    "Fighter 1 ID": 300,
                    "Fighter 2 ID": 997,
                    "Weight Class": "Bantamweight",
                    "Winning Fighter": "Yadong Song",
                    "Winning Method": "Decision",
                    "Winning Round": 3,
                    "Winning Time": "5:00",
                    "Referee": "Ref C",
                    "Fight Type": "Main Event",
                },
                {
                    "Event Name": "UFC 5",
                    "Event Location": "Vegas",
                    "Event Date": "2025-10-11T00:00:00+00:00",
                    "Fighter 1": "Deiveson Figueiredo",
                    "Fighter 2": "Montel Jackson",
                    "Fighter 1 ID": 400,
                    "Fighter 2 ID": 996,
                    "Weight Class": "Bantamweight",
                    "Winning Fighter": "Deiveson Figueiredo",
                    "Winning Method": "Decision",
                    "Winning Round": 3,
                    "Winning Time": "5:00",
                    "Referee": "Ref D",
                    "Fight Type": "Main Event",
                },
                {
                    "Event Name": "UFC 6",
                    "Event Location": "Vegas",
                    "Event Date": "2021-07-10T00:00:00+00:00",
                    "Fighter 1": "Conor McGregor",
                    "Fighter 2": "Dustin Poirier",
                    "Fighter 1 ID": 500,
                    "Fighter 2 ID": 995,
                    "Weight Class": "Lightweight",
                    "Winning Fighter": "Dustin Poirier",
                    "Winning Method": "TKO",
                    "Winning Round": 1,
                    "Winning Time": "5:00",
                    "Referee": "Ref E",
                    "Fight Type": "Main Event",
                },
                {
                    "Event Name": "UFC 7",
                    "Event Location": "Vegas",
                    "Event Date": "2024-10-26T00:00:00+00:00",
                    "Fighter 1": "Max Holloway",
                    "Fighter 2": "Ilia Topuria",
                    "Fighter 1 ID": 600,
                    "Fighter 2 ID": 994,
                    "Weight Class": "Featherweight",
                    "Winning Fighter": "Ilia Topuria",
                    "Winning Method": "KO",
                    "Winning Round": 3,
                    "Winning Time": "1:34",
                    "Referee": "Ref F",
                    "Fight Type": "Main Event",
                },
            ]
        )
        event_df.to_csv(self.data_dir / "event_data_sherdog.csv", index=False)
        (self.data_dir / "fighters.zip").write_bytes(b"test placeholder")

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
            openai_timeout_seconds=45,
            log_level="INFO",
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

    def test_fighter_matching_handles_reversed_names_and_typos(self):
        builder = MmaContextBuilder(
            fighter_info_path=self.data_dir / "fighter_info.csv",
            event_data_path=self.data_dir / "event_data_sherdog.csv",
        )
        reversed_and_misspelled = builder.build_context(
            "@TheFightAgent Song Yadong vs Deiveson Figuieredo prediction?"
        )
        typo = builder.build_context("@TheFightAgent Conor McGregor vs Mac Holloway?")

        self.assertEqual(
            set(reversed_and_misspelled["matched_fighters"]),
            {"Yadong Song", "Deiveson Figueiredo"},
        )
        self.assertEqual(set(typo["matched_fighters"]), {"Conor McGregor", "Max Holloway"})

    def test_context_includes_direct_fighter_career_file(self):
        career_dir = self.data_dir / "fighters"
        career_dir.mkdir()
        (career_dir / "Islam_Makhachev_100.csv").write_text(
            "Result,Opponent,Event Date,Method/Referee,Rounds,Time\n"
            "win,Alexander Volkanovski,Feb / 12 / 2023,Decision (Unanimous)Herb Dean,5,5:00\n"
            "win,Charles Oliveira,Oct / 22 / 2022,Submission (Arm-Triangle Choke)Jason Herzog,2,3:16\n",
            encoding="utf-8",
        )
        builder = MmaContextBuilder(
            fighter_info_path=self.data_dir / "fighter_info.csv",
            event_data_path=self.data_dir / "event_data_sherdog.csv",
        )

        context = builder.build_context("@TheFightAgent Islam Makhachev vs Arman Tsarukyan?")

        self.assertIn("Full career record:", context["context_text"])
        self.assertIn(
            "- win vs Alexander Volkanovski, Feb / 12 / 2023, Decision (Unanimous)Herb Dean, R5 5:00",
            context["context_text"],
        )
        self.assertIn(
            "- win vs Charles Oliveira, Oct / 22 / 2022, Submission (Arm-Triangle Choke)Jason Herzog, R2 3:16",
            context["context_text"],
        )

    def test_context_reads_fighter_career_from_zip_when_directory_missing(self):
        with zipfile.ZipFile(self.data_dir / "fighters.zip", "w") as archive:
            archive.writestr(
                "fighters/Arman_Tsarukyan_200.csv",
                "Result,Opponent,Event Date,Method/Referee,Rounds,Time\n"
                "win,Beneil Dariush,Dec / 02 / 2023,KO (Punches)Dan Miragliotta,1,1:04\n",
            )
        builder = MmaContextBuilder(
            fighter_info_path=self.data_dir / "fighter_info.csv",
            event_data_path=self.data_dir / "event_data_sherdog.csv",
        )

        context = builder.build_context("@TheFightAgent Islam Makhachev vs Arman Tsarukyan?")

        self.assertIn("Full career record:", context["context_text"])
        self.assertIn(
            "- win vs Beneil Dariush, Dec / 02 / 2023, KO (Punches)Dan Miragliotta, R1 1:04",
            context["context_text"],
        )

    def test_context_keeps_existing_summary_when_fighter_career_file_missing(self):
        builder = MmaContextBuilder(
            fighter_info_path=self.data_dir / "fighter_info.csv",
            event_data_path=self.data_dir / "event_data_sherdog.csv",
        )

        context = builder.build_context("@TheFightAgent Islam Makhachev vs Arman Tsarukyan?")

        self.assertIn("Islam Makhachev: 26-1", context["context_text"])
        self.assertIn("Last 5 fights:", context["context_text"])
        self.assertNotIn("Full career record:", context["context_text"])

    def test_require_runtime_accepts_zip_or_direct_fighter_career_source(self):
        (self.data_dir / "fighters.zip").write_bytes(b"not a real zip but present")
        self.config.require_runtime()

        (self.data_dir / "fighters.zip").unlink()
        career_dir = self.data_dir / "fighters"
        career_dir.mkdir()
        (career_dir / "Islam_Makhachev_100.csv").write_text(
            "Result,Opponent,Event Date,Method/Referee,Rounds,Time\n",
            encoding="utf-8",
        )
        self.config.require_runtime()

        (career_dir / "Islam_Makhachev_100.csv").unlink()
        with self.assertRaisesRegex(RuntimeError, "fighters.zip or fighters/.*\\.csv"):
            self.config.require_runtime()

    def test_runtime_bundle_attaches_fighters_zip_to_openai_fallback_files(self):
        (self.data_dir / "fighters.zip").write_bytes(b"zip bytes")

        runtime = FightAgentRuntime(build_runtime_bundle(self.config), start_worker=False)

        attached_paths = [path.name for path in runtime.bundle.responder.data_file_paths]
        self.assertIn("fighter_info.csv", attached_paths)
        self.assertIn("event_data_sherdog.csv", attached_paths)
        self.assertIn("fighters.zip", attached_paths)

    def test_follow_up_text_uses_parent_tweet_context(self):
        parent_text = (
            "@TheFightAgent Research and analyze Song Yadong vs Deiveson Figuieredo in depth."
        )
        responder = FakeResponder(text="Yadong by decision.")
        x_client = FakeXClient(parent_texts={"900": parent_text})
        app = self.make_app(responder=responder, x_client=x_client)
        payload = self.make_payload(
            text="@TheFightAgent you have access to it somewhere in your datasets. Find it.",
            tweet_id="901",
        )
        payload["tweet_create_events"][0]["in_reply_to_status_id_str"] = "900"

        app.runtime.bundle.processor.process_inbox_record({"payload": payload}, source="manual")  # type: ignore[attr-defined]
        replies = list(read_jsonl(app.runtime.state.replies_path))  # type: ignore[attr-defined]
        app.runtime.stop()  # type: ignore[attr-defined]

        self.assertEqual(len(replies), 1)
        self.assertEqual(set(replies[0]["matched_fighters"]), {"Yadong Song", "Deiveson Figueiredo"})
        self.assertIn(parent_text, responder.last_tweet_text)

    def test_scope_filter_replies_to_generic_spam_without_openai(self):
        scope_reply = (
            "I only process MMA/UFC/fight prediction questions or questions about this AI "
            "bot, its data, and how it works. Tag me with an in-scope question and I'll help."
        )

        spam_examples = [
            "@TheFightAgent Let's pump it. Can we talk privately? DM me now.",
            "@TheFightAgent Let's talk privately for collab.",
            "@TheFightAgent Please follow me back let's collaborate.",
            "@TheFightAgent ALTCOIN KING OFFICIAL. Let's talk privately for collab.",
            "@TheFightAgent Any crypto picks for this altcoin pump?",
            "@TheFightAgent What is your favorite pizza topping?",
        ]

        for index, text in enumerate(spam_examples, start=1):
            with self.subTest(text=text):
                responder = FakeResponder()
                x_client = FakeXClient()
                app = self.make_app(responder=responder, x_client=x_client)
                payload = self.make_payload(text=text, tweet_id=f"scope-{index}")

                app.runtime.bundle.processor.process_inbox_record({"payload": payload}, source="manual")  # type: ignore[attr-defined]
                replies = list(read_jsonl(app.runtime.state.replies_path))  # type: ignore[attr-defined]
                processed = list(read_jsonl(app.runtime.state.processed_ids_path))  # type: ignore[attr-defined]
                app.runtime.stop()  # type: ignore[attr-defined]

                self.assertEqual(responder.calls, 0)
                self.assertEqual(x_client.calls, 1)
                self.assertEqual(x_client.replies[0]["text"], scope_reply)
                self.assertEqual(replies[0]["reply_text"], scope_reply)
                self.assertEqual(replies[0]["resolution_source"], "scope_filter")
                self.assertEqual(processed[-1]["reason"], "scope_replied")

    def test_scope_filter_allows_mma_and_bot_meta_prompts_to_openai(self):
        allowed_examples = [
            "@TheFightAgent Islam Makhachev vs Arman Tsarukyan prediction?",
            "@TheFightAgent What data do you use for fight predictions?",
            "@TheFightAgent How does this AI bot make its picks?",
        ]

        for index, text in enumerate(allowed_examples, start=1):
            with self.subTest(text=text):
                responder = FakeResponder(text="In-scope answer.")
                x_client = FakeXClient()
                app = self.make_app(responder=responder, x_client=x_client)
                payload = self.make_payload(text=text, tweet_id=f"ai-{index}")

                app.runtime.bundle.processor.process_inbox_record({"payload": payload}, source="manual")  # type: ignore[attr-defined]
                replies = list(read_jsonl(app.runtime.state.replies_path))  # type: ignore[attr-defined]
                processed = list(read_jsonl(app.runtime.state.processed_ids_path))  # type: ignore[attr-defined]
                app.runtime.stop()  # type: ignore[attr-defined]

                self.assertEqual(responder.calls, 1)
                self.assertEqual(x_client.calls, 1)
                self.assertEqual(replies[0]["reply_text"], "In-scope answer.")
                self.assertNotEqual(replies[0]["resolution_source"], "scope_filter")
                self.assertEqual(processed[-1]["reason"], "replied")

    def test_web_fallback_reply_preserves_long_text(self):
        text = "word " * 200
        reply = format_web_fallback_reply(text, ["https://example.com/a"])
        self.assertGreater(len(reply), 900)
        self.assertIn("https://example.com/a", reply)

    def test_normalize_reply_text_preserves_paragraphs_and_lists(self):
        text = (
            "Pick: Fighter A  by decision\n\n"
            "- Recent form: better pace\tand cardio\n"
            "- Key risk: takedown defense"
        )

        reply = normalize_reply_text(text)

        self.assertEqual(
            reply,
            "Pick: Fighter A by decision\n\n"
            "- Recent form: better pace and cardio\n"
            "- Key risk: takedown defense",
        )

    def test_system_prompt_does_not_force_one_direct_reply_wording(self):
        self.assertNotIn("Write one direct fight prediction reply.", SYSTEM_PROMPT)

    def test_web_fallback_reply_does_not_auto_add_disclosure(self):
        reply = format_web_fallback_reply(
            "I lean Fighter A by decision.",
            ["https://example.com/a"],
        )

        self.assertNotIn("Local dataset was missing/ambiguous", reply)
        self.assertNotIn("confidence lower", reply)
        self.assertIn("I lean Fighter A by decision.", reply)
        self.assertIn("https://example.com/a", reply)

    def test_web_fallback_reply_keeps_sources_without_disclosure(self):
        reply = format_web_fallback_reply(
            "I lean Fighter A by decision.",
            ["https://example.com/a", "https://example.com/b"],
        )

        self.assertNotIn("Local dataset was missing/ambiguous", reply)
        self.assertNotIn("confidence lower", reply)
        self.assertIn("https://example.com/a", reply)
        self.assertIn("https://example.com/b", reply)

    def test_require_x_admin_no_longer_requires_bearer_token(self):
        config = Config(
            root_dir=self.root,
            data_dir=self.data_dir,
            state_dir=self.state_dir,
            openai_api_key="test-openai-key",
            x_api_key="test-api-key",
            x_api_secret="secret",
            x_bearer_token=None,
            x_access_token="access",
            x_access_token_secret="access-secret",
            x_oauth2_user_token=None,
            bot_username="TheFightAgent",
            public_base_url="https://fight-agent.example.com",
            openai_model="gpt-5-mini",
            openai_timeout_seconds=45,
            log_level="INFO",
            x_timeout_seconds=30,
        )
        config.require_x_admin()

    def test_from_env_overrides_existing_process_values(self):
        env_path = Path(__file__).resolve().parents[1] / ".env"
        previous = env_path.read_text() if env_path.exists() else None
        original_process_value = os.environ.get("X_API_SECRET")
        try:
            os.environ["X_API_SECRET"] = "REPLACE_ME"
            env_path.write_text(
                "\n".join(
                    [
                        "OPENAI_API_KEY=test-openai",
                        "X_API_KEY=test-api-key",
                        "X_API_SECRET=fresh-secret",
                        "X_ACCESS_TOKEN=test-access",
                        "X_ACCESS_TOKEN_SECRET=test-access-secret",
                        "BOT_USERNAME=TheFightAgent",
                        "PUBLIC_BASE_URL=https://fight-agent.example.com",
                    ]
                )
            )
            self.assertEqual(Config.from_env().x_api_secret, "fresh-secret")
        finally:
            if previous is None:
                env_path.unlink(missing_ok=True)
            else:
                env_path.write_text(previous)
            if original_process_value is None:
                os.environ.pop("X_API_SECRET", None)
            else:
                os.environ["X_API_SECRET"] = original_process_value

    def test_bearer_request_refreshes_from_oauth2_token(self):
        client = XApiClient(self.config)
        captured_headers = []

        def fake_request(method, url, headers, auth, json, timeout):
            captured_headers.append(headers["Authorization"])
            if len(captured_headers) == 1:
                return FakeHttpResponse(
                    401,
                    {
                        "title": "Unauthorized",
                        "status": 401,
                        "detail": "Unauthorized",
                    },
                )
            return FakeHttpResponse(200, {"data": {"id": "42", "username": "TheFightAgent"}})

        with patch("x_api.requests.request", side_effect=fake_request), patch(
            "x_api.requests.post",
            return_value=FakeHttpResponse(
                200,
                {
                    "token_type": "bearer",
                    "access_token": "fresh-bearer-token",
                },
            ),
        ) as mocked_post:
            response = client.get_user_by_username("TheFightAgent")

        self.assertEqual(response["data"]["id"], "42")
        self.assertEqual(captured_headers, ["Bearer bearer", "Bearer fresh-bearer-token"])
        mocked_post.assert_called_once()

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
