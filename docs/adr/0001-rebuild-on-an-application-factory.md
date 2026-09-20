# ADR 0001 — Rebuild on an application factory

**Status:** accepted
**Date:** 2026-09-07

## Context

The previous semester's prototype delivered working features but placed all
routing, configuration and business logic in a single `app.py` with
module-level state. Three developers now need to add three independent feature
areas in parallel, and the project needs to be testable and deployable.

## Decision

Rebuild on a Flask application factory with blueprints, a configuration class
per environment, Alembic migrations and a pytest suite. Port the prototype's
features module by module rather than importing the code wholesale, fixing the
defects recorded in `docs/prototype-review.md` as each module is ported.

## Consequences

- Every module can be tested in isolation with a throwaway database.
- Feature areas live in separate packages, so three people can work without
  conflicting on the same files.
- Porting costs more time than copying, and features become available later in
  the semester. This is accepted because the prototype's payment flow and
  password storage were not safe to carry forward unchanged.
