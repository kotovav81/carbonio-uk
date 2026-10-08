import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from carbonio_uk.fetch import cache_path
from carbonio_uk.manual import import_manual, read_tsv, validate_manual, write_export
from carbonio_uk.pilot import execute_plan, make_plan
from carbonio_uk.review import decide


class PilotTest(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        components = {}
        cache = root / "cache"
        for component_name, marker in (("login", "l"), ("mail", "m")):
            commit = ("a" if component_name == "login" else "b") * 40
            components[component_name] = {
                "repository": f"https://github.com/Zextras/{component_name}-i18n",
                "branch": "main",
                "commit": commit,
                "baseline_audit": True,
                "translation": {
                    "available": True, "type": "json", "english": "en.json",
                    "russian": "ru.json", "ukrainian": "uk.json",
                },
            }
            values = {
                "en": {f"{marker}{index}": f"Account value {index}" for index in range(12)},
                "ru": {f"{marker}{index}": f"Справка {index}" for index in range(12)},
                "uk": {},
            }
            for language, filename in (("en", "en.json"), ("ru", "ru.json"), ("uk", "uk.json")):
                path = cache_path(cache, component_name, commit, language, filename)
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(values[language]), encoding="utf-8")
        manifest = root / "manifest.yaml"
        manifest.write_text(yaml.safe_dump({"components": components}), encoding="utf-8")
        glossary = root / "glossary.yaml"
        glossary.write_text(yaml.safe_dump({"terms": {"Account": "Обліковий запис"}}, allow_unicode=True), encoding="utf-8")
        return manifest, glossary

    def test_plan_is_exactly_ten_login_and_ten_mail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, glossary = self._fixture(root)
            plan = make_plan(manifest, root / "cache", glossary)
            self.assertEqual(len(plan["rows"]), 20)
            self.assertEqual(sum(row["component"] == "login" for row in plan["rows"]), 10)
            self.assertEqual(sum(row["component"] == "mail" for row in plan["rows"]), 10)
            self.assertEqual(plan["rows"][0]["glossary_context"], {"Account": "Обліковий запис"})

    def test_openai_safety_gates_and_pending_is_not_automatically_merged(self):
        plan = {"rows": []}
        with patch("carbonio_uk.providers.openai.OpenAITranslationProvider") as provider:
            with self.assertRaisesRegex(ValueError, "--provider openai"):
                execute_plan(plan, Path("unused"), "none", False, None)
            provider.assert_not_called()
            with self.assertRaisesRegex(ValueError, "--model"):
                execute_plan(plan, Path("unused"), "openai", True, None)
            provider.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pending = root / "review" / "pending" / "login"
            pending.mkdir(parents=True)
            (pending / "row.yaml").write_text("status: pending_review\n", encoding="utf-8")
            self.assertFalse((root / "translations" / "merged").exists())

    def test_each_pending_row_can_be_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pending = root / "pending" / "login"
            pending.mkdir(parents=True)
            row = {
                "id": "row1", "component": "login", "key": "key.one", "commit": "a" * 40,
                "uk_candidate": "Кандидат", "status": "pending_review",
            }
            source = pending / "row1.yaml"
            source.write_text(yaml.safe_dump(row, allow_unicode=True), encoding="utf-8")
            target = decide(root / "pending", root / "decisions", "login", "key.one", "reject", "needs work")
            decision = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(decision["decision"], "reject")
            self.assertEqual(yaml.safe_load(source.read_text(encoding="utf-8"))["status"], "pending_review")

    def test_executed_rows_are_validated_and_saved_pending(self):
        class FakeProvider:
            def __init__(self, model):
                self.model = model

            def translate(self, request):
                return f"Переклад <strong>{{{{name}}}}</strong>"

        plan = {
            "rows": [{
                "id": "row1", "component": "login", "repository": "example", "commit": "a" * 40,
                "key": "welcome", "en": "Welcome <strong>{{ name }}</strong>", "ru_reference": "Справка",
                "glossary_context": {}, "status": "planned_not_executed",
            }]
        }
        with tempfile.TemporaryDirectory() as directory, patch(
            "carbonio_uk.providers.openai.OpenAITranslationProvider", FakeProvider
        ):
            report = execute_plan(plan, Path(directory), "openai", True, "test-model")
            self.assertEqual(report["valid"], 1)
            self.assertEqual(report["rows"][0]["status"], "pending_review")
            self.assertTrue((Path(directory) / "login" / "row1.yaml").exists())

    def test_manual_import_validates_and_never_merges(self):
        rows = [
            {
                "id": "good", "component": "login", "key": "welcome",
                "en": "Welcome <strong>{{ name }}</strong>",
                "uk_candidate": "Вітаємо, <strong>{{ name }}</strong>",
            },
            {
                "id": "bad", "component": "mail", "key": "selected",
                "en": "Selected {{ count }}", "uk_candidate": "Вибрано",
            },
        ]
        report = validate_manual({"rows": rows})
        self.assertEqual(report["rows"][0]["status"], "pending_review")
        self.assertEqual(report["rows"][1]["status"], "manual_validation_failed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "manual.yaml"
            source.write_text(yaml.safe_dump({"rows": rows}, allow_unicode=True), encoding="utf-8")
            imported = import_manual(source, root / "review" / "pending", root / "report.json")
            self.assertEqual(imported["valid"], 1)
            self.assertEqual(imported["invalid"], 1)
            self.assertFalse((root / "translations" / "merged").exists())

    def test_tsv_export_import_preserves_and_validates_placeholders(self):
        row = {
            "id": "ignored", "component": "login", "key": "welcome", "en": "Welcome <b>{{ name }}</b>",
            "ru_reference": "Добро пожаловать, {{ name }}", "uk_candidate": "Вітаємо, <b>{{ name }}</b>", "status": "translated",
            "placeholders": [{"token": "i18n:name", "count": 1}],
            "markup": [{"closing": False, "tag": "b", "count": 1}, {"closing": True, "tag": "b", "count": 1}],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "manual.tsv"
            write_export({"rows": [row]}, source)
            parsed = read_tsv(source)
            self.assertEqual(parsed["rows"][0]["placeholders"], row["placeholders"])
            report = import_manual(source, root / "pending", root / "report.json")
            self.assertEqual(report["valid"], 1)
            self.assertTrue(report["rows"][0]["validation"]["placeholders"])
            self.assertFalse((root / "translations" / "merged").exists())

    def test_tsv_import_rejects_lost_placeholder(self):
        row = {
            "component": "mail", "key": "count", "en": "Selected {{ count }}", "ru_reference": "",
            "uk_candidate": "Вибрано", "status": "translated",
            "placeholders": [{"token": "i18n:count", "count": 1}], "markup": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "manual.tsv"
            write_export({"rows": [row]}, source)
            report = import_manual(source, root / "pending", root / "report.json")
            self.assertEqual(report["invalid"], 1)
            self.assertFalse(report["rows"][0]["validation"]["placeholders"])


if __name__ == "__main__":
    unittest.main()
