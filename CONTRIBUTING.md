# Contributing

## Ground rules

1. **`main` is protected.** All changes arrive through a pull request.
2. **Every PR needs one approving review from another team member.** This is
   how the repository records that the work was done jointly.
3. **Nobody merges their own PR.**
4. **Everyone pushes from their own GitHub account.** Never commit on a
   teammate's behalf from one laptop — the contributors graph is part of what
   is assessed. If you genuinely pair, use a co-author trailer:

   ```
   Co-authored-by: Name <email@example.com>
   ```

5. **Never commit** `.env`, `*.db`, `node_modules/`, `venv/`, or any real
   credential. `.gitignore` covers these; do not override it.

## Branches

```
feat/<lane>-<short-description>     feat/donor-search-endpoint
fix/<short-description>             fix/payment-signature-check
docs/<short-description>            docs/week-3-report
chore/<short-description>           chore/bump-ruff
```

Branch off `main`, keep branches short-lived, rebase rather than merge `main`
into your branch.

## Commit messages

Conventional Commits:

```
<type>(<scope>): <summary in the imperative mood>

feat(donors): add blood group and location search
fix(payments): validate SSLCommerz signature before confirming
test(auth): cover role escalation attempt
docs(porting): mark appointments module complete
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.

## Definition of done

A module is not done until all of these are true:

- [ ] Endpoints implemented and returning correct status codes
- [ ] Model registered in `backend/app/models/__init__.py`
- [ ] Migration generated and committed
- [ ] Tests written, including at least one failure case
- [ ] `ruff check`, `ruff format --check` and `pytest` pass locally
- [ ] Frontend passes `npm run lint` and `npm run format:check`
- [ ] CI green on the PR
- [ ] Reviewed and approved by another team member
- [ ] `docs/PORTING.md` row updated

## Weekly rhythm

| Day | What happens |
| --- | --- |
| Saturday | Supervisor meeting. Demo the tagged release. |
| Sunday | Plan the week. Create issues, assign owners, set the milestone. |
| Mon–Wed | Build. Open PRs early as drafts. |
| Thursday | Review each other's PRs. |
| Friday | Merge, tag `v0.x.0-weekN`, write `docs/weekly/week-N.md`. |
