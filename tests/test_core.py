import datetime
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from reading_queue.cli import main
from reading_queue.core import ReadingQueue

D = datetime.date(2026, 1, 10)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.q = ReadingQueue(":memory:", today=D)

    def test_add_and_get_with_tags(self):
        pid = self.q.add("Attention Is All You Need", doi="10.5555/ABC", priority=1, tags=["NLP", "transformers"])
        p = self.q.get(pid)
        self.assertEqual(p["doi"], "10.5555/abc")
        self.assertEqual(p["tags"], ["nlp", "transformers"])
        self.assertEqual(p["added"], "2026-01-10")

    def test_duplicate_doi_rejected(self):
        self.q.add("A", doi="10.1/x")
        with self.assertRaises(ValueError):
            self.q.add("A again", doi="10.1/X")

    def test_ordering_and_next(self):
        low = self.q.add("low", priority=5)
        high = self.q.add("high", priority=1)
        self.assertEqual(self.q.next()["id"], high)
        self.q.set_status(low, "reading")
        self.assertEqual(self.q.next()["id"], low)
        self.assertEqual([p["title"] for p in self.q.list()], ["low", "high"])

    def test_status_dates_and_rating(self):
        pid = self.q.add("x")
        self.q.set_status(pid, "read", rating=4)
        p = self.q.get(pid)
        self.assertEqual((p["started"], p["finished"], p["rating"]), ("2026-01-10", "2026-01-10", 4))
        with self.assertRaises(ValueError):
            self.q.set_status(pid, "lost")
        with self.assertRaises(KeyError):
            self.q.set_status(999, "read")

    def test_filters_and_notes(self):
        a = self.q.add("Graph networks", tags=["gnn"])
        self.q.add("Protein folding")
        self.q.note(a, "great related work section")
        self.assertEqual(len(self.q.list(tag="gnn")), 1)
        self.assertEqual(self.q.list(search="related work")[0]["id"], a)

    def test_stats(self):
        old = ReadingQueue(":memory:", today=datetime.date(2025, 12, 1))
        pid = old.add("old paper", tags=["x"])
        old._today = D
        old.set_status(pid, "read")
        old.add("unread")
        s = old.stats(days=30)
        self.assertEqual(s["counts"]["read"], 1)
        self.assertEqual(s["counts"]["to-read"], 1)
        self.assertEqual(s["finished_recently"], 1)
        self.assertEqual(s["mean_days_to_finish"], 40.0)
        self.assertEqual(s["top_tags"], [("x", 1)])

    def test_cascade_delete(self):
        pid = self.q.add("x", tags=["t"])
        self.q.remove(pid)
        self.assertEqual(self.q.db.execute("SELECT COUNT(*) FROM tags").fetchone()[0], 0)

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "q.sqlite")
            buf = io.StringIO()
            with redirect_stdout(buf):
                main(["--db", db, "add", "Paper one", "-p", "2", "-t", "ml"])
                main(["--db", db, "start", "1"])
                main(["--db", db, "next"])
                self.assertEqual(main(["--db", db, "done", "7"]), 1)
                main(["--db", db, "stats"])
            out = buf.getvalue()
            self.assertIn("added #1", out)
            self.assertIn("reading  Paper one", out)
            self.assertIn("reading: 1", out)


if __name__ == "__main__":
    unittest.main()
