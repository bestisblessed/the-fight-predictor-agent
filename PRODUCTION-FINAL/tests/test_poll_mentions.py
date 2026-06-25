import importlib
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeState:
    def __init__(self, webhook_config=None):
        self.webhook_config = webhook_config or {}
        self.processed = set()
        self.processed_marks = []
        self.saved_configs = []
        self.reply_records = []
        self.failure_records = []

    def load_webhook_config(self):
        return dict(self.webhook_config)

    def save_webhook_config(self, updates):
        self.webhook_config.update(updates)
        self.saved_configs.append(dict(updates))
        return dict(self.webhook_config)

    def is_processed(self, event_key):
        return event_key in self.processed

    def mark_processed(self, event_key, tweet_id, reason):
        self.processed.add(event_key)
        self.processed_marks.append((event_key, tweet_id, reason))

    def record_reply(self, record):
        self.reply_records.append(record)

    def record_failure(self, record):
        self.failure_records.append(record)


class FakeContextBuilder:
    def build_context(self, tweet_text):
        return {
            "matched_fighters": ["Fighter One", "Fighter Two"],
            "context_text": f"context for {tweet_text}",
            "resolution_source": "local",
            "resolution_complete": True,
            "match_details": [],
        }


class FakeResponder:
    def __init__(self):
        self.calls = []
        self.reply_text = "Official pick: Fighter One"

    def generate_reply(self, tweet_text, context_text, context_payload):
        self.calls.append(
            {
                "tweet_text": tweet_text,
                "context_text": context_text,
                "context_payload": context_payload,
            }
        )
        return {
            "text": self.reply_text,
            "response_id": "resp_1",
            "model": "fake-model",
            "matched_fighters": context_payload["matched_fighters"],
            "resolution_source": "local",
        }


class FakeXClient:
    def __init__(self, pages=None):
        self.pages = pages or []
        self.mention_calls = []
        self.replies = []
        self.retweets = []
        self.username_lookups = []

    def get_user_by_username(self, username):
        self.username_lookups.append(username)
        return {"data": {"id": "bot-123", "username": username.lstrip("@")}}

    def get_mentions(self, user_id, since_id=None, pagination_token=None, max_results=100):
        self.mention_calls.append(
            {
                "user_id": user_id,
                "since_id": since_id,
                "pagination_token": pagination_token,
                "max_results": max_results,
            }
        )
        index = len(self.mention_calls) - 1
        return self.pages[index] if index < len(self.pages) else {"data": [], "meta": {"result_count": 0}}

    def create_reply(self, tweet_id, text):
        self.replies.append((tweet_id, text))
        return {"data": {"id": f"reply-{tweet_id}"}}

    def retweet(self, user_id, tweet_id):
        self.retweets.append((user_id, tweet_id))
        return {"data": {"retweeted": True}}


class PollMentionsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.poll_mentions = importlib.import_module("poll_mentions")
        from settings import Config

        root = Path(self.temp_dir.name)
        data_dir = root / "data"
        logs_dir = root / "logs"
        data_dir.mkdir()
        logs_dir.mkdir()
        self.config = Config(
            root_dir=root,
            data_dir=data_dir,
            state_dir=root / "state",
            logs_dir=logs_dir,
            openai_api_key="openai-key",
            x_api_key="x-key",
            x_api_secret="x-secret",
            x_bearer_token="bearer",
            x_access_token="access",
            x_access_token_secret="access-secret",
            x_oauth2_user_token=None,
            bot_username="TheFightAgent",
            public_base_url=None,
            openai_model="fake-model",
            openai_timeout_seconds=30,
            log_level="INFO",
            x_timeout_seconds=30,
        )

    def make_runtime(self, state, responder, x_client):
        from service import EventProcessor, RuntimeBundle

        processor = EventProcessor(
            config=self.config,
            state=state,
            context_builder=FakeContextBuilder(),
            responder=responder,
            x_client=x_client,
        )
        return RuntimeBundle(
            config=self.config,
            state=state,
            context_builder=FakeContextBuilder(),
            responder=responder,
            x_client=x_client,
            processor=processor,
        )

    def test_mention_to_event_payload_matches_event_processor_shape(self):
        mention = {
            "id": "200",
            "text": "@TheFightAgent Islam vs Charles?",
            "author_id": "author-1",
            "created_at": "2026-06-25T12:00:00Z",
            "referenced_tweets": [{"type": "replied_to", "id": "150"}],
            "entities": {"mentions": [{"username": "TheFightAgent"}]},
        }
        includes = {"tweets": [{"id": "150", "text": "Parent matchup text"}]}

        payload = self.poll_mentions.mention_to_event_payload(mention, "bot-123", includes)

        self.assertEqual(payload["for_user_id"], "bot-123")
        self.assertEqual(payload["tweet_create_events"][0]["id"], "200")
        self.assertEqual(payload["tweet_create_events"][0]["id_str"], "200")
        self.assertEqual(payload["tweet_create_events"][0]["text"], "@TheFightAgent Islam vs Charles?")
        self.assertEqual(payload["tweet_create_events"][0]["user"]["id_str"], "author-1")
        self.assertEqual(payload["tweet_create_events"][0]["entities"]["user_mentions"][0]["screen_name"], "TheFightAgent")
        self.assertEqual(payload["tweets"]["150"]["text"], "Parent matchup text")

    def test_poll_once_uses_since_id_paginates_and_processes_oldest_first(self):
        state = FakeState({"bot_user_id": "bot-123", "bot_username": "TheFightAgent"})
        responder = FakeResponder()
        x_client = FakeXClient(
            [
                {
                    "data": [
                        {"id": "300", "text": "@TheFightAgent third", "author_id": "author-3"},
                        {"id": "200", "text": "@TheFightAgent second", "author_id": "author-2"},
                    ],
                    "meta": {"next_token": "NEXT", "newest_id": "300"},
                },
                {
                    "data": [
                        {"id": "100", "text": "@TheFightAgent first", "author_id": "author-1"},
                    ],
                    "meta": {"newest_id": "100"},
                },
            ]
        )
        runtime = self.make_runtime(state, responder, x_client)
        self.poll_mentions.save_poll_state(self.config.logs_dir / "poll_state.json", {"since_id": "99"})

        summary = self.poll_mentions.poll_once(self.config, runtime, max_results=100)

        self.assertEqual(
            x_client.mention_calls,
            [
                {"user_id": "bot-123", "since_id": "99", "pagination_token": None, "max_results": 100},
                {"user_id": "bot-123", "since_id": "99", "pagination_token": "NEXT", "max_results": 100},
            ],
        )
        self.assertEqual([call["tweet_text"] for call in responder.calls], ["@TheFightAgent first", "@TheFightAgent second", "@TheFightAgent third"])
        self.assertEqual(summary["fetched_mentions"], 3)
        self.assertEqual(summary["processed_mentions"], 3)
        self.assertEqual(self.poll_mentions.load_poll_state(self.config.logs_dir / "poll_state.json")["since_id"], "300")

    def test_poll_once_skips_self_authored_and_already_processed_mentions(self):
        state = FakeState({"bot_user_id": "bot-123", "bot_username": "TheFightAgent"})
        state.processed.add("bot-123:201")
        responder = FakeResponder()
        x_client = FakeXClient(
            [
                {
                    "data": [
                        {"id": "202", "text": "@TheFightAgent self", "author_id": "bot-123"},
                        {"id": "201", "text": "@TheFightAgent duplicate", "author_id": "author-2"},
                        {"id": "200", "text": "@TheFightAgent new", "author_id": "author-1"},
                    ],
                    "meta": {"newest_id": "202"},
                }
            ]
        )
        runtime = self.make_runtime(state, responder, x_client)
        self.poll_mentions.save_poll_state(self.config.logs_dir / "poll_state.json", {"since_id": "199"})

        summary = self.poll_mentions.poll_once(self.config, runtime)

        self.assertEqual([call["tweet_text"] for call in responder.calls], ["@TheFightAgent new"])
        self.assertEqual(summary["fetched_mentions"], 3)
        self.assertEqual(summary["processed_mentions"], 1)
        self.assertIn(("bot-123:202", "202", "self_authored"), state.processed_marks)

    def test_posted_reply_text_removes_internal_notes_and_links(self):
        state = FakeState({"bot_user_id": "bot-123", "bot_username": "TheFightAgent"})
        responder = FakeResponder()
        responder.reply_text = (
            "I found this in local data after fuzzy lookup.\n\n"
            "Official pick: Fighter One. ([ufc.com](https://www.ufc.com/event/example))\n"
            "Sources: https://www.sherdog.com/fighter/example"
        )
        x_client = FakeXClient(
            [
                {
                    "data": [{"id": "200", "text": "@TheFightAgent matchup?", "author_id": "author-1"}],
                    "meta": {"newest_id": "200"},
                }
            ]
        )
        runtime = self.make_runtime(state, responder, x_client)
        self.poll_mentions.save_poll_state(self.config.logs_dir / "poll_state.json", {"since_id": "199"})

        self.poll_mentions.poll_once(self.config, runtime)

        posted_text = x_client.replies[0][1]
        self.assertEqual(posted_text, "Official pick: Fighter One.")
        self.assertEqual(state.reply_records[0]["reply_text"], "Official pick: Fighter One.")
        self.assertNotIn("fuzzy lookup", posted_text.lower())
        self.assertNotIn("http", posted_text.lower())
        self.assertNotIn("ufc.com", posted_text.lower())
        self.assertNotIn("Sources:", posted_text)

    def test_poll_state_is_not_advanced_when_processing_raises(self):
        class FailingResponder(FakeResponder):
            def generate_reply(self, tweet_text, context_text, context_payload):
                raise RuntimeError("openai unavailable")

        state = FakeState({"bot_user_id": "bot-123", "bot_username": "TheFightAgent"})
        x_client = FakeXClient(
            [
                {
                    "data": [{"id": "200", "text": "@TheFightAgent new", "author_id": "author-1"}],
                    "meta": {"newest_id": "200"},
                }
            ]
        )
        runtime = self.make_runtime(state, FailingResponder(), x_client)
        state_path = self.config.logs_dir / "poll_state.json"
        self.poll_mentions.save_poll_state(state_path, {"since_id": "199"})

        with self.assertRaises(RuntimeError):
            self.poll_mentions.poll_once(self.config, runtime)

        self.assertEqual(self.poll_mentions.load_poll_state(state_path)["since_id"], "199")
        self.assertEqual(state.failure_records[0]["phase"], "openai")

    def test_poll_once_resolves_and_caches_bot_user_id(self):
        state = FakeState()
        responder = FakeResponder()
        x_client = FakeXClient([{"data": [], "meta": {"result_count": 0}}])
        runtime = self.make_runtime(state, responder, x_client)

        summary = self.poll_mentions.poll_once(self.config, runtime)

        self.assertEqual(x_client.username_lookups, ["TheFightAgent"])
        self.assertEqual(state.saved_configs[0]["bot_user_id"], "bot-123")
        self.assertEqual(runtime.processor.bot_user_id, "bot-123")
        self.assertEqual(summary["processed_mentions"], 0)

    def test_first_run_bootstraps_since_id_without_processing_backlog(self):
        state = FakeState({"bot_user_id": "bot-123", "bot_username": "TheFightAgent"})
        responder = FakeResponder()
        x_client = FakeXClient(
            [
                {
                    "data": [
                        {"id": "202", "text": "@TheFightAgent old second", "author_id": "author-2"},
                        {"id": "201", "text": "@TheFightAgent old first", "author_id": "author-1"},
                    ],
                    "meta": {"newest_id": "202"},
                }
            ]
        )
        runtime = self.make_runtime(state, responder, x_client)

        summary = self.poll_mentions.poll_once(self.config, runtime)

        self.assertEqual(responder.calls, [])
        self.assertEqual(summary["fetched_mentions"], 2)
        self.assertEqual(summary["processed_mentions"], 0)
        self.assertTrue(summary["bootstrapped"])
        self.assertEqual(self.poll_mentions.load_poll_state(self.config.logs_dir / "poll_state.json")["since_id"], "202")

    def test_mark_seen_advances_cursor_without_processing_existing_mentions(self):
        state = FakeState({"bot_user_id": "bot-123", "bot_username": "TheFightAgent"})
        responder = FakeResponder()
        x_client = FakeXClient(
            [
                {
                    "data": [{"id": "205", "text": "@TheFightAgent current newest", "author_id": "author-1"}],
                    "meta": {"newest_id": "205"},
                }
            ]
        )
        runtime = self.make_runtime(state, responder, x_client)
        self.poll_mentions.save_poll_state(self.config.logs_dir / "poll_state.json", {"since_id": "199"})

        summary = self.poll_mentions.poll_once(self.config, runtime, mark_seen=True)

        self.assertEqual(x_client.mention_calls[0]["since_id"], "199")
        self.assertEqual(responder.calls, [])
        self.assertEqual(summary["processed_mentions"], 0)
        self.assertTrue(summary["mark_seen"])
        self.assertEqual(self.poll_mentions.load_poll_state(self.config.logs_dir / "poll_state.json")["since_id"], "205")


class CronWrapperTests(unittest.TestCase):
    def test_cron_wrapper_uses_lockf_to_skip_overlaps(self):
        script = (ROOT / "run_agent_m1_cron.sh").read_text(encoding="utf-8")

        self.assertIn('LOCK_FILE="/tmp/fight_predictor_agent.lockfile"', script)
        self.assertIn('/usr/bin/lockf -s -t 0 -k "$LOCK_FILE"', script)
        self.assertIn('if [ "$lock_status" -eq 75 ]; then', script)
        self.assertIn("another poll_mentions.py run is still active", script)
        self.assertNotIn("poll_mentions.lock", script)
        self.assertIn('exec "$PYTHON_BIN" -u poll_mentions.py "$@"', script)


if __name__ == "__main__":
    unittest.main()
