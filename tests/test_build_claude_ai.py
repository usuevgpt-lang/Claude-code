#!/usr/bin/env python3
"""Тесты сборки архивов навыков для claude.ai (scripts/build_claude_ai_skills.py)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_claude_ai_skills", ROOT / "scripts" / "build_claude_ai_skills.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
ALL = sorted(p.parent.name for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md"))


def run(*args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = build.main(list(args))
    return rc, buf.getvalue()


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_skills_build_and_meet_claude_ai_rules(self):
        rc, out = run("--out", str(self.out))
        self.assertEqual(rc, 0, out)
        zips = sorted(p.stem for p in self.out.glob("*.zip"))
        self.assertEqual(zips, [n for n in ALL if n not in build.EXCLUDE])
        for z in self.out.glob("*.zip"):
            with self.subTest(skill=z.stem), zipfile.ZipFile(z) as f:
                names = f.namelist()
                self.assertIn(f"{z.stem}/SKILL.md", names)
                self.assertTrue(all(n.startswith(z.stem + "/") for n in names), "всё внутри папки навыка")
                self.assertFalse([n for n in names if "__pycache__" in n or n.endswith(".pyc")])
                text = f.read(f"{z.stem}/SKILL.md").decode("utf-8")
                fm = yaml.safe_load(re.match(r"^---\n(.*?)\n---", text, re.S).group(1))
                self.assertEqual(set(fm), {"name", "description"})
                self.assertEqual(fm["name"], z.stem)
                self.assertLessEqual(len(fm["description"]), 1024)
                self.assertNotRegex(fm["description"], r"[<>]")
                self.assertIn("НОВАПРОМ", text)

    def test_when_to_use_is_kept_in_description(self):
        run("--out", str(self.out), "--only", "novaprom-pressure-vessels")
        with zipfile.ZipFile(self.out / "novaprom-pressure-vessels.zip") as f:
            text = f.read("novaprom-pressure-vessels/SKILL.md").decode("utf-8")
        self.assertIn("рассчитай толщину обечайки", text.split("---")[1])
        self.assertIn("scripts/vessel_calc.py", " ".join(zipfile.ZipFile(self.out / "novaprom-pressure-vessels.zip").namelist()))

    def test_unknown_skill_is_an_error(self):
        rc, out = run("--out", str(self.out), "--only", "no-such-skill")
        self.assertEqual(rc, 2)

    def test_too_long_description_rejected(self):
        with self.assertRaises(ValueError):
            build.convert_skill_md("---\nname: x\ndescription: " + "а" * 1100 + "\n---\nтекст\n")


if __name__ == "__main__":
    unittest.main(verbosity=1)
