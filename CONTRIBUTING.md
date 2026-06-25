# Contributing

Thanks for taking a look. This project has a deliberately narrow v1
scope, so before sending a PR for a new feature, it's worth checking
whether it's something already considered and explicitly deferred
rather than overlooked.

## Explicitly out of scope for now, and why

- **Device groups / multi-device schedules.** A schedule targets
  exactly one device today. Group support would touch the data model,
  the API contract, and most of the UI; it's a real feature, not a
  small addition, so it's deferred rather than half-built.
- **Playlists.** WLED supports them natively; this app doesn't expose
  them yet. Same reasoning as groups.
- **mDNS auto-discovery.** Devices are added by IP/hostname only.
  Online/offline status uses a periodic HTTP reachability check
  instead of mDNS, specifically to avoid taking a dependency on
  discovery before it's actually built.
- **Manual, real-time light control from the UI.** This app only ever
  changes a light's state as the result of a schedule firing (or
  "run now," which exists specifically as the one way to verify a
  schedule works without waiting for it). There's no brightness slider
  or color picker for live control. This was a deliberate, revisited
  decision; please open an issue to discuss before submitting a PR
  that adds it.
- **Remote access outside your LAN.** WLED itself has no cloud API,
  and this project intentionally doesn't add one either.

If you want to work on one of these, please open an issue first so
the design can be discussed before code is written, these all have
real implications for the data model.

## Setting up a dev environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

## Running tests

```bash
pytest                  # full suite
pytest -m "not slow"    # skip the one real-time test
pytest tests/test_models.py -v   # a single file, verbose
```

The suite runs against a real SQLite database and a small mock WLED
HTTP server (`tests/mock_wled/`), not mocks of the application's own
code. If you're adding a feature that talks to a device, please add a
test that exercises it against the mock server rather than only
asserting on the parts that don't touch HTTP.

## Database changes

If you change `app/models.py`, generate a migration:

```bash
alembic revision --autogenerate -m "what changed"
```

Then open the generated file and actually read it. Autogenerate is
reliable for new tables and columns; it is **not** reliable for
`CheckConstraint`s added to a column that already exists, those have
gone in empty more than once during this project's own development.
Apply the migration to a real database and inspect the resulting
`CREATE TABLE` SQL directly if you're not sure it did what you expect.

## Code style

```bash
ruff check .
```

No strong opinions beyond what `ruff` already enforces, configured in
`pyproject.toml`.

## Pull requests

Small, focused PRs are easier to review than large ones. If a change
touches the data model, the API contract, and the UI all at once,
consider whether it can be split.
