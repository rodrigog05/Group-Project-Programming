# AGENTS.md

Project-agnostic instructions for coding agents. Follow for every task. Repository instructions/spec may add constraints but cannot weaken these without explicit human approval.

## Default stack

Use simplest stack satisfying product requirements and explainable to every member.

Preferred:

- Python
- Streamlit for forms, tables, charts, dashboards, small interactive apps
- SQLite for local/single-user persistence
- `pytest` for tests
- `uv` for dependency/command management

Choose another stack only when requirements justify it: custom responsive UI, games, mobile clients, real-time multi-user state, or consumed APIs. Record choice/reason in `README.md` or architecture notes. Do not mix stacks without clear need or switch late without human approval.

Before stack changes, verify:

- interface/interaction model
- persistence/concurrency needs
- hosting support
- dependency/operational cost
- team maintainability

Document current stack, app/test/deployment commands explicitly in `README.md`; keep current.

## Repository rules

- Read `README.md`, relevant specs, existing tests, nearby code before editing.
- One task, bug, or spec at a time.
- Use task-named branch; never commit directly to `main`.
- Keep scope tight. No unrelated refactors, redesigns, dependency upgrades, or features.
- Keep commits small/explainable; commit only after relevant checks pass.
- Never edit, delete, skip, weaken, or reorder tests to pass. If test conflicts with requirements, stop and report.
- Do not edit generated files, seed/deployed data, or destructively effective config unless explicitly required.
- Never create, read, print, commit, or modify secrets; expose no credentials, tokens, passwords, private keys, or real personal data.
- Keep `.env` and secret-bearing files out of version control. Document env-var names only with safe examples.
- No destructive actions against shared/prod/deployed resources without explicit confirmation.
- Claim commands passed only when output proves it.

## Task contract

Before implementation, identify/request spec with exactly:

### Why

Short user value and intent.

### What

Concrete, checkable behaviour; one checklist item/expected behaviour. Include accepted/rejected actions, unchanged state after rejection, persistence, and relevant errors.

### Out of scope

Tempting adjacent work excluded.

### Done when

Proof required: tests, manual checks, deployment checks, repository state. Include stop condition and run cap for repeated automation.

Without adequate spec, create/propose one before coding. Do not infer broad scope from short requests.

## Verification workflow

1. Inspect state; run relevant existing tests.
2. Add/review checklist tests before implementation when practical.
3. Implement smallest complete change; no placeholders, dead paths, knowingly incomplete workflows.
4. Run focused tests after each meaningful change.
5. Read failures from bottom; fix cause; rerun.
6. Run full suite.
7. Read diff; inspect changed files.
8. Run app; manually verify each user-facing acceptance scenario.
9. Report commands, exact results, changed files, limitations.

Tests are evidence, not product review. Green suite is insufficient for visual, interactive, deployment-specific, or untested requirements.

If same failure remains after two correction attempts, stop. Explain failure, evidence, likely cause, next action. Resume only with better spec/new information.

## Test expectations

Cover as applicable:

- successful primary workflows
- invalid input/rejected actions
- unchanged state after rejection
- boundaries/empty states
- persistence across restart/reload
- permissions/role boundaries
- external failure, timeout, fallback
- important regressions

Tests deterministic/fast. Mock external APIs, model providers, email services, clocks, randomness. No real credentials, deployed DBs, network, quotas, or model output dependencies.

## Product and UX quality

Complete entry-to-visible-result workflows. App must:

- fit problem/user
- make primary actions easy
- validate before unsafe/invalid operations
- show clear success, empty, loading, error states
- preserve valid data after acceptance
- reject invalid actions without corruption
- give useful feedback without internals/secrets
- work on supported sizes/input methods

Prefer reliable, understandable behaviour over risky polish or unclear interaction.

## Security and reliability

- Validate untrusted input at boundary; enforce authorization server-side.
- Least privilege for accounts/services/database.
- Parameterize DB queries; avoid unsafe shell, HTML, SQL, template interpolation.
- Pin/constrain dependencies per package manager; avoid unnecessary packages.
- Check dependency vulnerabilities when tooling supports it.
- External services: bounded timeouts, safe fallback, user-visible status.
- Separate local/test/prod data.
- Assume no local file, secret, DB, or warm process exists in deployment.

## Deployment and demo readiness

Before declaring complete:

- verify public URL/deployment target
- confirm deployed code matches intended `main`
- run full demo deployed, not only locally
- verify DB, host, auth, API, model, real-time dependencies
- confirm demo accounts/starting data
- test invalid input/dependency failure
- prepare safe fallback per external dependency
- ensure shared screens show no secrets/private dashboards

No untested last-minute feature change before demo.

## Repository and walkthrough standard

Keep repo understandable to newcomers. When applicable, `README.md` documents:

- purpose/main workflows
- deployed URL
- project members
- stack and reason
- tools/setup
- local app, test, seed, lint, deployment commands
- env-var names only, never values
- storage/reset strategy
- external services/failure behaviour
- test coverage/known limits
- structure/ownership boundaries

Every member can explain main parts, design reasons, limitations, security, tests, and likely next changes.

## Evaluation criteria

Optimize all criteria, not feature count:

1. **It works:** deployed primary/invalid-input workflows work without crashes/workarounds.
2. **User interface and experience:** fit problem; direct actions; clear results, empty states, errors.
3. **Scope and ambition:** coherent product; exceeds minimal prototype when required; no disconnected extras.
4. **Verification:** accepted/rejected actions, edge cases, persistence, regressions covered; all pass on `main`.
5. **Security:** no credentials; access control/input validation enforced; dependencies minimal/maintained.
6. **Repository walkthrough:** decisions, limits, tests, deployment, data, failure handling understandable.

Do not trade reliability, verification, security, explainability for ambition.

## Completion report

Report:

- implemented behaviour summary
- changed files
- tests/validation commands
- exact final results/counts/decisive output
- manual/deployed checks
- limitations/follow-up

Never report “done” from inspection or assumption alone.
