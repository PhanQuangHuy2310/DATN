"""Read-only per-type approval matrix and proposed versioned releases (A3/B3).

Nothing is created or published. The output JSON lists, for every published
request type, the current route and the proposed one, and the full proposed
route_rules / sla_profile a Policy Admin can submit as a new DRAFT release
version for review (config-releases API) once the owner approves.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from api_core.catalog.thesis_core_types import THESIS_CORE_CODES
from api_core.domain.approval_policy import (
    GENERAL_PURCHASING_TYPES,
    PRESERVED_STRICTER,
    apply_purchasing_ladder,
    describe_rules,
)
from api_core.domain.routing import MONETARY_PAYLOAD_FIELDS

THESIS_NOTES = {
    "LEAVE": "R01 (≤2 ngày): AI chỉ tư vấn, vẫn 1 cấp người duyệt (A1). "
    "R02 (>2 ngày) đồ án 1 cấp; hiện tại 2 cấp (thêm Giám đốc) — chặt hơn, giữ nguyên chờ xác nhận.",
    "ACCESS": "R06 đồ án: quyền quản trị cần IT_MANAGER → CISO; hiện tại DIRECT_MANAGER → DIRECTOR "
    "cho ứng dụng đặc quyền — cần quyết định.",
}


class Command(BaseCommand):
    help = "Print/write the per-type approval matrix and proposed releases (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="Write the JSON plan to this file")
        parser.add_argument(
            "--reminder-fraction",
            type=float,
            default=None,
            help="Also propose this SLA reminder fraction (0.8 needs migration 07)",
        )

    def handle(self, *args, **options):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """
                SELECT rt.code, rt.name, rt.lifecycle, cr.id::text, cr.version,
                       cr.route_rules, cr.sla_profile, cr.form_schema
                FROM eas.request_type rt
                JOIN eas.config_release cr ON cr.id = rt.active_release_id
                WHERE rt.is_active AND cr.state = 'PUBLISHED'
                ORDER BY rt.lifecycle, rt.code
                """
            )
            rows = cursor.fetchall()
        matrix, proposals = [], []
        for code, name, lifecycle, release_id, version, rules, sla, form in rows:
            props = set((form or {}).get("properties", {}))
            has_amount = bool(props & set(MONETARY_PAYLOAD_FIELDS))
            proposed = rules
            if code in GENERAL_PURCHASING_TYPES and has_amount:
                proposed = apply_purchasing_ladder(rules)
                if describe_rules(proposed) == describe_rules(rules):
                    proposed = rules  # same tiers; only ids/priorities differ
                change = "LADDER" if proposed != rules else "ALREADY_COMPLIANT"
                note = "Thang duyệt mua sắm chung R03–R05 (5/50 triệu)."
            elif code in PRESERVED_STRICTER:
                change, note = "PRESERVED", PRESERVED_STRICTER[code]
            elif code in GENERAL_PURCHASING_TYPES:
                change, note = "NO_AMOUNT_FIELD", "Biểu mẫu chưa có trường số tiền."
            else:
                change, note = "UNCHANGED", ""
            note = " ".join(filter(None, [note, THESIS_NOTES.get(code, "")]))
            new_sla = dict(sla)
            if options["reminder_fraction"] is not None:
                new_sla["reminder_fraction"] = options["reminder_fraction"]
            matrix.append(
                {
                    "code": code,
                    "name": name,
                    "lifecycle": lifecycle,
                    "thesis_core": code in THESIS_CORE_CODES,
                    "current_version": version,
                    "current": describe_rules(rules),
                    "proposed": describe_rules(proposed),
                    "change": change,
                    "note": note,
                }
            )
            if proposed != rules or new_sla != sla:
                proposals.append(
                    {
                        "code": code,
                        "base_release_id": release_id,
                        "base_version": version,
                        "route_rules": proposed,
                        "sla_profile": new_sla,
                    }
                )
        plan = {"matrix": matrix, "proposed_releases": proposals}
        text = json.dumps(plan, indent=2, ensure_ascii=False)
        if options["output"]:
            Path(options["output"]).write_text(text, encoding="utf-8")
            self.stdout.write(
                f"Wrote {len(matrix)} types, {len(proposals)} proposed releases to {options['output']}"
            )
        else:
            self.stdout.write(text)
