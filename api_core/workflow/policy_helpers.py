"""Pure helpers for policy draft preparation and fail-closed publish checks.

A template is NEVER a published policy. Human administrators must configure
real department bindings and grant scoped memberships before operational use.
"""
from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from api_core.domain.routing import APPROVER_SLOTS, EXECUTOR_SLOTS, ACCEPTOR_SLOTS


# Readable mapping from the plan's approval-route descriptions to existing
# single-executor engine slots. These are only suggested DRAFT routes.
# Routes with parallel execution (RESIGNATION) are not publishable by P0.
PLAN_ROUTE_SUGGESTIONS = {
    'RESIGNATION': (['DIRECT_MANAGER', 'HR_MANAGER', 'DIRECTOR'], 'EXECUTOR_HR', 'REQUESTER'),
    'OVERTIME_REQ': (['DIRECT_MANAGER'], 'EXECUTOR_HR', None),
    'WFH_REQ': (['DIRECT_MANAGER'], None, None),
    'ROOM_VEHICLE': (['DIRECT_MANAGER'], 'EXECUTOR_ADMIN', None),
    'ADVANCE_SMALL': (['DIRECT_MANAGER','FINANCE'], 'EXECUTOR_FINANCE', None),
    'ADVANCE_MEDIUM': (['DIRECT_MANAGER','FINANCE'], 'EXECUTOR_FINANCE', None),
    'ADVANCE_LARGE': (['DIRECT_MANAGER','FINANCE','DIRECTOR'], 'EXECUTOR_FINANCE', None),
    'REIMBURSEMENT': (['DIRECT_MANAGER','FINANCE'], 'EXECUTOR_FINANCE', None),
    'VENDOR_PAYMENT': (['DIRECT_MANAGER','FINANCE','DIRECTOR'], 'EXECUTOR_FINANCE', 'DIRECT_MANAGER'),
    'PROD_DATA_ACCESS': (['DIRECT_MANAGER','SECURITY','CTO'], 'EXECUTOR_IT', 'CTO'),
    'SAAS_LICENSE_BUY': (['DIRECT_MANAGER','IT_MANAGER','FINANCE'], 'EXECUTOR_PROCUREMENT', 'DIRECT_MANAGER'),
    'ASSET_PURCHASE': (['DIRECT_MANAGER','PROCUREMENT_MANAGER','FINANCE'], 'EXECUTOR_PROCUREMENT', 'DIRECT_MANAGER'),
    'FACILITY_REPAIR': (['OPERATIONS_MANAGER'], 'EXECUTOR_FACILITY', 'DIRECT_MANAGER'),
}

def initial_policy_draft(type_code: str, lifecycle: str) -> dict:
    """Prefer the versioned plan's draft spec, otherwise a safe editable starter.

    This function does not manufacture staff IDs, grants, or AI auto approval.
    """
    from api_core.catalog.plan_catalog import plan_item
    from pathlib import Path
    import json

    path = Path(__file__).resolve().parents[2] / 'docs' / 'APPROVAL_MENU_POLICY_DRAFTS.json'
    draft = None
    if plan_item(type_code) and path.is_file():
        blueprints = json.loads(path.read_text(encoding='utf-8'))
        draft = next((p for p in blueprints.get('drafts', []) if p.get('code') == type_code and p.get('lifecycle') == lifecycle), None)
    if draft:
        keys = ('form_schema', 'route_rules', 'actor_bindings', 'sla_profile')
        return {'source': 'PLAN_DRAFT', **{key: deepcopy(draft[key]) for key in keys}}

    route = {'schema_version': 1,
             'rules': [{'id': f'{type_code}-DEFAULT', 'default': True, 'approvers': ['DIRECT_MANAGER']}],
             'executor': None if lifecycle == 'A' else 'EXECUTOR_ADMIN',
             'acceptor': 'REQUESTER' if lifecycle == 'C' else None}
    form = {'schema_version': 1, 'type': 'object', 'additionalProperties': False,
            'properties': {'title': {'type': 'string', 'minLength': 5, 'maxLength': 150},
                           'reason': {'type': 'string', 'minLength': 10, 'maxLength': 2000}},
            'required': ['title', 'reason']}
    sla = {'schema_version': 1, 'clock': 'CALENDAR_UTC', 'reminder_fraction': .5,
           'approval_hours': 24, 'execution_hours': 48 if lifecycle != 'A' else None,
           'acceptance_hours': 24 if lifecycle == 'C' else None}
    item = plan_item(type_code)
    if item and item['lifecycle'] == lifecycle:
        form = deepcopy(item['form_schema'])
        sla['approval_hours'] = max(1, min(720, int(item.get('sla_hours', 24))))
        suggested = PLAN_ROUTE_SUGGESTIONS.get(type_code)
        if suggested:
            slots, executor, acceptor = suggested
            route.update({'rules':[{'id':f'{type_code}-DEFAULT', 'default':True, 'approvers':slots}],
                          'executor':executor,'acceptor':acceptor})
        return {'source':'PLAN_FORM_ROUTE_SUGGESTION', 'form_schema': form,
                'route_rules':route, 'actor_bindings':{'schema_version':1, 'departments':{}},
                'sla_profile':sla}
    return {'source': 'SAFE_STARTER', 'form_schema': form, 'route_rules': route,
            'actor_bindings': {'schema_version': 1, 'departments': {}}, 'sla_profile': sla}


