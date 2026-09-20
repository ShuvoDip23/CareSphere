# Architecture

## Why a rebuild

The previous prototype was a single 1,342-line `app.py` with module-level
globals, no application factory, no configuration layer, no migrations and no
tests. That structure made three things impossible: running the app under test,
deploying it anywhere other than a developer laptop, and letting three people
work on it without constant conflicts. Since this semester adds three new
feature areas built by three people in parallel, the structure has to change
first.

## Layout

```
backend/
  app/
    __init__.py        create_app() factory - the only place wiring happens
    config.py          Development / Testing / Production, all env-driven
    extensions.py      db, migrate, cors - instantiated unbound
    models/            one module per aggregate, all registered in __init__
    blueprints/        one package per feature area, routes only
    services/          business logic that is not HTTP-aware
    utils/             cross-cutting helpers (security, validation)
  migrations/          Alembic, via Flask-Migrate
  tests/               pytest, app/client/user fixtures in conftest.py
  wsgi.py              gunicorn entry point

frontend/
  assets/css/
    tokens.css         design tokens - the only file with raw colour values
    base.css           reset and element defaults
    components.css     reusable components, each defined exactly once
  assets/js/
    config.js          API origin, overridable at deploy time
    api.js             fetch wrapper, JSON helper, HTML escaping
    ui/                presentational helpers (toast, skeleton, modal)
```

## Key decisions

**Application factory.** `create_app(config_name)` builds an isolated app per
call, so tests get a throwaway in-memory database and production gets a real
one, with no global state shared between them.

**Blueprints registered one at a time.** `_register_blueprints` carries a
commented line per unported module with its owner and target week. A module is
enabled in the pull request that ports it, so each PR diff shows exactly one
feature arriving.

**Roles resolved from the database.** `utils/security.py` looks the user up on
every request. The prototype copied the role into the session at login, so a
promotion required re-login and a demotion did not take effect at all.

**Fail-fast production config.** `ProductionConfig.init_app` raises if
`SECRET_KEY` or `DATABASE_URL` is missing. The prototype shipped a hard-coded
fallback secret, which meant anyone reading the source could forge a session
cookie for any account.

**Design tokens before components.** Every colour, space and type size is a
custom property in `tokens.css`. The prototype ran a 58KB hand-written
stylesheet and the Tailwind CDN against each other on the same pages.

## Diagrams

To be added in week 2 (`docs/diagrams/`): ER diagram, module dependency
diagram, and the booking + payment sequence diagram.
