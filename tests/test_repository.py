from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent


class RepositoryTests(unittest.TestCase):
    def test_required_project_structure_exists(self):
        required = [
            ROOT / "HEEDS_PROJECT",
            ROOT / "HEEDS_PROJECT" / "README.md",
            ROOT / "runs" / ".gitkeep",
            ROOT / "heeds" / "catalog.yaml",
            ROOT / "sample.csv",
            ROOT / ".env.example",
        ]
        missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
        self.assertEqual(missing, [])

    def test_local_markdown_links_resolve(self):
        pattern = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)")
        broken: list[str] = []
        for markdown_path in ROOT.rglob("*.md"):
            text = markdown_path.read_text(encoding="utf-8")
            for target in pattern.findall(text):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                linked_path = markdown_path.parent / unquote(target)
                if not linked_path.exists():
                    broken.append(
                        f"{markdown_path.relative_to(ROOT)} -> {target}"
                    )
        self.assertEqual(broken, [])

    def test_old_repository_name_is_not_referenced(self):
        stale: list[str] = []
        for pattern in ("*.py", "*.md", "*.yaml", "*.example", "*.bat"):
            for path in ROOT.rglob(pattern):
                if path.resolve() == Path(__file__).resolve():
                    continue
                if "20260914_LangGraph-HEEDS" in path.read_text(
                    encoding="utf-8", errors="ignore"
                ):
                    stale.append(str(path.relative_to(ROOT)))
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
