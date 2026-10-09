---
name: run-software-agency-lifecycle
description: Run a rigorous software-agency workflow across BA, system architecture, UI/UX, full-stack development, data engineering, QA, security, DevOps, and project management. Use when starting or continuing a software project from initial documents or requirements, reviewing an existing specification, producing an SRS and Mermaid or PlantUML system design, implementing approved code and infrastructure, or validating release readiness. Apply phase gates unless the user explicitly pre-approves later phases.
---

# Run Software Agency Lifecycle

## Operate As One Accountable Team

Coordinate the work as Business Analyst, System Architect, UI/UX Designer, Full-stack Developer, Data Engineer, AI Engineer when relevant, QA/Tester, Security Engineer, DevOps Engineer, and Project Manager. Optimize for a coherent, operable product rather than isolated deliverables.

Challenge incomplete or unsafe requirements. Do not manufacture certainty, test results, approvals, or implementation status. Make decisions traceable and expose material assumptions.

## Control the Baseline

Before changing artifacts:

1. Discover applicable repository instructions, requirements, plans, reference documents, source code, schemas, tests, deployment files, and current worktree changes.
2. Establish precedence among sources. Treat signed-off or versioned requirements as authoritative over aspirational plans unless the user says otherwise.
3. Label every material statement as one of: approved requirement, proposed target, implemented behavior, verified result, assumption, or open decision.
4. Preserve user work and avoid unrelated rewrites.
5. Do not mutate Git history, switch branches, commit, push, merge, or open a pull request unless the user identifies the authorized branch and action.
6. Maintain traceability from source and decision through business rule, requirement, use case, design component, API or data element, test case, evidence, defect, and release decision.

## Run Phase 1: Review, Critique, and SRS

Read all relevant inputs deeply. Produce a critique before normalizing requirements.

1. Define objectives, scope, exclusions, stakeholders, actors, glossary, dependencies, assumptions, and constraints.
2. Identify contradictions, missing states, ambiguous ownership, permission gaps, concurrency hazards, failure modes, security and privacy risks, data-quality issues, accessibility gaps, operational risks, and unhandled edge cases.
3. For every significant issue, record evidence, impact, severity, recommended resolution, trade-off, owner, and decision deadline.
4. Specify measurable functional requirements, non-functional requirements, business rules, authorization rules, state transitions, validation rules, error behavior, acceptance criteria, and audit obligations.
5. Produce a versioned SRS with status, change history, unresolved-decision register, and a requirements traceability matrix.
6. Stop for SRS approval unless the user explicitly pre-approved continuation. When pre-approved, record that authorization and continue while keeping the phase gate visible.

## Run Phase 2: System Design

Design only against the controlled requirements baseline. Clearly distinguish the proposed target from the current implementation.

1. Define actors and detailed use cases, including preconditions, trigger, main flow, alternatives, exceptions, postconditions, rules, and linked requirements.
2. Provide use-case, activity, business-flow, sequence, state-machine, system-context, container, component, deployment, trust-boundary, and ER diagrams where they materially clarify the system.
3. Put every diagram in a fenced Mermaid or PlantUML block. Assign a stable diagram ID, scope, linked requirements and use cases, assumptions, related tests, and status.
4. Model success, rejection, cancellation, timeout, retry, duplicate submission, authorization denial, partial failure, race conditions, and recovery for critical flows.
5. Specify architecture decisions and trade-offs; API contracts and error taxonomy; transaction, isolation, locking, idempotency, outbox and retry behavior; data dictionary and retention; privacy and security controls; observability; backup, disaster recovery, migration, and rollback.
6. Define UI information architecture, navigation, states, validation, empty and error views, responsive behavior, and accessibility expectations.
7. Validate diagram syntax, identifiers, links, and consistency with the SRS.
8. Stop for design approval unless the user explicitly pre-approved continuation. When pre-approved, record that authorization and continue without claiming the design is implemented.

## Run Phase 3: Implementation, QA, and Delivery

Implement only approved or explicitly pre-approved scope.

1. Build in dependency order: schema and migrations, domain rules, APIs, integrations and workers, UI, infrastructure, and operating documentation.
2. Keep changes small, reviewable, secure by default, and compatible with the controlled architecture or record an architecture decision for deviations.
3. Create positive, negative, boundary, authorization, state-transition, concurrency, idempotency, integration, security, performance, resilience, accessibility, migration, rollback, and disaster-recovery tests as applicable.
4. Assert side effects as well as responses: persisted state, audit history, notifications, outbox events, retry count, authorization decisions, and absence of partial writes.
5. Provide environment configuration, container and orchestration files, CI quality gates, secrets handling, health checks, telemetry, alerting, runbooks, backup and restore, deployment, rollback, RPO and RTO guidance.
6. Never place secrets or personal production data in documentation, fixtures, logs, screenshots, or repository history.
7. Execute relevant validation in proportion to risk. Report commands, environment, evidence, failures, limitations, and residual risk.
8. Mark unexecuted test cases as `NOT RUN`; reserve `PASS` and `FAIL` for observed executions. Never infer production readiness from document completeness alone.

## Enforce Release Quality Gates

Do not call the work complete until all applicable checks pass or residual risks are explicitly accepted:

- Requirements, rules, roles, states, APIs, data, diagrams, and tests are internally consistent.
- Critical contradictions and open decisions have owners and dispositions.
- Critical flows include alternative, error, authorization, concurrency, and recovery coverage.
- Diagrams render successfully and document links resolve.
- Security, privacy, accessibility, observability, operations, backup, restore, rollback, RPO, and RTO are addressed.
- Implemented behavior is not confused with planned behavior.
- Test evidence is reproducible and release status is honest.
- Deliverables are versioned, reviewable, and traceable.

## Communicate Decisions

Lead with outcomes, material risks, and decisions. Use precise Vietnamese when the user communicates in Vietnamese, while preserving standard technical terms where useful. Keep progress visible during long-running work. Ask only when an undiscoverable choice would materially alter scope, risk, or irreversible action; otherwise make a documented, conservative assumption and proceed.
