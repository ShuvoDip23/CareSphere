# CareSphere

[![CI](https://github.com/ShuvoDip23/CareSphere/actions/workflows/ci.yml/badge.svg)](https://github.com/ShuvoDip23/CareSphere/actions/workflows/ci.yml)

Smart healthcare through AI. An integrated healthcare coordination platform:
doctor discovery, a two-stage AI health assistant, appointment booking with
online payment, emergency assistance, prescription OCR, medication reminders,
blood donor coordination and ambulance services.

**CSE 3200 — Software Development Project II**
Department of Computer Science & Engineering, Rajshahi University of Engineering & Technology
Supervisor: Utsha Das, Assistant Professor

| Name | Roll | Lane |
| --- | --- | --- |
| Jit Banerjee Mithun | 2203127 | Prescription intelligence — OCR, medication reminders, notifications |
| Shuvo Dip Kar | 2203168 | Core platform — auth, doctors, appointments, payments, AI assistant, emergency, UI, CI/CD |
| Md. Istiak Ahmed Ifti | 2203177 | Community services — blood donor, ambulance, provider accounts |

## Relationship to previous work

CareSphere is a ground-up development project. The system is being built from the beginning with a focus on establishing a scalable and maintainable architecture. The project aims to develop key healthcare functionalities, including doctor discovery, an AI assistant, appointment booking, payment integration, and emergency assistance. Each module is being designed and implemented based on the proposed architecture, following modern software engineering practices to ensure reliability, security, and future extensibility.
[`docs/architecture.md`](docs/architecture.md) and hardened as it is ported.
[`docs/PORTING.md`](docs/PORTING.md) tracks that work module by module, and
[`docs/prototype-review.md`](docs/prototype-review.md) records the defects found
in the prototype that this rebuild is required to fix.

## Quick start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate      # macOS / Linux
pip install -r requirements-dev.txt
copy .env.example .env          # then fill in the values
flask --app wsgi db upgrade
flask --app wsgi seed            # demo specialties, doctors and hours
flask --app wsgi run --port 5000
```

The API is then at <http://127.0.0.1:5000>. Check `GET /api/health`.

### Frontend

Serve `frontend/` on port 5500 (VS Code Live Server, or
`python -m http.server 5500 --directory frontend`) and open
<http://127.0.0.1:5500>.

> Use `127.0.0.1` for both, not `localhost`. The browser treats them as
> different sites, so mixing them silently drops the session cookie.

### Checks

```bash
cd backend && ruff check . && ruff format --check . && pytest
npm install && npm run lint && npm run format:check
```

These are exactly what CI runs. Run them before you push.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: branch, commit, open a
PR, get it reviewed by another team member, let CI go green, then merge.
Nobody merges their own pull request.
