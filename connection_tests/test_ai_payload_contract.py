"""Dependency-light contract test for the Django AI client (no live networking)."""

import asyncio
import unittest
from unittest.mock import patch

from api_core.ai_client import AIServiceClient


class AIContractTests(unittest.TestCase):
    def test_risk_field_names_and_values(self):
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"risk_score": 2, "fallback_used": False}

        class Client:
            def __init__(self, timeout):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def post(self, url, json, headers):
                self_url = url
                assert self_url.endswith("/ai/risk/score")
                assert json["amount_vnd"] == 45_000_000
                assert json["num_attachments"] == 3
                assert json["past_requests_count"] == 4
                assert json["past_rejection_rate"] == 0.25
                assert json["is_off_hours"] == 1
                assert "amount" not in json
                return Response()

        with patch("api_core.ai_client.httpx.AsyncClient", Client):
            result = asyncio.run(
                AIServiceClient().score_risk(
                    "advance_payment",
                    "A",
                    2,
                    amount=45_000_000,
                    attachment_count=3,
                    request_count_30d=4,
                    reject_count_30d=1,
                    is_weekend_or_holiday=True,
                )
            )
        self.assertFalse(result["fallback_used"])

    def test_classify_route_contract_exists(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        client = (root / "api_core" / "ai_client.py").read_text(encoding="utf-8")
        server = (root / "ai_service" / "routers" / "classify.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("/ai/classify/request", client)
        self.assertIn('@router.post("/request"', server)


if __name__ == "__main__":
    unittest.main()
