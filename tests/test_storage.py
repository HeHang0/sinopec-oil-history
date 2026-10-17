import unittest

from app.storage import merge_rows


class MergeTests(unittest.TestCase):
    def test_adds_and_overwrites(self):
        existing = [
            {"date": "2026-09-05", "92": 8.20},
            {"date": "2026-09-19", "92": 8.30},
        ]
        incoming = [
            {"date": "2026-09-19", "92": 8.31, "95": 8.88},
            {"date": "2026-10-03", "92": 8.40},
        ]
        merged = merge_rows(existing, incoming)
        self.assertEqual([row["date"] for row in merged], ["2026-09-05", "2026-09-19", "2026-10-03"])
        self.assertEqual(merged[1]["92"], 8.31)
        self.assertEqual(merged[1]["95"], 8.88)

    def test_zone_is_part_of_key(self):
        existing = [{"date": "2026-09-05", "zone": "一价区", "92": 8.20}]
        incoming = [{"date": "2026-09-05", "zone": "二价区", "92": 8.30}]
        merged = merge_rows(existing, incoming)
        self.assertEqual(len(merged), 2)
        self.assertEqual({row["zone"] for row in merged}, {"一价区", "二价区"})


if __name__ == "__main__":
    unittest.main()
