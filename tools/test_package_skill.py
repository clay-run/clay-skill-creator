"""Tests for package_skill.validate. Run: python3 -m unittest tools/test_package_skill.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import package_skill  # noqa: E402

FRONTMATTER = "---\nname: demo\ndescription: Scores Northwind accounts.\n---\n\n# Demo\n\n"
OUTPUT_TABLE = "| Account | Score |\n|---|---|\n| Northwind | 82 |\n"


def _validate(body: str) -> dict:
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write(body)
        return package_skill.validate(root)


class RepresentativeOutputHeadingTest(unittest.TestCase):
    def test_level_two_heading(self):
        res = _validate(FRONTMATTER + "## Representative output\n\n" + OUTPUT_TABLE)
        checks = {f["check"] for f in res["findings"]}
        self.assertNotIn("missing_representative_output", checks)

    def test_level_three_heading_does_not_crash(self):
        res = _validate(FRONTMATTER + "### Representative output\n\n" + OUTPUT_TABLE)
        checks = {f["check"] for f in res["findings"]}
        self.assertNotIn("missing_representative_output", checks)

    def test_heading_on_last_line_without_newline_does_not_crash(self):
        res = _validate(FRONTMATTER + "## Representative output")
        checks = {f["check"] for f in res["findings"]}
        self.assertNotIn("missing_representative_output", checks)


if __name__ == "__main__":
    unittest.main()
