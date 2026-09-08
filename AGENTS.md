# Orca Scorer — project context

Ball-by-ball cricket scoring app. Read this before changing anything.

## What this project is for

A learning project. The owner is preparing for interviews and is **new to Python
and React** — they have prior web experience with PHP/MySQL via XAMPP but had
never connected PostgreSQL to an application before this.

This changes how work should be delivered:

- **Explain, don't just produce.** Small steps with the reasoning shown beat
  large correct diffs dropped in silently.
- **Verify claims.** Run the thing and show real output. Where numbers are
  involved (cricket statistics especially), check them against manual
  arithmetic rather than asserting they are right.
- **Prefer teaching the idiom** over clever code. If two approaches work, pick
  the one a reader learns more from.

## Hard conventions

1. **No AI or employer attribution in commits or PRs.** No `Co-Authored-By`
   trailers, no "Generated with …" lines, no assistant links. Git history was
   rewritten once already to strip these; do not reintroduce them.
2. **Git identity is `Anbarasan Muthu <anbumuthu0509@gmail.com>`**, set
   repo-locally. The machine's global `~/.gitconfig` holds a separate employer
   identity that must never appear in this repo — this is entirely the owner's
   personal work. `~/.gitconfig` has `includeIf` rules covering
   `D:/Orca-Scorer/` and `D:/personal/` that select the personal identity
   automatically. Verify with `git config user.email` before committing.
3. **Never commit `.env`.** It holds the local PostgreSQL password.
   `.env.example` is the tracked template.
4. **Nothing derivable is stored.** See "Schema philosophy" below. This is the
   single most important design rule in the project.

## Stack

| | Version |
|---|---|
| Python | 3.14.3 |
| PostgreSQL | 16.14 (Windows service `postgresql-x64-16`) |
| FastAPI | 0.141.1 |
| SQLAlchemy | 2.0.52 (2.x style: `Mapped` / `mapped_column`) |
| Alembic | 1.19.1 |
| psycopg | 3.3.5 — driver URL is `postgresql+psycopg://`, **not** psycopg2 |
| Node | 24.14.0 (frontend not started) |

Platform is Windows 11. The venv lives at `backend/.venv`.

## Running it

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```

| Task | Command (from `backend/`) |
|---|---|
| Apply migrations | `alembic upgrade head` |
| Preview SQL without running | `alembic upgrade head --sql` |
| New migration from model changes | `alembic revision --autogenerate -m "..."` |
| Confirm models match the DB | `alembic check` |
| Roll back one | `alembic downgrade -1` |
| Demo data + scorecard | `python -m scripts.seed_demo` |

## Layout

```
backend/
  app/
    core/config.py       pydantic-settings; reads .env; exposes `settings`
    db/base.py           DeclarativeBase, naming convention, IdMixin, TimestampMixin
    db/session.py        engine, SessionLocal, get_db() FastAPI dependency
    db/types.py          enum_col(): StrEnum -> VARCHAR + CHECK
    db/models/           nine tables, one file each, all re-exported in __init__
    schemas/             Pydantic request/response models
    api/routes/          APIRouter per resource, collected in __init__.api_router
    main.py              FastAPI app; includes api_router
  alembic/
    env.py               reads DB URL from app.core.config, NOT alembic.ini
    versions/0001_initial_schema.py
  scripts/seed_demo.py   inserts a demo over, prints a scorecard, tests constraints
