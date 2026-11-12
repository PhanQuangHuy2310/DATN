# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

The employee portal (`web_client`) and the administration portal (`web_admin`) are React/Vite web apps. A separate Flutter app (`mobile_app`) exists; this record covers the web portals.

## Users

- **Office employees** create requests on a desktop computer during working hours: leave, advances, purchases, IT and access requests, bookings, and the like. They track progress and respond when information is requested.
- **Managers and heads of department** approve many requests a day. They need to read a request, its attachments and the AI advice quickly, then decide.
- **Executors and acceptors** carry out approved work, submit evidence, and accept or send back the result.
- **Auditors** look up requests and the audit trail, read-only.
- **System administrators** (operations and policy) work only in the separate administration portal. They manage users, roles, workflows, regulations, AI and integrations.

## Product Purpose

EAS (Enterprise Approval System) receives and approves internal company requests end to end:
- creation from a catalogue of request forms;
- approval chains;
- execution;
- acceptance;
- full traceability.

Success means:
- requests reach the right people automatically;
- decisions are made within the SLA;
- every decision can be explained and audited afterwards.

## Positioning

- **AI advises, people decide.** The AI service recommends, and the assigned approver makes every decision. Each recommendation cites the company regulation clause it was checked against (regulation, version, clause, quoted text, the comparison made). When a regulation changes, the AI relearns and the new rules apply to the next request.
- **Three lifecycles with SLA.** Every request type follows lifecycle A (approve only), B (approve then execute) or C (approve, execute, accept). Each step has an SLA, automatic assignment and escalation, and delegation while an approver is absent.
- **External systems through APIs only.** Requests are checked against HR, finance, asset, facility and IT systems; the system never reaches into their databases. Here those systems are simulated by the Mock Systems API.
- **Transparent audit and separation of duties.** The audit chain is hash-linked and tamper-evident. The requester can never approve, execute or accept their own request. Access is role- and position-based (RBAC), and administrators stay out of business decisions.

## Operating Context

- **Employee portal:** dashboard, request creation by request group, "my requests" as Kanban or list, assigned work, request detail with tabs (information, progress, approvers, attachments, AI assessment, activity, flow diagram), department dashboards for managers, org chart, regulations, account and delegation.
- **Administration portal:** operations overview, users and roles, permission matrix, request workflows, regulations and AI management, API management, system versions.
- **Request catalogue:** 58 request types in 12 business groups across lifecycles A/B/C. Forms are defined by published configuration releases.

## Capabilities and Constraints

- Backend: Django API with raw SQL on Supabase PostgreSQL, a background worker, a FastAPI AI service (optional; rule-based fallback when absent), Redis cache. Browsers never talk to Supabase directly.
- Security rules in `AGENTS.md` are binding:
  - strict CSP;
  - no secrets in the frontend;
  - generic error messages with no technical details;
  - RBAC checked on the server.
- Terminology:
  - "yêu cầu" / "hồ sơ" for a request;
  - "phê duyệt", "thực hiện", "nghiệm thu" for the three stages;
  - "ủy quyền" for delegation;
  - "quy chế" / "quy định" for company regulations.

## Brand Commitments

- Product name: **EAS** (Enterprise Approval System). The portals are "EAS Portal" (employees) and "EAS Admin" (administration).
- All user-facing text is Vietnamese: labels, messages, errors and notifications. Backend error codes must never reach the user untranslated.

## Evidence on Hand

- This is a graduation thesis project (DATN, Nhóm 07). There are no real customers, testimonials, production metrics, certifications or press. Data is demo or seed data, and future work must not invent any of these.
- Product and design documentation is in `docs/` (request taxonomy, lifecycle and auto-assignment, external integrations, schema v2, UI functions and permissions) and `workspace/` (thesis report and analysis/design documents).

## Product Principles

1. **The human decides; the system explains.** Every automated suggestion shows its source and reasoning, and no automation finalises a business decision on its own authority.
2. **The right person, on time.** Routing, SLA, escalation and delegation exist so that no request waits on someone who cannot act.
3. **Nothing happens off the record.** Every state change is attributable and auditable, and segregation of duties is never relaxed for convenience.
4. **The employee never decodes the system.** Clear Vietnamese language, validation before submit, and errors that name the problem and the fix.

## Accessibility & Inclusion

The target is WCAG 2.1 AA. This covers:
- text and control contrast;
- full keyboard operation with visible focus;
- labelled controls and screen-reader names;
- support for reduced motion.
