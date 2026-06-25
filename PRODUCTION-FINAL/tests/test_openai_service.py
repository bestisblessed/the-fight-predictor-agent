import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class OpenAIServiceTextTests(unittest.TestCase):
    def setUp(self):
        self.openai_service = importlib.import_module("openai_service")

    def test_sanitize_reply_for_x_removes_internal_notes_and_links(self):
        text = (
            "I found this in local data after fuzzy lookup.\n\n"
            "Official pick: Rafael Fiziev. ([sherdog.com](https://www.sherdog.com/fighter/Rafael-Fiziev-202657?utm_source=openai))\n"
            "More detail at https://www.ufc.com/event/example and www.tapology.com/fightcenter.\n"
            "Sources: https://www.sherdog.com/fighter/Rafael-Fiziev-202657"
        )

        cleaned = self.openai_service.sanitize_reply_for_x(text)

        self.assertIn("Official pick: Rafael Fiziev.", cleaned)
        self.assertNotIn("fuzzy lookup", cleaned.lower())
        self.assertNotIn("http", cleaned.lower())
        self.assertNotIn("www.", cleaned.lower())
        self.assertNotIn("sherdog.com", cleaned.lower())
        self.assertNotIn("tapology.com", cleaned.lower())
        self.assertNotIn("Sources:", cleaned)

    def test_format_web_fallback_reply_does_not_append_urls(self):
        text = (
            "Fiziev by decision. ([sherdog.com](https://www.sherdog.com/fighter/Rafael-Fiziev-202657))"
        )

        cleaned = self.openai_service.format_web_fallback_reply(
            text,
            ["https://www.ufc.com/event/example"],
        )

        self.assertEqual(cleaned, "Fiziev by decision.")
        self.assertNotIn("http", cleaned.lower())
        self.assertNotIn("Sources:", cleaned)


if __name__ == "__main__":
    unittest.main()
