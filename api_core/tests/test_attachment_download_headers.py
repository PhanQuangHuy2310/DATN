"""vibe-check #12/#14: downloads are always attachments, never rendered inline,
and the stored file name is encoded per RFC 6266."""

from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.authn.models import Actor


def _actor():
    return Actor(
        id=str(uuid4()),
        email="requester@eas.com",
        display_name="Requester",
        department_id=str(uuid4()),
        auth_version=1,
        roles=frozenset({"REQUESTER"}),
        must_change_password=False,
    )


@patch(
    "api_core.authn.service.load_actor_from_session", side_effect=lambda _r: _actor()
)
class AttachmentDownloadHeaderTests(SimpleTestCase):
    def _get(self, name, mime):
        with patch(
            "api_core.workflow.views.download_attachment",
            return_value=(b"%PDF-1.7", name, mime),
        ):
            return self.client.get(f"/api/v1/attachments/{uuid4()}/download")

    def test_unicode_and_quote_in_name_are_encoded(self, _load):
        response = self._get('Hóa đơn "x".pdf', "application/pdf")
        self.assertEqual(response.status_code, 200)
        disposition = response["Content-Disposition"]
        self.assertTrue(disposition.startswith("attachment; filename*=utf-8''"))
        self.assertNotIn('"x"', disposition)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Content-Security-Policy"], "default-src 'none'")

    def test_active_content_types_are_downgraded(self, _load):
        for mime in ("text/html", "image/svg+xml", "application/xhtml+xml"):
            with self.subTest(mime=mime):
                response = self._get("file.bin", mime)
                self.assertEqual(response["Content-Type"], "application/octet-stream")
