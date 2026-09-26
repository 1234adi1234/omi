"""Tests for memories to CSV exporter (#18894).

Pins column header order, loose-type coercion, formula injection defense,
tag concatenation, exclusive creation semantics, and UTF-8-sig BOM handling.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

script_path = Path(__file__).resolve().parent.parent / "examples" / "memories_to_csv.py"
spec = importlib.util.spec_from_file_location("memories_to_csv", script_path)
m2c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m2c)


class TestMemoriesToCSV(unittest.TestCase):
    def setUp(self):
        self.sample_memories = [
            {
                "id": "mem_01",
                "content": "User prefers dark mode in editors",
                "category": "preferences",
                "created_at": "2026-09-20T10:00:00Z",
                "visibility": "private",
                "tags": ["ui", "editor", "theme"],
            },
            {
                "id": "mem_02",
                "content": "=1+1",
                "category": None,
                "created_at": "2026-09-21T12:00:00Z",
                "visibility": True,
                "tags": [],
            },
            {
                "id": "mem_03_minimal",
                "content": "Meeting scheduled",
                "category": None,
                "created_at": None,
                "visibility": None,
                "tags": None,
            },
        ]

    def test_spreadsheet_text_coercion_and_formula_guard(self):
        self.assertEqual(m2c.spreadsheet_text("Note"), "Note")
        self.assertEqual(m2c.spreadsheet_text(None), "")
        self.assertEqual(m2c.spreadsheet_text(True), "true")
        self.assertEqual(m2c.spreadsheet_text(False), "false")
        self.assertEqual(m2c.spreadsheet_text(["tag1", "tag2"]), "tag1; tag2")
        self.assertEqual(m2c.spreadsheet_text({"nested": 1}), '{"nested": 1}')

        # Formula guards
        self.assertEqual(m2c.spreadsheet_text("=CMD('calc')"), "'=CMD('calc')")
        self.assertEqual(m2c.spreadsheet_text("+100"), "'+100")
        self.assertEqual(m2c.spreadsheet_text("-50"), "'-50")
        self.assertEqual(m2c.spreadsheet_text("@macro"), "'@macro")
        self.assertEqual(m2c.spreadsheet_text("\nmultiline_prefix"), "'\nmultiline_prefix")

    def test_convert_happy_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "memories.json"
            dst = Path(tmpdir) / "memories.csv"

            src.write_text(json.dumps(self.sample_memories), encoding="utf-8")
            m2c.convert(src, dst)

            raw_bytes = dst.read_bytes()
            self.assertTrue(raw_bytes.startswith(b"\xef\xbb\xbf"))

            content = dst.read_text(encoding="utf-8-sig")
            lines = [l.strip() for l in content.splitlines() if l.strip()]

            self.assertEqual(lines[0], ",".join(m2c.FIELDS))
            self.assertIn("mem_01,User prefers dark mode in editors,preferences,2026-09-20T10:00:00Z,private,ui; editor; theme", lines[1])
            self.assertIn("mem_02,'=1+1,,2026-09-21T12:00:00Z,true,", lines[2])
            self.assertIn("mem_03_minimal,Meeting scheduled,,,,", lines[3])

    def test_refuse_overwrite_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "memories.json"
            dst = Path(tmpdir) / "memories.csv"

            src.write_text(json.dumps(self.sample_memories), encoding="utf-8")
            dst.write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                m2c.convert(src, dst)

    def test_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "empty.json"
            dst = Path(tmpdir) / "empty.csv"

            src.write_text("[]", encoding="utf-8")
            m2c.convert(src, dst)

            content = dst.read_text(encoding="utf-8-sig")
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0], ",".join(m2c.FIELDS))


if __name__ == "__main__":
    unittest.main()
