# Week 1 — 12 September 2026

**Milestone:** repository, pipeline and authentication foundation
**Tag:** `v0.1.0-week1`

## Delivered

| PR | Author | Reviewer | Content |
| --- | --- | --- | --- |
| #1 | Shuvo | Mithun | Repository scaffold, `.gitattributes`, `.gitignore`, README, CONTRIBUTING, CI workflow |
| #2 | Shuvo | Jit | Application factory, config layer, User model, auth blueprint, 8 tests |
| #3 | Ifti | Shuvo | Blood donor data model, migration, seed script |
| #4 | Jit | Shuvo | OCR feasibility spike and recommendation |
| #5 | Shuvo | Ifti | Doctor discovery module, directory and profile pages, 12 tests |
| #6 | Shuvo | Jit | Admin console: doctor CRUD, availability editor, role-based routing, 18 tests |

## Demonstrated to the supervisor

1. Repository with three collaborators and branch protection on `main`
2. CI running on every pull request — lint, tests, security scan
3. Contributors graph showing all three members
4. Architecture: why the rebuild, what the factory pattern buys us
5. Authentication working, with the password hashing defect from the prototype
   fixed and covered by a regression test
6. OCR feasibility findings and the resulting scope decision
7. Admin console: adding a doctor live, and it appearing in the public directory

## Decisions taken

-
-

## Next week

- Appointment booking module (Shuvo)
- Donor search endpoint (Ifti)
- Prescription upload endpoint (Jit)
