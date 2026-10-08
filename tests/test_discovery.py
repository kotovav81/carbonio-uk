import unittest

from carbonio_uk.discovery import render_manifest


class DiscoveryManifestTest(unittest.TestCase):
    def test_manifest_retains_blocked_component(self):
        base = {
            "repository": "https://github.com/Zextras/example-i18n",
            "source_repository": None,
            "branch": "main",
            "commit": "a" * 40,
            "checked_at": "2026-10-08T00:00:00+00:00",
            "status": "active",
            "baseline_audit": True,
            "translation": {
                "type": "json",
                "available": True,
                "english": "en.json",
                "russian": "ru.json",
                "ukrainian": "uk.json",
            },
        }
        output = render_manifest({"components": [{"name": "kept", "included": True, **base}], "aggregators": []})
        self.assertIn("  kept:", output)
        self.assertIn("baseline_audit: true", output)
        self.assertIn('commit: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"', output)


if __name__ == "__main__":
    unittest.main()
