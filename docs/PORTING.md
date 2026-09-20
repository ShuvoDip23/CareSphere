# Porting and delivery schedule

CareSphere is rebuilt module by module on the new architecture. This file is
the single source of truth for what is done, what is in progress, and who owns
what. **Update the relevant row in the same PR that changes its status.**

Status values: `not started` · `in progress` · `in review` · `done`

## Core platform — Shuvo (2203168)

| # | Module | Proposal § | Week | Status | Hardening required during the port |
| --- | --- | --- | --- | --- | --- |
| 1 | App factory, config, CI/CD, auth | 4.1 | 1 | done | PBKDF2 password hashing; no role from request body; fail-fast secret |
| 2 | Doctor discovery + availability | 4.2 | 1 | done | Specialty is now its own table with a unique slug; all reads are side-effect free |
| 3 | Appointment booking | 4.4 | 3 | not started | TTL releases abandoned `payment_pending` slots instead of locking them forever |
| 4 | Payments (SSLCommerz) | 4.5 | 4 | not started | **Verify the gateway signature.** Prototype confirmed payment from unauthenticated query params |
| 5 | Two-stage AI assistant | 4.3 | 5 | not started | Reconcile urgency levels to Routine / Urgent / Emergency per the proposal |
| 6 | Chat history | 4.6 | 6 | not started | Ownership check on every session read |
| 7 | Emergency assist | 4.7 | 6–7 | not started | Real Rajshahi hospital data; add PDF export and directions link |
| 8 | Doctor dashboard | 4.1 | 8 | not started | New — prototype doctors could log in but saw nothing |
| 9 | UI system rollout | — | 2–10 | in progress | Tokens and components applied to every page as it is ported |
| 10 | Admin console (doctor CRUD) | 4.1 | 1 | done | Role resolved from the DB on every request; validation shared with week-2 doctor signup |
| 11 | Doctor self-registration + approval queue | 4.1 | 2 | not started | Reuses `blueprints/admin/validators.py`; edits to an approved profile drop it back to pending |
| 12 | Doctor dashboard | 4.1 | 2 | not started | Approval state, profile editing, rejection note |

## Community services — Ifti (2203177)

| # | Module | Proposal § | Week | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 10 | Blood donor model + search | 4.9 | 3–4 | not started | Search by group, location, availability; last donation date |
| 11 | Donor contact-request flow | 4.9 | 5 | not started | Donor phone numbers are never returned directly — request/approve only |
| 12 | Service-provider accounts | 4.1 | 5 | not started | `User.ROLE_PROVIDER` already exists; blood banks and ambulance operators use it |
| 13 | Ambulance directory | 4.10 | 6 | not started | Same shape as the donor directory — reuse the search service |
| 14 | Attendant accommodation | 1, 8 | 8 | not started | Listed in the proposal narrative but missing from §4 — add a §4.11 |

## Prescription intelligence — Jit (2203127)

| # | Module | Proposal § | Week | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 15 | OCR feasibility spike | 4.8 | 1 | not started | **Do this first.** Decide Tesseract vs EasyOCR and, critically, whether handwritten prescriptions are in scope |
| 16 | Prescription upload + storage | 4.8 | 3 | not started | Validate MIME type and size; store outside the repo |
| 17 | OCR extraction pipeline | 4.8 | 4–5 | not started | Extract medicine name, dose, frequency |
| 18 | Patient verification UI | 4.8 | 6 | not started | The patient corrects OCR output before anything is saved — never trust extraction |
| 19 | Medication reminders | 4.8 | 7 | not started | Schedule model + browser notifications |

## Risk register

| Risk | Owner | Mitigation |
| --- | --- | --- |
| OCR cannot read handwritten Bangladeshi prescriptions | Jit | Week 1 spike decides scope. Fall back to printed prescriptions and pharmacy labels |
| SSLCommerz sandbox credentials expire or change | Shuvo | Payment service isolated behind an interface so it can be stubbed in tests |
| Three people editing shared files | All | Lane ownership via CODEOWNERS; blueprints keep features in separate packages |
| Scope is larger than one semester | All | Modules 14 and 19 are explicitly the first to be cut if the schedule slips |
