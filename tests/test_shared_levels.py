# 共通水準の作り方と、実行スクリプトへの受け渡しを確認します。
# HEEDS は起動しません。

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from heeds.cli_backend import _copy_project, _validate, _write_script
from heeds.shared_levels import axis_values, build_shared_levels

_TEMPLATE = Path(__file__).resolve().parent.parent / "heeds" / "scripts" / "run_studies_template.py"


class SharedLevelTests(unittest.TestCase):
    def test_axis_lands_on_the_upper_bound(self):
        self.assertEqual(axis_values(1, 3, 0.5), [1.0, 1.5, 2.0, 2.5, 3.0])
        tenths = axis_values(0, 1, 0.1)
        self.assertEqual(len(tenths), 11)
        self.assertEqual(tenths[0], 0.0)
        self.assertEqual(tenths[3], 0.3)
        self.assertEqual(tenths[-1], 1.0)

    def test_product_order_follows_csv_rows(self):
        levels, errors = build_shared_levels(
            [
                {
                    "name": "thickness",
                    "lower": 1,
                    "baseline": 1.2,
                    "upper": 3,
                    "step": 0.5,
                },
                {"name": "width", "lower": 40, "baseline": 50, "upper": 60, "step": 10},
            ]
        )
        self.assertEqual(errors, [])
        self.assertEqual(levels[0], {"thickness": 1.0, "width": 40.0})
        self.assertEqual(levels[1], {"thickness": 1.0, "width": 50.0})
        self.assertEqual(levels[2], {"thickness": 1.0, "width": 60.0})
        self.assertEqual(levels[3], {"thickness": 1.5, "width": 40.0})
        self.assertEqual(len(levels), 15)
        self.assertNotIn(1.2, [item["thickness"] for item in levels])

    def test_more_than_200_levels_is_rejected(self):
        variables = [
            {"name": "thickness", "lower": 0, "baseline": 0.5, "upper": 1, "step": 0.01},
            {"name": "width", "lower": 0, "baseline": 1, "upper": 2, "step": 1},
        ]
        levels, errors = build_shared_levels(variables)
        self.assertEqual(levels, [])
        self.assertTrue(errors)
        self.assertIn("200", errors[0])
        self.assertTrue(any("200" in item for item in _validate(["stress"], variables)))

    def test_project_copy_keeps_the_original(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "MyProject.heeds"
            source.write_text("original", encoding="utf-8")
            dest = _copy_project(source, "20261002T000000000000Z")
            self.assertEqual(source.read_text(encoding="utf-8"), "original")
            self.assertEqual(dest.read_text(encoding="utf-8"), "original")
            self.assertEqual(dest.parent, source.parent)
            self.assertIn("_chat_", dest.name)

    def test_runtime_script_embeds_the_shared_levels(self):
        template = _TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('study.set("strAgentType", "EVAL")', template)
        self.assertIn('"map", False', template)
        self.assertIn("__PLACEHOLDER_LEVELS__", template)
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "run_studies_heeds.py"
            project = Path(folder) / "MyProject.heeds"
            _write_script(
                script,
                project_path=project,
                out_dir=Path(folder),
                studies=[{"id": "crash", "heeds_name": "Study_crash"}],
                variables=[
                    {
                        "name": "thickness",
                        "lower": 1.0,
                        "baseline": 1.0,
                        "upper": 1.0,
                        "step": 1.0,
                    }
                ],
                levels=[{"thickness": 1.0}],
            )
            text = script.read_text(encoding="utf-8")
        self.assertIn('LEVELS = [{"thickness": 1.0}]', text)
        self.assertNotIn("__PLACEHOLDER_LEVELS__", text)


if __name__ == "__main__":
    unittest.main()
