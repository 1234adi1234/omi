"""Tests for goals to CSV exporter (#19070).

Pins column header order, type coercion, formula injection defense,
exclusive creation semantics, and UTF-8-sig BOM handling.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

script_path = Path(__file__).resolve().parent.parent / "examples" / "goals_to_csv.py"
spec = importlib.util.spec_from_file_location("goals_to_csv", script_path)
g2c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g2c)


class TestGoalsToCSV(unittest.TestCase):
    def setUp(self):
        self.sample_goals = [
            {
                "id": "goal_01",
                "title": "Drink 2L Water",
                "goal_type": "habit",
                "current_value": 1.5,
                "target_value": 2.0,
                "unit": "liters",
                "is_active": True,
                "created_at": "2026-09-20T10:00:00Z",
            },
            {
                "id": "goal_02",
                "title": "=SUM(A1:A10)",
                "goal_type": "numeric",
                "current_value": 0,
                "target_value": 100,
                "unit": "pages",
                "is_active": False,
                "created_at": "2026-09-21T12:00:00Z",
            },
            {
                "id": "goal_03_minimal",
                "title": "Meditate",
                "goal_type": None,
                "current_value": None,
                "target_value": None,
                "unit": None,
                "is_active": None,
                "created_at": None,
            },
        ]

    def test_spreadsheet_text_coercion_and_formula_guard(self):
        self.assertEqual(g2c.spreadsheet_text("Hello"), "Hello")
        self.assertEqual(g2c.spreadsheet_text(None), "")
        self.assertEqual(g2c.spreadsheet_text(True), "true")
        self.assertEqual(g2c.spreadsheet_text(False), "false")
        self.assertEqual(g2c.spreadsheet_text(42), "42")
        self.assertEqual(g2c.spreadsheet_text(3.14), "3.14")

        # Formula guards
        self.assertEqual(g2c.spreadsheet_text("=CMD('calc')"), "'=CMD('calc')")
        self.assertEqual(g2c.spreadsheet_text("+1234"), "'+1234")
        self.assertEqual(g2c.spreadsheet_text("-500"), "'-500")
        self.assertEqual(g2c.spreadsheet_text("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(g2c.spreadsheet_text("\ttab_prefixed"), "'\ttab_prefixed")

    def test_convert_happy_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "goals.json"
            dst = Path(tmpdir) / "goals.csv"

            src.write_text(json.dumps(self.sample_goals), encoding="utf-8")
            g2c.convert(src, dst)

            raw_bytes = dst.read_bytes()
            # Must start with UTF-8 BOM
            self.assertTrue(raw_bytes.startswith(b"\xef\xbb\xbf"))

            content = dst.read_text(encoding="utf-8-sig")
            lines = [line.strip() for line in content.splitlines() if line.strip()]

            # Header row
            self.assertEqual(lines[0], ",".join(g2c.FIELDS))

            # Row 1
            self.assertIn("goal_01,Drink 2L Water,habit,1.5,2.0,liters,true,2026-09-20T10:00:00Z", lines[1])

            # Row 2 with protected formula title
            self.assertIn("goal_02,'=SUM(A1:A10),numeric,0,100,pages,false,2026-09-21T12:00:00Z", lines[2])

            # Row 3 minimal
            self.assertIn("goal_03_minimal,Meditate,,,,,,", lines[3])

    def test_refuse_overwrite_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "goals.json"
            dst = Path(tmpdir) / "goals.csv"

            src.write_text(json.dumps(self.sample_goals), encoding="utf-8")
            dst.write_text("existing content", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                g2c.convert(src, dst)

            self.assertEqual(dst.read_text(encoding="utf-8"), "existing content")

    def test_empty_goals_array(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "empty.json"
            dst = Path(tmpdir) / "empty.csv"

            src.write_text("[]", encoding="utf-8")
            g2c.convert(src, dst)

            content = dst.read_text(encoding="utf-8-sig")
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0], ",".join(g2c.FIELDS))

    def test_invalid_json_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "invalid.json"
            dst = Path(tmpdir) / "invalid.csv"

            src.write_text('{"not": "a list"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                g2c.convert(src, dst)


if __name__ == "__main__":
    unittest.main()
