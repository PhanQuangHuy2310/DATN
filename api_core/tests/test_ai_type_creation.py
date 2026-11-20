"""AI tạo loại yêu cầu mới từ nhu cầu chưa có trong danh mục, và cho loại mới dùng ngay các cơ chế AI của loại có sẵn.

* nhu cầu khớp loại đã có (kể cả loại AI vừa tạo cho người khác) -> trả loại đó, không tạo trùng;
* nhu cầu mới -> đề xuất mẫu B/C (không bao giờ A), quản lý trực tiếp duyệt, bộ phận thực hiện theo bộ phận AI đoán;
* chỉ người có vai trò tạo yêu cầu mới được tạo; tối đa 3 loại / người / 24 giờ;
* loại mẫu A có bản nâng cấp B/C; tình huống xấu của loại gần nhất được mở rộng sang loại mới khi đủ giống.
"""

from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from api_core.workflow import ai_type_creation as atc
from api_core.workflow import type_onboarding as onb
from api_core.workflow.errors import CommandError

MOD = "api_core.workflow.ai_type_creation"
GROUPS = {"PEOPLE": "Nhân sự & Đào tạo", "WORK": "Công việc chung", "ASSET": "Tài sản"}


def _actor(*roles):
    return SimpleNamespace(
        id="u-1",
        email="nv@eas.com",
        display_name="Nhân viên",
        roles=frozenset(roles),
        must_change_password=False,
    )


def _novel(**extra):
    return {
        "predicted_request_type": "LAPTOP_PROVISION",
        "predicted_request_name": "Cấp máy tính",
        "predicted_category": "PEOPLE",
        "predicted_department": "HR",
        "confidence_request_type": 0.84,
        "novel": True,
        "unclear": False,
        "fallback_used": False,
        "source": "model",
        **extra,
    }


class ProposalTests(SimpleTestCase):
    def propose(self, text, classify, assess=None):
        with (
            patch(f"{MOD}._classify", return_value=classify),
            patch(
                f"{MOD}._assess",
                return_value=assess or {"lifecycle": "B", "risk_weight": 2},
            ),
            patch(f"{MOD}._groups", return_value=GROUPS),
        ):
            return atc.propose(text)

    def test_text_must_be_a_short_need(self):
        for text in ("ăn", "x" * 121):
            with self.assertRaises(CommandError) as ctx:
                self.propose(text, _novel())
            self.assertEqual(ctx.exception.code, "TEXT_LENGTH_INVALID")

    def test_gibberish_is_refused(self):
        with self.assertRaises(CommandError) as ctx:
            self.propose("asdf qwer zxcv", _novel(unclear=True))
        self.assertEqual(ctx.exception.code, "TEXT_UNCLEAR")

    def test_keyword_fallback_is_not_trusted(self):
        with self.assertRaises(CommandError) as ctx:
            self.propose("đăng ký chỗ đỗ ô tô", _novel(fallback_used=True))
        self.assertEqual(ctx.exception.status, 503)

    def test_a_need_the_model_knows_returns_the_existing_type(self):
        plan = self.propose(
            "xin nghỉ phép năm 2 ngày",
            {
                "predicted_request_type": "LEAVE",
                "predicted_request_name": "Nghỉ phép",
                "confidence_request_type": 0.91,
                "novel": False,
                "source": "model",
            },
        )
        self.assertEqual(
            plan,
            {"existing": {"code": "LEAVE", "name": "Nghỉ phép", "confidence": 0.91}},
        )

    def test_a_type_another_user_already_created_is_reused(self):
        plan = self.propose(
            "đặt suất ăn trưa",
            {
                "predicted_request_type": "AI_1A2B3C4D",
                "predicted_request_name": "Đăng ký suất ăn trưa",
                "confidence_request_type": 0.62,
                "novel": False,
                "source": "learned",
            },
        )
        self.assertEqual(plan["existing"]["code"], "AI_1A2B3C4D")

    def test_new_need_gets_a_reviewed_route_never_auto_approval(self):
        plan = self.propose(
            "Em muốn đăng ký suất ăn trưa",
            _novel(),
            assess={"lifecycle": "A", "risk_weight": 1},
        )
        p = plan["proposal"]
        self.assertEqual(p["name"], "Đăng ký suất ăn trưa")
        self.assertEqual(p["lifecycle"], "B")
        self.assertEqual(p["group_code"], "PEOPLE")
        self.assertEqual(
            p["route_rules"]["rules"],
            [{"id": "AI_DEFAULT", "default": True, "approvers": ["DIRECT_MANAGER"]}],
        )
        self.assertEqual(p["route_rules"]["executor"], "EXECUTOR_HR")
        self.assertIsNone(p["route_rules"]["acceptor"])
        self.assertIn("Nhân sự", p["route_summary"])
        self.assertEqual(p["nearest_type"], "LAPTOP_PROVISION")

    def test_type_c_is_accepted_by_the_requester_and_unknown_groups_fall_back(self):
        plan = self.propose(
            "thuê xe tải chở hàng triển lãm",
            _novel(predicted_category="NOPE", predicted_department=""),
            assess={"lifecycle": "C", "risk_weight": 9},
        )
        p = plan["proposal"]
        self.assertEqual(
            (p["lifecycle"], p["group_code"], p["risk_weight"]), ("C", "WORK", 5)
        )
        self.assertEqual(p["route_rules"]["acceptor"], "REQUESTER")
        self.assertEqual(p["route_rules"]["executor"], "EXECUTOR_ADMIN")

    def test_names_drop_the_filler_words(self):
        self.assertEqual(
            atc.clean_name("  cho em xin phép   đăng ký chỗ đỗ ô tô!! "),
            "Đăng ký chỗ đỗ ô tô",
        )
        self.assertEqual(atc.clean_name("Làm sao để mượn máy chiếu"), "Mượn máy chiếu")


