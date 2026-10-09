from django.test import SimpleTestCase

from api_core.config.database import DatabaseUrlError, parse_database_url


class DatabaseUrlTests(SimpleTestCase):
    def test_parses_encoded_postgres_url(self):
        config = parse_database_url(
            "postgresql://eas_api:p%40ss@db.example.com:5432/postgres?sslmode=verify-full"
        )
        self.assertEqual(config["USER"], "eas_api")
        self.assertEqual(config["PASSWORD"], "p@ss")
        self.assertEqual(config["HOST"], "db.example.com")
        self.assertEqual(config["OPTIONS"]["sslmode"], "verify-full")

    def test_supports_legacy_unescaped_at_without_logging_it(self):
        config = parse_database_url(
            "postgresql://user:p@ss@db.example.com:5432/postgres"
        )
        self.assertEqual(config["PASSWORD"], "p@ss")
        self.assertEqual(config["HOST"], "db.example.com")

    def test_rejects_non_postgres_url(self):
        with self.assertRaises(DatabaseUrlError):
            parse_database_url("sqlite:///tmp/db.sqlite3")
