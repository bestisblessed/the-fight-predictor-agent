import tempfile
import unittest
from pathlib import Path

from storage import StateStore


class StateStoreTests(unittest.TestCase):
    def test_missing_logs_inbox_returns_no_records_from_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = StateStore(root / "state", root / "logs")
            store.events_inbox_path.unlink()

            records, offset = store.read_inbox_records_from_offset(10)

        self.assertEqual(records, [])
        self.assertEqual(offset, 0)


if __name__ == "__main__":
    unittest.main()
