import json
from pathlib import Path
import tempfile
import unittest

import yaml

from carbonio_uk.audit import compare
from carbonio_uk.formats.catalog import flatten, parse_json, parse_properties
from carbonio_uk.merge import merge_keep_existing, merge_with_flat_additions
from carbonio_uk.fetch import cache_path
from carbonio_uk.validate import _json_with_duplicates, markup_signature, placeholder_signature, validate_component
from carbonio_uk.manual import write_export
from carbonio_uk.staged_merge import stage


class FlattenTest(unittest.TestCase):
    def test_recursive_leaf_keys(self):
        self.assertEqual(
            flatten({"dialog": {"title": "Title", "actions": ["Save", "Cancel"]}}),
            {"dialog.title": "Title", "dialog.actions[0]": "Save", "dialog.actions[1]": "Cancel"},
        )


class CompareTest(unittest.TestCase):
    def test_en_structure_and_uk_translation(self):
        result = compare(
            {"a": "Hello {name}", "b": "Save", "c": "<b>Open</b>", "null": "Required"},
            {"a": "Привет {name}"},
            {"a": "Вітаємо {name}", "b": "", "c": "<i>Відкрити</i>", "null": None, "extra": "x"},
        )
        self.assertEqual(result["empty"], ["b"])
        self.assertEqual(result["null"], ["null"])
        self.assertEqual(result["extra"], ["extra"])
        self.assertEqual(result["markup_errors"], ["c"])
        self.assertEqual(result["reference"]["ru_missing_against_en"], ["b", "c", "null"])

    def test_placeholder_and_markup_signatures(self):
        self.assertEqual(placeholder_signature("Hello {{ name }}"), placeholder_signature("Вітаю {{name}}"))
        self.assertNotEqual(placeholder_signature("Hello {{ name }}"), placeholder_signature("Вітаю {{user}}"))
        self.assertEqual(markup_signature("<strong>Hello</strong>"), markup_signature("<strong>Вітаю</strong>"))
        self.assertNotEqual(markup_signature("Hello<br>World"), markup_signature("Вітаю"))
        self.assertEqual(markup_signature("<No Name>"), markup_signature("<Без імені>"))

    def test_validator_normalizes_spacing_but_preserves_names_and_ru_is_reference_only(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            commit = "b" * 40
            component = {
                "repository": "https://github.com/Zextras/example-i18n",
                "branch": "main",
                "commit": commit,
                "translation": {"type": "json", "english": "en.json", "russian": "ru.json", "ukrainian": "uk.json"},
            }
            values = {
                "en": {"spacing": "Hello {{ name }}", "strict": "Hello {{ account }}", "ru_only": "Hello {{ valid }}"},
                "uk": {"spacing": "Вітаю {{name}}", "strict": "Вітаю {{ user }}", "ru_only": "Вітаю {{ valid }}"},
                "ru": {"spacing": "Привет {{ wrong }}", "strict": "Привет {{ wrong }}", "ru_only": "Привет {{ broken }}"},
            }
            for language, filename in (("en", "en.json"), ("ru", "ru.json"), ("uk", "uk.json")):
                path = cache_path(cache, "sample", commit, language, filename)
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(values[language]), encoding="utf-8")
            result = validate_component("sample", component, cache)
            self.assertEqual(result["interpolation_format_warnings"], ["spacing"])
            self.assertEqual(result["placeholder_errors"], ["strict"])
            self.assertEqual(result["counts"]["critical"], 1)
            self.assertNotIn("ru_only", result["placeholder_errors"])


