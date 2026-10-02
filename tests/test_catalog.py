# 言葉と試験の対応が catalog.yaml だけから決まることを確認します。
# HEEDS も Azure も使いません。

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from heeds.catalog import (
    heeds_study_name,
    load_catalog,
    starter_examples,
    welcome_markdown,
)
from heeds.plan import (
    confirmation_message,
    is_run_approval,
    match_requirements,
    study_ids_for,
)

_FATIGUE = """
design_requirements:
  - id: durability
    label: 耐久
    aliases:
      - 疲労
    study_ids:
      - fatigue
studies:
  - id: fatigue
    name_ja: 耐久解析
    description: テスト用
    heeds_name: Study_fatigue
"""


class CatalogTests(unittest.TestCase):
    def test_real_catalog_loads(self):
        data = load_catalog()
        ids = {item["id"] for item in data["studies"]}
        self.assertEqual(ids, {"stress", "crash", "eigenvalue", "frf"})

    def test_words_come_from_catalog(self):
        matched = match_requirements("乗員保護を確認したい。")
        self.assertEqual([item["id"] for item in matched], ["crash_safety"])
        self.assertEqual(study_ids_for(matched), ["stress", "crash"])

    def test_confirmation_lists_catalog_studies_and_every_variable(self):
        requirements = match_requirements("NVHを見たい")
        variables = [
            {"name": "thickness", "lower": 1, "baseline": 2, "upper": 3, "step": 0.5},
            {"name": "width2", "lower": 10, "baseline": 12, "upper": 20, "step": 2},
        ]
        text = confirmation_message(requirements, variables)
        self.assertIn("固有値解析（eigenvalue）", text)
        self.assertIn("周波数応答解析（frf）", text)
        self.assertIn("width2", text)
        self.assertIn("共通の水準は 30 件です。", text)
        self.assertIn("水準1: thickness 1、width2 10", text)
        self.assertIn("これで合っていますか？", text)
        self.assertNotIn("必ず2試験", text)

    def test_approval_rejects_requirement_words(self):
        self.assertTrue(is_run_approval("はい"))
        self.assertTrue(is_run_approval("実行して"))
        self.assertFalse(is_run_approval("はいお願いします"))
        self.assertFalse(is_run_approval("はい、ただしその前に確認して"))
        self.assertFalse(is_run_approval("はい" + "a" * 41))
        self.assertFalse(is_run_approval("はい、衝突で"))
        self.assertFalse(is_run_approval("NVHに変えて"))

    def test_heeds_name_defaults_to_catalog_and_env_overrides(self):
        key = "HEEDS_STUDY_STRESS"
        previous = os.environ.pop(key, None)
        try:
            self.assertEqual(heeds_study_name("stress"), "Study_stress")
            os.environ[key] = "Other_stress"
            self.assertEqual(heeds_study_name("stress"), "Other_stress")
        finally:
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    def test_new_requirement_is_only_a_catalog_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.yaml"
            path.write_text(_FATIGUE, encoding="utf-8")
            data = load_catalog(path)
        self.assertEqual(starter_examples(data), [("耐久", "耐久を確認したい。")])
        welcome = welcome_markdown(data)
        self.assertIn("耐久", welcome)
        self.assertIn("耐久解析", welcome)
        self.assertNotIn("衝突安全", welcome)
        matched = match_requirements("疲労を確認したい。", data)
        text = confirmation_message(
            matched,
            [{"name": "thickness", "lower": 1, "baseline": 1, "upper": 2, "step": 0.1}],
            data,
        )
        self.assertIn("耐久解析（fatigue）", text)
        self.assertNotIn("静荷重", text)

    def test_unknown_study_id_is_rejected(self):
        broken = _FATIGUE.replace("- fatigue", "- missing")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.yaml"
            path.write_text(broken, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_catalog(path)

    def test_id_that_cannot_form_an_environment_key_is_rejected(self):
        broken = _FATIGUE.replace("id: fatigue", "id: fatigue-test")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.yaml"
            path.write_text(broken, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "試験 ID"):
                load_catalog(path)

    def test_non_mapping_catalog_root_is_rejected_cleanly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.yaml"
            path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "一番外側"):
                load_catalog(path)


if __name__ == "__main__":
    unittest.main()
