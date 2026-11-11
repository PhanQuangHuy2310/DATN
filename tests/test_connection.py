import contextlib
import io
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import unquote, urlsplit

import connect_database as db


class ConnectionTests(unittest.TestCase):
    def config(self):
        return {
            "DB_HOST": "localhost",
            "DB_USER": "runtime",
            "DB_PASSWORD": "p@ss:#/? %",
            "DB_NAME": "postgres",
        }

    def test_password_roundtrip(self):
        env = self.config()
        self.assertEqual(
            unquote(urlsplit(db.database_url(env)).password), env["DB_PASSWORD"]
        )

    def test_url_precedence(self):
        env = self.config() | {
            "DATABASE_URL": "postgresql://chosen",
            "EAS_API_DATABASE_URL": "postgresql://other",
        }
        self.assertEqual(db.database_url(env), "postgresql://chosen")

    def test_missing_config_does_not_reveal_password(self):
        with self.assertRaises(db.ConfigurationError) as ctx:
            db.database_url({"DB_PASSWORD": "secret-value"})
        self.assertNotIn("secret-value", str(ctx.exception))

    def test_invalid_port(self):
        for port in ("abc", "0", "65536"):
            with self.assertRaises(db.ConfigurationError):
                db.database_url(self.config() | {"DB_PORT": port})

    def test_ipv6(self):
        self.assertEqual(
            urlsplit(db.database_url(self.config() | {"DB_HOST": "::1"})).hostname,
            "::1",
        )

    def test_environment_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / ".env"
            p.write_text("DB_PASSWORD='a#b@c'\nDB_HOST=file-host\n", encoding="utf-8")
            env = {"DB_HOST": "process-host"}
            db.load_environment(p, env)
            self.assertEqual(env["DB_PASSWORD"], "a#b@c")
            self.assertEqual(env["DB_HOST"], "process-host")

    def test_malformed_file_is_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / ".env"
            p.write_text("DB_HOST=x\ninvalid\n")
            env = {}
            with self.assertRaises(db.ConfigurationError):
                db.load_environment(p, env)
            self.assertEqual(env, {})

    def test_database_readonly_probe(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(1,), (True,)] + [
            (v,) for n in db.EXPECTED_TABLES for v in ("eas." + n, True)
        ]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        module = types.SimpleNamespace(
            connect=MagicMock(), Error=type("DbError", (Exception,), {})
        )
        module.connect.return_value.__enter__.return_value = conn
        with (
            patch.dict("sys.modules", {"psycopg": module}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(db.check_database("postgresql://secret"), 0)
        self.assertEqual(
            cursor.execute.call_args_list[0].args[0], "SET TRANSACTION READ ONLY"
        )
        self.assertEqual(module.connect.call_args.kwargs["prepare_threshold"], None)

    def test_driver_error_is_redacted(self):
        error = type("DbError", (Exception,), {})
        module = types.SimpleNamespace(
            connect=MagicMock(side_effect=error("password=super-secret")), Error=error
        )
        output = io.StringIO()
        with (
            patch.dict("sys.modules", {"psycopg": module}),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(db.check_database("postgresql://super-secret"), 1)
        self.assertNotIn("super-secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
