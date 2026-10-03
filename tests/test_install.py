#!/usr/bin/env python3
"""Тесты установщика scripts/install_novaprom.py и правила бюджета списка навыков в merge_settings.py.

Установка выполняется во временную папку (--claude-dir), реальный ~/.claude не трогается.
Запуск: python -m unittest tests.test_install
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


inst = load("install_novaprom", ROOT / "scripts" / "install_novaprom.py")
merge = load("merge_settings_t", ROOT / "scripts" / "merge_settings.py")
SKILLS = sorted(p.name for p in (ROOT / ".claude" / "skills").iterdir() if (p / "SKILL.md").is_file())
AGENTS = sorted(p.name for p in (ROOT / ".claude" / "agents").glob("*.md"))


def run(*args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = inst.main(list(args))
    return rc, buf.getvalue()


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / ".claude"

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, *extra: str) -> tuple[int, str]:
        return run("--claude-dir", str(self.dir), *extra)

    def test_fresh_install_has_everything(self):
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(p.name for p in (self.dir / "skills").iterdir()), SKILLS)
        self.assertEqual(sorted(p.name for p in (self.dir / "agents").glob("*.md")), AGENTS)
        self.assertTrue((self.dir / "hooks" / "novaprom_guard.py").is_file())
        self.assertIn("novaprom/NOVAPROM.md", (self.dir / "CLAUDE.md").read_text(encoding="utf-8"))
        settings = json.loads((self.dir / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("novaprom_guard", json.dumps(settings["hooks"]))
        self.assertIs(settings["enabledPlugins"]["novaprom-marketing@novaprom"], True)
        self.assertFalse(list(self.dir.rglob("__pycache__")), "служебные файлы Python не копируются")
        self.assertEqual(run("--claude-dir", str(self.dir), "--check")[0], 0)

    def test_second_run_changes_nothing(self):
        self.install()
        before = {p: p.stat().st_mtime_ns for p in self.dir.rglob("*") if p.is_file()}
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        self.assertIn("изменений нет", out)
        self.assertFalse((self.dir / "novaprom-backups").exists())
        after = {p: p.stat().st_mtime_ns for p in self.dir.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual((self.dir / "CLAUDE.md").read_text(encoding="utf-8").count("NOVAPROM.md"), 1)

    def test_changed_skill_is_backed_up_not_lost(self):
        self.install()
        edited = self.dir / "skills" / SKILLS[0] / "SKILL.md"
        edited.write_text("моя правка", encoding="utf-8")
        (self.dir / "skills" / "my-own-skill").mkdir()
        (self.dir / "skills" / "my-own-skill" / "SKILL.md").write_text("---\nname: my-own-skill\n---\n", encoding="utf-8")
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        self.assertNotEqual(edited.read_text(encoding="utf-8"), "моя правка")
        backups = list((self.dir / "novaprom-backups").glob(f"*/skills/{SKILLS[0]}/SKILL.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "моя правка")
        self.assertTrue((self.dir / "skills" / "my-own-skill" / "SKILL.md").is_file(), "чужие навыки не трогаются")

    def test_existing_claude_md_in_utf16_keeps_text(self):
        self.dir.mkdir(parents=True)
        (self.dir / "CLAUDE.md").write_bytes(b"\xff\xfe" + "# Мои правила\nотвечать кратко\n".encode("utf-16-le"))
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        text = (self.dir / "CLAUDE.md").read_bytes().decode("utf-8")
        self.assertTrue(text.startswith("# Мои правила\nотвечать кратко\n"))
        self.assertIn("NOVAPROM.md", text)
        self.assertTrue(list(self.dir.glob("CLAUDE.md.bak-*")))

    def test_user_settings_are_kept(self):
        self.dir.mkdir(parents=True)
        (self.dir / "settings.json").write_text(json.dumps(
            {"model": "opus", "permissions": {"allow": ["Bash(ls *)"]}, "skillListingBudgetFraction": 0.02}),
            encoding="utf-8")
        self.install()
        s = json.loads((self.dir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(s["model"], "opus")
        self.assertEqual(s["permissions"]["allow"], ["Bash(ls *)"])
        proposed = json.loads((ROOT / "docs" / "settings.proposed.json").read_text(encoding="utf-8"))
        self.assertEqual(s["skillListingBudgetFraction"], proposed["skillListingBudgetFraction"])

    def test_retired_skill_moved_aside(self):
        (self.dir / "skills" / "task-observer").mkdir(parents=True)
        (self.dir / "skills" / "task-observer" / "SKILL.md").write_text("x", encoding="utf-8")
        self.install()
        self.assertFalse((self.dir / "skills" / "task-observer").exists())
        self.assertTrue(list((self.dir / "novaprom-backups").glob("*/skills-removed/task-observer/SKILL.md")))

    def test_dry_run_writes_nothing(self):
        rc, out = self.install("--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertFalse(any(self.dir.rglob("*")) if self.dir.exists() else False)

    def test_check_reports_missing_parts(self):
        rc, out = run("--claude-dir", str(self.dir), "--check")
        self.assertEqual(rc, 1)
        self.assertIn("[X]", out)


class ListingBudget(unittest.TestCase):
    PROP = {"skillListingBudgetFraction": 0.06}

    def test_budget_raised_when_lower_or_missing(self):
        for cur in ({}, {"skillListingBudgetFraction": 0.02}, {"skillListingBudgetFraction": "x"}):
            with self.subTest(cur=cur):
                out, _ = merge.merge(cur, self.PROP, [], [])
                self.assertEqual(out["skillListingBudgetFraction"], 0.06)

    def test_larger_user_budget_kept(self):
        out, log = merge.merge({"skillListingBudgetFraction": 0.1}, self.PROP, [], [])
        self.assertEqual(out["skillListingBudgetFraction"], 0.1)
        self.assertFalse(log)

    def test_proposed_budget_fits_all_listed_skills(self):
        """Бюджет (окно 200 тыс. токенов × 4 символа × доля) вмещает описания навыков НОВАПРОМ и маркетинга
        с запасом на навыки claude.ai и встроенные — иначе часть навыков попадает в список только по имени."""
        import re
        import yaml
        total = 0
        for root in (ROOT / ".claude" / "skills", ROOT / "plugins" / "novaprom-marketing" / "skills"):
            for p in root.glob("*/SKILL.md"):
                fm = yaml.safe_load(re.match(r"^---\n(.*?)\n---", p.read_text(encoding="utf-8"), re.S).group(1))
                desc = fm["description"] + (" - " + fm["when_to_use"] if fm.get("when_to_use") else "")
                total += len(fm["name"]) + 4 + min(len(desc), 1536)
        fraction = json.loads((ROOT / "docs" / "settings.proposed.json").read_text(encoding="utf-8"))[
            "skillListingBudgetFraction"]
        budget = 200_000 * 4 * fraction
        self.assertLess(total + 16_000, budget, f"описания {total} симв. + ~16 тыс. прочих > бюджета {budget:.0f}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