class CreateTests(SimpleTestCase):
    def _db(self, fetchone):
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetchone
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        return conn, cursor

    def test_existing_type_is_returned_without_writing(self):
        with (
            patch(
                f"{MOD}.propose",
                return_value={"existing": {"code": "LEAVE", "name": "Nghỉ phép"}},
            ),
            patch(f"{MOD}.connection") as conn,
        ):
            result = atc.create(_actor("REQUESTER"), "xin nghỉ phép", "cid")
        self.assertEqual(
            result, {"created": False, "type": {"code": "LEAVE", "name": "Nghỉ phép"}}
        )
        conn.cursor.assert_not_called()

    def test_daily_limit(self):
        with (
            patch(f"{MOD}._classify", return_value=_novel()),
            patch(f"{MOD}._groups", return_value=GROUPS),
            patch(f"{MOD}._assess", return_value={"lifecycle": "B", "risk_weight": 2}),
            patch(f"{MOD}.transaction"),
        ):
            conn, _ = self._db([(atc.MAX_PER_DAY,)])
            with (
                patch(f"{MOD}.connection", conn),
                self.assertRaises(CommandError) as ctx,
            ):
                atc.create(_actor("REQUESTER"), "đăng ký suất ăn trưa", "cid")
        self.assertEqual(
            (ctx.exception.code, ctx.exception.status), ("AI_TYPE_CREATION_LIMIT", 429)
        )

    def test_creates_type_release_menu_and_scoped_bad_cases(self):
        with (
            patch(f"{MOD}._classify", return_value=_novel()),
            patch(f"{MOD}._groups", return_value=GROUPS),
            patch(f"{MOD}._assess", return_value={"lifecycle": "B", "risk_weight": 2}),
            patch(f"{MOD}.transaction"),
            patch(
                f"{MOD}.type_onboarding.extend_bad_cases", return_value=["BC_X_AI_1"]
            ) as extend,
            patch(f"{MOD}._append_admin_audit") as audit,
            patch(f"{MOD}.learned_types.invalidate") as invalidate,
        ):
            conn, cursor = self._db(
                [(0,), None, ({"DIRECT_MANAGER": "x"},), ("rel-1",)]
            )
            with patch(f"{MOD}.connection", conn):
                result = atc.create(
                    _actor("REQUESTER"), "Em muốn đăng ký suất ăn trưa", "cid"
                )
        self.assertTrue(result["created"])
        self.assertRegex(result["type"]["code"], r"^AI_[0-9A-F]{8}$")
        self.assertEqual(result["type"]["lifecycle"], "B")
        sql = " ".join(call.args[0] for call in cursor.execute.call_args_list)
        for fragment in (
            "lock_security",
            "INSERT INTO eas.request_type",
            "INSERT INTO eas.config_release",
            "INSERT INTO eas.request_menu_item",
            "security_epoch",
            "system_announcement",
        ):
            self.assertIn(fragment, sql)
        self.assertEqual(extend.call_args.kwargs["nearest_code"], "LAPTOP_PROVISION")
        self.assertEqual(audit.call_args.kwargs["action"], "AI_REQUEST_TYPE_CREATED")
        invalidate.assert_called_once()
        # The admin announcement uses the {title, steps} guidance shape SystemUpdates.jsx renders.
        announce = next(
            c
            for c in cursor.execute.call_args_list
            if "system_announcement" in c.args[0]
        )
        changes, guidance = announce.args[1][3].obj, announce.args[1][4].obj
        self.assertTrue(all(isinstance(c, dict) and c.get("title") for c in changes))
        self.assertTrue(
            guidance
            and all(isinstance(g.get("steps"), list) and g["steps"] for g in guidance)
        )


class EndpointTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def post(self, path, roles, body):
        with patch(
            "api_core.authn.service.load_actor_from_session",
            return_value=_actor(*roles),
        ):
            return self.client.post(path, data=body, content_type="application/json")

    def test_only_requesters_may_create_types(self):
        res = self.post(
            "/api/v1/ai/request-types", ["APPROVER"], {"text": "đăng ký suất ăn trưa"}
        )
        self.assertEqual(res.status_code, 403)

    def test_unauthenticated_is_rejected(self):
        res = self.client.post(
            "/api/v1/ai/request-types/proposal",
            data={"text": "đăng ký suất ăn trưa"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 401)

    def test_proposal_and_creation_status_codes(self):
        with patch(
            f"{MOD}.propose",
            return_value={"proposal": {"name": "Đăng ký suất ăn trưa"}},
        ):
            res = self.post(
                "/api/v1/ai/request-types/proposal",
                ["REQUESTER"],
                {"text": "đăng ký suất ăn trưa"},
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["proposal"]["name"], "Đăng ký suất ăn trưa")
        with patch(
            f"{MOD}.create", return_value={"created": True, "type": {"code": "AI_1"}}
        ):
            res = self.post(
                "/api/v1/ai/request-types",
                ["REQUESTER"],
                {"text": "đăng ký suất ăn trưa"},
            )
        self.assertEqual(res.status_code, 201)
        with patch(
            f"{MOD}.create", return_value={"created": False, "type": {"code": "LEAVE"}}
        ):
            res = self.post(
                "/api/v1/ai/request-types", ["REQUESTER"], {"text": "xin nghỉ phép"}
            )
        self.assertEqual(res.status_code, 200)

    def test_missing_text_and_command_errors(self):
        res = self.post("/api/v1/ai/request-types/proposal", ["REQUESTER"], {})
        self.assertEqual(res.status_code, 422)
        with patch(
            f"{MOD}.propose", side_effect=CommandError("TEXT_UNCLEAR", status=422)
        ):
            res = self.post(
                "/api/v1/ai/request-types/proposal",
                ["REQUESTER"],
                {"text": "asdf qwer"},
            )
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["error"]["code"], "TEXT_UNCLEAR")


class OnboardingTests(SimpleTestCase):
    def test_escalated_routes_follow_the_group_plan(self):
        route = {
            "rules": [{"id": "R1", "default": True, "approvers": ["DIRECT_MANAGER"]}],
            "executor": "EXECUTOR_HR",
        }
        b = onb._escalated_route(route, "B", onb.ESCALATION_PLAN["PAYMENT"])
        c = onb._escalated_route(route, "C", onb.ESCALATION_PLAN["PAYMENT"])
        self.assertEqual(b["rules"][0]["approvers"], ["DIRECT_MANAGER", "FINANCE"])
        self.assertEqual((b["executor"], b["acceptor"]), ("EXECUTOR_FINANCE", None))
        self.assertEqual(
            c["rules"][0]["approvers"], ["DIRECT_MANAGER", "FINANCE", "DIRECTOR"]
        )
        self.assertEqual(c["acceptor"], "DIRECT_MANAGER")

    def test_escalation_never_exceeds_five_approvers(self):
        route = {
            "rules": [
                {"id": "R1", "default": True, "approvers": ["A1", "A2", "A3", "A4"]}
            ]
        }
        c = onb._escalated_route(route, "C", onb.ESCALATION_PLAN["PAYMENT"])
        self.assertEqual(len(c["rules"][0]["approvers"]), 5)

    def test_only_type_a_gets_escalation_releases(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(True,), ("B", "PEOPLE", {}, {}, {}, {})]
        self.assertEqual(
            onb.ensure_escalation_releases(cursor, type_id="t", actor_id="a"), []
        )

    def test_existing_escalation_releases_are_not_duplicated(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (True,),
            ("A", "PEOPLE", {}, {"rules": []}, {}, {}),
            (1,),
            None,
        ]
        self.assertEqual(
            onb.ensure_escalation_releases(cursor, type_id="t", actor_id="a"), ["C"]
        )

    def test_bad_cases_extend_only_when_the_nearest_type_is_close(self):
        cursor = MagicMock()
        self.assertEqual(
            onb.extend_bad_cases(
                cursor, type_code="AI_1", nearest_code="LEAVE", confidence=0.3
            ),
            [],
        )
        self.assertEqual(
            onb.extend_bad_cases(
                cursor, type_code="AI_1", nearest_code=None, confidence=0.9
            ),
            [],
        )
        cursor.execute.assert_not_called()
        cursor.fetchone.side_effect = [(True,), ("BC_LEAVE_X_AI_1",)]
        cursor.fetchall.return_value = [("BC_LEAVE_X", "t", "r", "c", 3, "B")]
        self.assertEqual(
            onb.extend_bad_cases(
                cursor, type_code="AI_1", nearest_code="LEAVE", confidence=0.9
            ),
            ["BC_LEAVE_X_AI_1"],
        )
