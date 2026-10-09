import json
from pathlib import Path

from django.test import SimpleTestCase

from api_core.audit import (
    AuditCanonicalizationError,
    canonical_bytes,
    canonical_sha256,
)


class AuditCanonicalizationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = (
            Path(__file__).resolve().parents[2]
            / "database"
            / "EAS_Supabase_SQL"
            / "demo_canonical_hash_vectors.json"
        )
        cls.vectors = json.loads(path.read_text(encoding="utf-8"))

    def test_matches_all_database_canonical_vectors(self):
        for vector in self.vectors["admin_events"]:
            with self.subTest(event=vector["canonical_event"]["id"]):
                self.assertEqual(
                    canonical_bytes(vector["canonical_event"]).decode(),
                    vector["canonical_utf8"],
                )
                self.assertEqual(
                    canonical_sha256(vector["canonical_event"]), vector["sha256"]
                )
        for vector in self.vectors["config_releases"]:
            with self.subTest(release=vector["content_sha256"]):
                self.assertEqual(
                    canonical_sha256(json.loads(vector["canonical_content"])),
                    vector["content_sha256"],
                )

    def test_normalizes_unicode_and_rejects_non_string_keys(self):
        self.assertEqual(canonical_bytes({"x": "e\u0301"}), b'{"x":"\xc3\xa9"}')
        with self.assertRaises(AuditCanonicalizationError):
            canonical_bytes({1: "not-allowed"})
