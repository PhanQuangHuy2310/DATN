"""Containers reach a database on the host (local Supabase) via host.docker.internal."""

import os
from unittest import mock

from django.test import SimpleTestCase

from api_core.config.database import parse_database_url

URL = "postgresql://eas_backend_login:pw@127.0.0.1:55322/postgres?sslmode=disable"


class DockerHostAliasTests(SimpleTestCase):
    def test_loopback_is_rewritten_inside_docker(self):
        with mock.patch.dict(os.environ, {"EAS_IN_DOCKER": "1"}):
            self.assertEqual(parse_database_url(URL)["HOST"], "host.docker.internal")

    def test_loopback_kept_outside_docker(self):
        with mock.patch.dict(os.environ, {"EAS_IN_DOCKER": ""}):
            self.assertEqual(parse_database_url(URL)["HOST"], "127.0.0.1")

    def test_remote_hosts_are_never_rewritten(self):
        cloud = "postgresql://u.ref:pw@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=require"
        with mock.patch.dict(os.environ, {"EAS_IN_DOCKER": "1"}):
            self.assertEqual(
                parse_database_url(cloud)["HOST"],
                "aws-0-ap-southeast-2.pooler.supabase.com",
            )
