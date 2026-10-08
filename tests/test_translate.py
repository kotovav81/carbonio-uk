import json
from pathlib import Path
import tempfile
import unittest

import yaml

from carbonio_uk.fetch import cache_path
from carbonio_uk.providers.base import TranslationRequest
from carbonio_uk.providers.mock import MockTranslationProvider
from carbonio_uk.review import approve
from carbonio_uk.translate import plan, translate_mock


class DryRunTest(unittest.TestCase):
    def test_plan_does_not_call_provider_or_write_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commit = "a" * 40
            manifest = {
                "components": {
                    "sample": {
                        "repository": "https://github.com/Zextras/sample-i18n",
                        "branch": "main",
                        "commit": commit,
                        "baseline_audit": True,
                        "translation": {
                            "available": True,
                            "type": "json",
                            "english": "en.json",
                            "russian": "ru.json",
                            "ukrainian": "uk.json",
                        },
                    }
                }
            }
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
            cache = root / "cache"
            for language, filename, value in (
                ("en", "en.json", {"kept": "Keep", "missing": "Translate me"}),
                ("uk", "uk.json", {"kept": "Збережено"}),
            ):
                path = cache_path(cache, "sample", commit, language, filename)
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            report = plan(manifest_path, cache, batch_size=1)
            self.assertTrue(report["dry_run"])
            self.assertFalse(report["provider_called"])
            self.assertEqual(report["totals"]["missing_or_empty"], 1)
            self.assertEqual(report["totals"]["batches"], 1)
            self.assertFalse((root / "translations").exists())

    def test_mock_provider_is_deterministic(self):
        provider = MockTranslationProvider()
        request = TranslationRequest("shell", "save", "Save", {})
        self.assertEqual(provider.translate(request), provider.translate(request))

    def test_mock_checkpoint_and_content_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commit = "c" * 40
            manifest = {
                "components": {
                    "sample": {
                        "repository": "https://github.com/Zextras/sample-i18n", "branch": "main", "commit": commit,
                        "baseline_audit": True,
                        "translation": {"available": True, "type": "json", "english": "en.json", "russian": "ru.json", "ukrainian": "uk.json"},
                    }
                }
            }
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
            cache = root / "upstream"
            for language, filename, value in (("en", "en.json", {"one": "One", "two": "Two"}), ("uk", "uk.json", {})):
                path = cache_path(cache, "sample", commit, language, filename)
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            kwargs = dict(
                manifest_path=manifest_path, cache_root=cache, generated_root=root / "generated",
                translation_cache=root / "translation-cache", checkpoint_root=root / "checkpoints",
                glossary_path=root / "glossary.yaml", batch_size=1, selected="sample", limit=2,
            )
            first = translate_mock(**kwargs)
            second = translate_mock(**kwargs)
            self.assertEqual(first["provider_calls"], 2)
            self.assertEqual(second["provider_calls"], 0)
            self.assertEqual(second["cache_hits"], 2)
            self.assertEqual(len(list((root / "checkpoints" / "sample").glob("*.json"))), 2)

    def test_review_apply_creates_approval_sidecar_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposed = root / "proposed"
            proposed.mkdir()
            proposal = {
                "component": "auth_ui", "repository": "example", "commit": "d" * 40,
                "changes": [{"key": "instruction.changePassword", "existing_uk": "Старе", "proposed_uk": "Нове"}],
            }
            source = proposed / "auth_ui.yaml"
            source.write_text(yaml.safe_dump(proposal, allow_unicode=True), encoding="utf-8")
            target = approve(proposed, root / "approved", "auth_ui", "instruction.changePassword")
            approval = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(approval["changes"][0]["status"], "review_approved")
            self.assertEqual(yaml.safe_load(source.read_text(encoding="utf-8"))["changes"][0]["existing_uk"], "Старе")


if __name__ == "__main__":
    unittest.main()
