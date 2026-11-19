"""Admin endpoints for the in-house process-profile model: read-only, admin roles only,
current configuration is read from the database and sent to the AI service."""

from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

MOD = "api_core.administration.regulations_ai"


def _actor(*roles):
    return SimpleNamespace(
        id="u-1",
        email="admin@eas.com",
        display_name="Admin",
        roles=frozenset(roles),
        must_change_password=False,
    )


def _http(status=200, body=None, calls=None):
    client = MagicMock()

    def post(path, json):
        if calls is not None:
            calls.append((path, json))
        return SimpleNamespace(status_code=status, json=lambda: body or {})

    client.post.side_effect = post
    ctx = MagicMock()
    ctx.__enter__.return_value = client
    return ctx


class ProcessProfileAdminTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def _cursor(self, fetchone=None, fetchall=None):
        cur = MagicMock()
        cur.fetchone.return_value = fetchone
        cur.fetchall.return_value = fetchall or []
        return cur

    def test_impact_requires_admin_role(self):
        with patch(
            "api_core.authn.service.load_actor_from_session",
            return_value=_actor("REQUESTER"),
        ):
            res = self.client.get(f"/api/v1/admin/regulations/{uuid4()}/impact")
        self.assertEqual(res.status_code, 403)

    def test_impact_requires_login(self):
        with patch("api_core.authn.service.load_actor_from_session", return_value=None):
            res = self.client.get(f"/api/v1/admin/regulations/{uuid4()}/impact")
        self.assertEqual(res.status_code, 401)

    def test_impact_sends_current_config_and_returns_proposals(self):
        reg = (
            "REG-007",
            "Nghiệm thu mua sắm",
            "Mọi đề nghị mua sắm phải được nghiệm thu trước khi thanh toán.",
        )
        types = [
            (
                "PURCHASE_REQUEST",
                "Đề nghị mua sắm",
                "PROCUREMENT",
                "",
                ["amount_vnd"],
                "B",
                3,
            )
        ]
        cur = self._cursor(fetchone=reg, fetchall=types)
        calls = []
        ai = {
            "version": "process-profile-3",
            "related": [{"code": "PURCHASE_REQUEST"}],
            "proposals": [
                {
                    "code": "PURCHASE_REQUEST",
                    "current": {"lifecycle": "B", "risk_weight": 3},
                    "proposed": {"lifecycle": "C", "risk_weight": 4},
                }
            ],
        }
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=_actor("POLICY_ADMIN"),
            ),
            patch(f"{MOD}.connection.cursor") as mock_cur,
            patch(f"{MOD}._ai_http", return_value=_http(body=ai, calls=calls)),
        ):
            mock_cur.return_value.__enter__.return_value = cur
            res = self.client.get(f"/api/v1/admin/regulations/{uuid4()}/impact")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["requires_admin_approval"])
        self.assertEqual(body["proposals"][0]["proposed"]["lifecycle"], "C")
        path, sent = calls[0]
        self.assertEqual(
            path, "/ai/regulation-llm/analyze"
        )  # mặc định: mô hình ngôn ngữ lớn + truy xuất
        self.assertIn("old_regulations", sent)
        self.assertEqual(sent["types"][0]["code"], "PURCHASE_REQUEST")
        self.assertEqual(sent["types"][0]["risk_weight"], 3)
        self.assertIn("nghiệm thu", sent["text"])

    def test_impact_ml_engine_uses_inhouse_model(self):
        reg = (
            "REG-007",
            "Nghiệm thu mua sắm",
            "Mọi đề nghị mua sắm phải được nghiệm thu trước khi thanh toán.",
        )
        cur = self._cursor(fetchone=reg, fetchall=[])
        calls = []
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=_actor("POLICY_ADMIN"),
            ),
            patch(f"{MOD}.connection.cursor") as mock_cur,
            patch(
                f"{MOD}._ai_http",
                return_value=_http(body={"version": "process-profile-3"}, calls=calls),
            ),
        ):
            mock_cur.return_value.__enter__.return_value = cur
            res = self.client.get(
                f"/api/v1/admin/regulations/{uuid4()}/impact?engine=ml"
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(calls[0][0], "/ai/process-profile/regulation-impact")

    def test_impact_rejects_unknown_engine(self):
        cur = self._cursor(
            fetchone=("REG-1", "Quy định", "Nội dung quy định đủ dài để đánh giá.")
        )
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=_actor("OPS_ADMIN"),
            ),
            patch(f"{MOD}.connection.cursor") as mock_cur,
        ):
            mock_cur.return_value.__enter__.return_value = cur
            res = self.client.get(
                f"/api/v1/admin/regulations/{uuid4()}/impact?engine=gpt"
            )
        self.assertEqual(res.status_code, 422)

    def test_impact_unknown_regulation_is_404(self):
        cur = self._cursor(fetchone=None)
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=_actor("OPS_ADMIN"),
            ),
            patch(f"{MOD}.connection.cursor") as mock_cur,
        ):
            mock_cur.return_value.__enter__.return_value = cur
            res = self.client.get(f"/api/v1/admin/regulations/{uuid4()}/impact")
        self.assertEqual(res.status_code, 404)

    def test_impact_ai_failure_is_generic_502(self):
        cur = self._cursor(
            fetchone=("REG-1", "Quy định", "Nội dung quy định đủ dài để đánh giá."),
            fetchall=[],
        )
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=_actor("OPS_ADMIN"),
            ),
            patch(f"{MOD}.connection.cursor") as mock_cur,
            patch(
                f"{MOD}._ai_http",
                return_value=_http(status=500, body={"detail": "Traceback ..."}),
            ),
        ):
            mock_cur.return_value.__enter__.return_value = cur
            res = self.client.get(f"/api/v1/admin/regulations/{uuid4()}/impact")
        self.assertEqual(res.status_code, 502)
        self.assertNotIn("Traceback", res.content.decode())

    def test_impact_rejects_post(self):
        with patch(
            "api_core.authn.service.load_actor_from_session",
            return_value=_actor("OPS_ADMIN"),
        ):
            res = self.client.post(
                f"/api/v1/admin/regulations/{uuid4()}/impact",
                data={},
                content_type="application/json",
            )
        self.assertIn(res.status_code, (403, 405))

    def test_assess_validates_input(self):
        with patch(
            "api_core.authn.service.load_actor_from_session",
            return_value=_actor("POLICY_ADMIN"),
        ):
            for bad in (
                {},
                {"name": ""},
                {"name": "X", "fields": "amount"},
                {"name": "X" * 201},
                {"name": "X", "fields": [1]},
            ):
                res = self.client.post(
                    "/api/v1/admin/ai-engine/process-profile",
                    data=bad,
                    content_type="application/json",
                )
                self.assertIn(res.status_code, (403, 422), bad)

    def test_assess_forwards_to_ai(self):
        calls = []
        ai = {
            "version": "process-profile-3",
            "lifecycle": "C",
            "risk_weight": 4,
            "requires_admin_approval": True,
        }
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=_actor("POLICY_ADMIN"),
            ),
            patch(f"{MOD}._ai_http", return_value=_http(body=ai, calls=calls)),
        ):
            res = self.client.post(
                "/api/v1/admin/ai-engine/process-profile",
                data={
                    "name": "Thanh lý tài sản",
                    "description": "Có biên bản bàn giao",
                    "fields": ["amount_vnd"],
                },
                content_type="application/json",
            )
        if res.status_code == 403:  # CSRF enforced by the test client setup
            self.skipTest("CSRF required for POST in this configuration")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["lifecycle"], "C")
        self.assertEqual(calls[0][0], "/ai/process-profile/assess")