frontend/                empty - not started
```

## Schema philosophy

Nine tables: `teams`, `players`, `team_players`, `matches`, `match_players`,
`innings`, `deliveries`, `wickets`, `match_events`.

**No statistics are stored anywhere.** There is no `total_runs` on a player row
and there must not be. Runs, balls faced, strike rate, economy, wickets and
averages are all *queries* over `deliveries`. `scripts/seed_demo.py` has
working examples of each. Do not add caching or summary tables without a
measured reason.

**No `overs` table.** An over is not an independent entity — it can contain 7,
8 or more deliveries because wides and no-balls are not legal balls.
`(innings_id, over_number, ball_number)` expresses it naturally.

**Extras are per-category counters, not a type.** `wide_runs`, `no_ball_runs`,
`bye_runs`, `leg_bye_runs`, `penalty_runs` each hold the runs attributed to
that category. A single column like `extra_type = 'NO_BALL'` cannot express a
no-ball that was hit for six, which is why it was rejected.

**Derived columns are `GENERATED ALWAYS … STORED` in PostgreSQL**, so they can
never drift from their inputs:

| Column | Meaning |
|---|---|
| `deliveries.is_legal` | no wide and no no-ball — counts toward the over |
| `deliveries.total_runs` | every run this ball gave the batting side |
| `deliveries.runs_conceded` | runs charged to the bowler — **excludes byes and leg byes** |
| `deliveries.counts_as_ball_faced` | false only for wides |
| `wickets.is_bowler_credited` | false for run outs and retirements |
| `team_players.is_active` | `left_at IS NULL` |

Never write to these from Python. Alembic will warn that a computed default
"cannot be modified" — that warning is expected and harmless.

**Ordering deliveries.** `(over_number, ball_number)` is **not unique** — a
wide repeats the same pair. `deliveries.ball_seq` is the ordering key, unique
per innings. Any code that walks an innings in order must use `ball_seq`.

**Over notation.** `over_number` is **1-based** (first over of an innings is 1).
Cricket's display form "4.3" means 4 completed overs plus 3 balls, so the UI
renders `over_number - 1` before the dot.

**Enums are VARCHAR + CHECK**, not native PostgreSQL `ENUM` types, so changing
the allowed values is a one-line migration instead of a type rebuild. Defined
as `StrEnum` in `app/db/models/enums.py` and wrapped by
`app/db/types.py::enum_col`.

## Laws of cricket enforced as CHECK constraints

On `deliveries`:

- no runs off the bat, and no byes, on a wide (everything goes down as wides)
- byes and leg byes are mutually exclusive on one ball
- `no_ball_runs IN (0, 1)` — the penalty is exactly 1; runs off a no-ball go to
  `runs_off_bat` or `bye_runs`
- runs off the bat exclude byes and leg byes
- `batter_id <> non_striker_id`

On `wickets`: a fielder is required for `CAUGHT`/`STUMPED`/`RUN_OUT` and
forbidden otherwise; the fielder cannot be the dismissed batter.

On `matches`: the two teams differ; the toss winner and match winner must be
one of the two; the toss is recorded whole or not at all; `result_type = 'WIN'`
iff `winner_team_id IS NOT NULL`.

## Invariants NOT enforced by the database

A CHECK constraint cannot see two tables, so these belong in the service layer
and are currently **unenforced**:

- `match_players.team_id` must be one of the match's two teams
- an innings' batting/bowling team must be one of the match's two teams
- a delivery's batter, non-striker and bowler must be in `match_players`
- the bowler must be on the fielding side
- `ball_seq` must be contiguous within an innings

Implementing these is legitimate future work.

## Gotcha: Alembic and enum CHECK constraints

`sa.Enum(native_enum=False, create_constraint=True)` generates a
`CHECK (col IN (...))` that Alembic classes as *type-bound* and skips when
reading models — but still reflects out of PostgreSQL. Without a filter,
every `--autogenerate` emits spurious `DROP CONSTRAINT` lines that would
silently delete enum validation.

`alembic/env.py` has an `include_object` filter that suppresses these. It
derives the names from the models, so new enums are covered automatically.
**Do not remove it**, and if `alembic check` starts reporting removed check
constraints, that filter is the first place to look.

## Current state

Database is migrated to revision `0001` and holds demo data:

```
teams 2 · players 8 · team_players 8 · matches 1
match_players 8 · innings 1 · deliveries 8 · wickets 1 · match_events 0
```

Endpoints implemented:

```
GET    /                       banner
GET    /health/db              proves the API reaches PostgreSQL
POST   /teams                  201; 409 on duplicate name/short_name
GET    /teams                  paginated, ?search= ?limit= ?offset=
GET    /teams/{id}             404 if absent
PATCH  /teams/{id}             partial; exclude_unset
DELETE /teams/{id}             204; 409 if the team has played a match
GET    /teams/{id}/squad       active squad, joins team_players
```

All verified against a running server: short_name normalisation
(`"orc"` → `"ORC"`), duplicate → 409, blank name → 422, partial PATCH firing
the `updated_at` trigger, missing id → 404, and both DELETE outcomes.

`scripts/seed_demo.py` scores an over containing a wide, a no-ball hit for six,
leg byes and a catch. Hand-checked: team 17, bowler conceded 15 (the 2 leg byes
correctly excluded), 6 legal balls, striker faced 4 (wide excluded, no-ball
included).

### API layer patterns to copy

`app/api/routes/teams.py` is the reference implementation. New resources should
match it:

- schemas split into `XBase` / `XCreate` / `XUpdate` / `XRead`; `XRead` sets
  `model_config = ConfigDict(from_attributes=True)`
- `XCreate` omits `id` and timestamps so clients cannot set them
- normalise in Pydantic validators where the DB has a CHECK (e.g. upper-casing)
  so the API accepts friendly input instead of 500ing at the database
- catch `IntegrityError`, read the violated constraint via
  `exc.orig.diag.constraint_name`, map it to a readable 409
- `get_X_or_404` helper for the lookup
- `db.refresh(obj)` after commit to load server-generated columns
- list endpoints are always paginated
- register the router with one line in `app/api/routes/__init__.py`

### Git state

Local `main` is `1116336`; `feat/teams-api` is `4e0b978`. **Neither is pushed
yet** — `origin/main` is still the pre-rewrite `ea90e53`. The pending commands
are:

```powershell
git push --force origin main
git push -u origin feat/teams-api
git reflog expire --expire=now --all
git gc --prune=now
```

## Roadmap

1. **Players API** — CRUD plus add/remove a player from a team's squad. First
   endpoint that writes to a join table (`team_players`), including closing a
   stint by setting `left_at` rather than deleting the row.
2. **Matches API** — create a match, record the toss, name the XI in
   `match_players`. Where the cross-table invariants above start to matter.
3. **Scoring endpoint** — `POST /innings/{id}/deliveries`. The heart of the
   app: assigning `ball_seq`, strike rotation, over completion, wickets.
   Needs an undo path (`DELETE` the last delivery; wickets cascade).
4. **Scorecard endpoints** — turn the aggregate queries in `seed_demo.py` into
   real responses. Watch for join fan-out: aggregating `deliveries` joined to
   `wickets` double-counts runs on a ball with two dismissals, so
   `seed_demo.py` uses separate queries and a correlated subquery.
5. **Tests** — there are none yet. pytest + a transactional fixture that rolls
   back per test.
6. **React frontend** — not started; `frontend/` is empty.

Deliberately deferred: authentication and `users`, venues, tournaments and
seasons, partnerships, live scoring over WebSockets, AI analysis.