class ParserTest(unittest.TestCase):
    def test_json_and_properties(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "catalog.json"
            json_path.write_text(json.dumps({"a": {"b": "value"}}), encoding="utf-8")
            values, errors = parse_json(json_path)
            self.assertEqual(values, {"a.b": "value"})
            self.assertEqual(errors, [])

            properties_path = root / "catalog.properties"
            properties_path.write_text("title=Hello\\nworld\ncontinued=first\\\n  second\n", encoding="utf-8")
            values, errors = parse_properties(properties_path)
            self.assertEqual(values["title"], "Hello\nworld")
            self.assertEqual(values["continued"], "firstsecond")
            self.assertEqual(errors, [])

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text('{"broken":', encoding="utf-8")
            values, errors = parse_json(path)
            self.assertEqual(values, {})
            self.assertTrue(errors)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"same": "first", "same": "second"}', encoding="utf-8")
            duplicates, errors = _json_with_duplicates(path)
            self.assertEqual(duplicates, ["same"])
            self.assertEqual(errors, [])


class MergeTest(unittest.TestCase):
    def test_keep_existing_uk_and_english_order(self):
        english = {"first": "One", "nested": {"kept": "Keep", "new": "New"}}
        ukrainian = {"nested": {"kept": "Зберегти", "new": ""}, "extra": "Додатково"}
        additions = {"first": "Один", "nested": {"kept": "НЕ ЗАМІНЮВАТИ", "new": "Новий"}}
        merged = merge_keep_existing(english, ukrainian, additions)
        self.assertEqual(list(merged), ["first", "nested", "extra"])
        self.assertEqual(merged["nested"]["kept"], "Зберегти")
        self.assertEqual(merged["nested"]["new"], "Новий")
        self.assertEqual(merged["extra"], "Додатково")

    def test_review_approval_is_the_only_existing_uk_override(self):
        english = {"keep": "Keep", "reviewed": "Reviewed", "missing": "Missing"}
        ukrainian = {"keep": "Зберегти", "reviewed": "Старий текст"}
        additions = {"keep": "MOCK", "reviewed": "MOCK", "missing": "Макет"}
        without_review = merge_with_flat_additions(english, ukrainian, additions, {})
        with_review = merge_with_flat_additions(english, ukrainian, additions, {"reviewed": "Схвалений текст"})
        self.assertEqual(without_review["reviewed"], "Старий текст")
        self.assertEqual(with_review["reviewed"], "Схвалений текст")
        self.assertEqual(with_review["keep"], "Зберегти")
        self.assertEqual(with_review["missing"], "Макет")

    def test_manual_tsv_stage_keeps_existing_and_english_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); cache = root / "cache"; commit = "c" * 40
            component = {"repository": "https://example.invalid/i18n", "branch": "main", "commit": commit,
                         "baseline_audit": True,
                         "translation": {"available": True, "type": "json", "english": "en.json", "russian": "ru.json", "ukrainian": "uk.json"}}
            manifest = root / "manifest.yaml"
            manifest.write_text(yaml.safe_dump({"components": {"sample": component}}), encoding="utf-8")
            values = {"en": {"first": "One", "second": "Hello {{ name }}"}, "ru": {"first": "Один", "second": "Привет {{ name }}"}, "uk": {"first": "Один"}}
            for language, filename in (("en", "en.json"), ("ru", "ru.json"), ("uk", "uk.json")):
                path = cache_path(cache, "sample", commit, language, filename); path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(values[language]), encoding="utf-8")
            source = root / "manual.tsv"
            write_export({"rows": [{"component": "sample", "key": "second", "en": "Hello {{ name }}", "ru_reference": "Привет {{ name }}",
                                      "uk_candidate": "Вітаю {{ name }}", "placeholders": [{"token": "i18n:name", "count": 1}], "markup": [], "status": "missing_uk"}]}, source)
            review = root / "review.tsv"; review.write_text("component\tkey\tEN\tRU reference\treason_code\treason\n", encoding="utf-8")
            result = stage(manifest, cache, source, review, root / "merged")
            merged = json.loads((root / "merged/sample/uk.json").read_text(encoding="utf-8"))
            self.assertEqual(list(merged), ["first", "second"])
            self.assertEqual(merged, {"first": "Один", "second": "Вітаю {{ name }}"})
            self.assertEqual(result["candidates_applied"], 1)


if __name__ == "__main__":
    unittest.main()