def binding_errors(route_rules: dict, actor_bindings: dict) -> list[str]:
    """Block publish if any department cannot resolve each configured slot.

    The database still authorizes all assigned people with live, scoped role
    memberships during submission; this only checks static coverage and UUIDs.
    """
    errors = []
    if not isinstance(route_rules, dict) or not isinstance(actor_bindings, dict):
        return ['actor_bindings:invalid structure']
    depts = actor_bindings.get('departments')
    if not isinstance(depts, dict) or not depts:
        return ['actor_bindings:at least one department with verified actor assignments is required']
    slots = set()
    for rule in route_rules.get('rules', []):
        if isinstance(rule, dict):
            slots.update(s for s in rule.get('approvers', []) if s in APPROVER_SLOTS and s != 'DIRECT_MANAGER')
    for name, allowed in [('executor', EXECUTOR_SLOTS), ('acceptor', ACCEPTOR_SLOTS)]:
        slot = route_rules.get(name)
        if slot in allowed and slot not in {None, 'REQUESTER', 'DIRECT_MANAGER'}:
            slots.add(slot)
    for dept_id, mapping in depts.items():
        try:
            UUID(str(dept_id))
        except (ValueError, AttributeError, TypeError):
            errors.append('actor_bindings:invalid department UUID')
            continue
        if not isinstance(mapping, dict):
            errors.append(f'actor_bindings:{dept_id}:must be a slot mapping')
            continue
        for slot in sorted(slots):
            try:
                UUID(str(mapping[slot]))
            except (KeyError, ValueError, TypeError, AttributeError):
                errors.append(f'actor_bindings:{dept_id}:missing/invalid {slot} UUID')
    return errors


def role_grant_errors(cursor, type_id: str, route_rules: dict, actor_bindings: dict) -> list[str]:
    """Verify current role grants for explicit policy assignees at validation time.

    The runtime always re-checks grants under request submission locks, so a
    role revoked *after* publication can never be used to route a new request.
    """
    errors = binding_errors(route_rules, actor_bindings)
    if errors:
        return errors
    depts = actor_bindings['departments']
    assignments = {}
    for rule in route_rules.get('rules', []):
        for slot in rule['approvers']:
            if slot != 'DIRECT_MANAGER':
                assignments[(slot, 'APPROVER')] = True
    for key, role in [('executor','EXECUTOR'),('acceptor','ACCEPTOR')]:
        slot = route_rules.get(key)
        if slot not in (None,'DIRECT_MANAGER','REQUESTER'):
            assignments[(slot,role)] = True
    for dept_id, mapping in depts.items():
        cursor.execute('SELECT is_active FROM eas.department WHERE id=%s', [dept_id])
        row = cursor.fetchone()
        if not row or not row[0]:
            errors.append(f'actor_bindings:{dept_id}:department inactive or missing')
            continue
        for slot, role in sorted(assignments):
            assignee = mapping[slot]
            cursor.execute(
                """
                SELECT EXISTS (
                  SELECT 1 FROM eas.app_user u
                  JOIN eas.role_membership m ON m.user_id=u.id
                  WHERE u.id=%s AND u.is_active AND m.role=%s
                    AND m.revoked_at IS NULL
                    AND m.valid_from<=statement_timestamp()
                    AND (m.valid_to IS NULL OR m.valid_to>statement_timestamp())
                    AND (m.type_scope='ALL' OR
                         (m.type_scope='ONE' AND m.type_id=%s))
                    AND (m.scope_kind='GLOBAL' OR
                         (m.scope_kind='DEPARTMENT' AND m.department_id=%s))
                )
                """, [assignee,role,type_id,dept_id]
            )
            if not cursor.fetchone()[0]:
                errors.append(f'actor_bindings:{dept_id}:{slot} requires active {role} grant in type/department scope')
        # Check static conflicts within every possible approval rule.
        for rule in route_rules.get('rules', []):
            approver_ids = [mapping[slot] for slot in rule['approvers'] if slot != 'DIRECT_MANAGER']
            if len(approver_ids) != len(set(approver_ids)):
                errors.append(f'actor_bindings:{dept_id}:same approver assigned to distinct steps')
            executor_slot = route_rules.get('executor')
            acceptor_slot = route_rules.get('acceptor')
            executor_id = mapping.get(executor_slot) if executor_slot not in (None, 'DIRECT_MANAGER') else None
            acceptor_id = mapping.get(acceptor_slot) if acceptor_slot not in (None, 'DIRECT_MANAGER','REQUESTER') else None
            if executor_id and executor_id in approver_ids:
                errors.append(f'actor_bindings:{dept_id}:executor cannot also approve')
            if executor_id and acceptor_id and executor_id == acceptor_id:
                errors.append(f'actor_bindings:{dept_id}:executor cannot also accept')
    return list(dict.fromkeys(errors))
