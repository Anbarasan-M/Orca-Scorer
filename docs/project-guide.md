# Orca Scorer — project guide

Written for the project owner: what has been built, how the pieces fit
together, how Python projects are laid out in general, and what comes next.

Assumes Laravel/PHP background. Comparisons to Laravel appear throughout.

---

## 1. The four libraries

Laravel is one framework that does everything. Python composes separate
libraries, which is why there are several names to keep straight.

| Library | Job | Laravel equivalent |
|---|---|---|
| **FastAPI** | HTTP — routing, status codes, request/response, auto docs | routing + controllers |
| **SQLAlchemy** | ORM — models and queries | Eloquent |
| **Alembic** | migrations | `php artisan migrate` |
| **Pydantic** | validating and shaping JSON | FormRequest + API Resource |

Rule of thumb when reading a file:

- anything about **HTTP** is FastAPI
- anything about the **database** is SQLAlchemy
- anything about **JSON in/out** is Pydantic

They meet in one place — a route function:

```python
@router.post("", response_model=PlayerRead, status_code=201)   # FastAPI
def create_player(
    payload: PlayerCreate,                                     # Pydantic
    db: Session = Depends(get_db),                             # FastAPI + SQLAlchemy
) -> Player:
    player = Player(**payload.model_dump())                    # SQLAlchemy + Pydantic
    db.add(player)                                             # SQLAlchemy
    db.commit()                                                # SQLAlchemy
    db.refresh(player)                                         # SQLAlchemy
    return player                                              # FastAPI serialises it
```

---

## 2. How tables are actually created

**Not by Pydantic.** Pydantic never touches the database. The chain is:

```
1.  app/db/models/player.py          you declare the columns  (SQLAlchemy)
             │
             │   alembic revision --autogenerate -m "add players"
             ▼
2.  alembic/versions/0001_*.py       a migration script is generated
             │
             │   alembic upgrade head
             ▼
3.  Alembic emits real SQL
             ▼
4.  PostgreSQL                       CREATE TABLE players (...)
```

### Step 1 — the model

`app/db/models/player.py` declares every column explicitly:

```python
class Player(Base, IdMixin, TimestampMixin):
    __tablename__ = "players"
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False, index=True)
```

`Mapped[str]` is the Python type. `mapped_column(...)` is the SQL detail.
Inheriting `Base` registers the class on `Base.metadata`, which is the
in-memory catalogue of every table.

> **Difference from Laravel.** In Laravel the *migration* defines the schema
> and the Eloquent model is thin, inferring columns from the database. Here
> it is the other way round: the **model is the source of truth**, and
> migrations are generated from it. That is why `delivery.py` is 138 lines
> where an Eloquent model would be nearly empty.

### Step 2 — generating the migration

```powershell
alembic revision --autogenerate -m "add players"
```

Alembic connects to the live database, reads the actual tables, compares them
against `Base.metadata`, and writes a migration containing the difference.
Laravel has no built-in equivalent — there you write migrations by hand.

The output is a **draft**. Always read it before running it: it cannot see
triggers, and it guesses badly at column renames (it will usually emit a drop
plus an add, which loses data).

### Step 3 — applying it

```powershell
alembic upgrade head
```

"Run every migration not yet applied, up to the newest." Alembic records the
current revision in an `alembic_version` table — one row, holding `0001`.
That is how it knows what has already run.

To see the SQL without executing it:

```powershell
alembic upgrade head --sql
```

### Where Pydantic sits instead

```
HTTP request  →  Pydantic schema  →  route function  →  SQLAlchemy model  →  PostgreSQL
                 (app/schemas/)                          (app/db/models/)
```

Pydantic guards the boundary between the outside world and the application.
SQLAlchemy guards the boundary between the application and the database. They
never overlap.

---

## 3. What has been built

### Database — 9 tables, revision `0001`

`teams`, `players`, `team_players`, `matches`, `match_players`, `innings`,
`deliveries`, `wickets`, `match_events`.

Current contents: 2 teams, 8 players, 8 squad rows, 1 match, 8 deliveries,
1 wicket — demo data from `scripts/seed_demo.py`.

Four design decisions worth being able to explain in an interview:

**No statistics are stored.** There is no `total_runs` column on a player.
Runs, balls faced, strike rate, economy and wickets are all *queries* over
`deliveries`. Storing them would mean two sources of truth that can disagree.

**No `overs` table.** An over is not an independent entity — it can contain 7
or 8 deliveries because wides and no-balls are not legal balls.
`(innings_id, over_number, ball_number)` expresses it without a table.

**Extras are per-category counters.** `wide_runs`, `no_ball_runs`, `bye_runs`,
`leg_bye_runs`, `penalty_runs`. A single `extra_type = 'NO_BALL'` column could
not represent a no-ball that was hit for six.

**Derived values are computed by PostgreSQL**, using `GENERATED ALWAYS ...
STORED` columns, so they cannot drift from their inputs:

| Column | Meaning |
|---|---|
| `deliveries.is_legal` | no wide, no no-ball — counts toward the over |
| `deliveries.total_runs` | every run the ball gave the batting side |
| `deliveries.runs_conceded` | runs charged to the bowler — excludes byes/leg byes |
| `deliveries.counts_as_ball_faced` | false only for wides |
| `wickets.is_bowler_credited` | false for run outs and retirements |
| `team_players.is_active` | `left_at IS NULL` |

The Laws of cricket are enforced as `CHECK` constraints: no runs off the bat
on a wide, byes and leg byes mutually exclusive, a no-ball penalty of exactly
1, a named fielder required for caught/stumped/run out.

### API — 13 endpoints

```
GET    /                                  banner
GET    /health/db                         proves the API reaches PostgreSQL

POST   /teams                             201; 409 on duplicate name/short_name
GET    /teams                             paginated; ?search= ?limit= ?offset=
GET    /teams/{id}                        404 if absent
PATCH  /teams/{id}                        partial update
DELETE /teams/{id}                        204; 409 if the team has played
GET    /teams/{id}/squad                  active squad
POST   /teams/{id}/squad                  201; 409 if already in squad
DELETE /teams/{id}/squad/{player_id}      204; sets left_at, keeps the row

POST   /players                           201
GET    /players                           paginated; ?search= ?role=
GET    /players/{id}                      404 if absent
PATCH  /players/{id}                      partial update
DELETE /players/{id}                      204; 409 if they have played
```

All verified against a running server, not assumed.

### The squad-removal decision

`DELETE /teams/{id}/squad/{player_id}` does **not** delete the row. It sets
`left_at` to today. Consequences:

- the generated `is_active` column flips to `false` by itself
- `GET /teams/{id}/squad` filters on `is_active`, so the player disappears
  with no change to that endpoint
- "who played for us in 2026?" remains answerable
- the player can rejoin later: `uq_team_players_active` is a *partial* unique
  index that forbids two simultaneously open stints, not two stints ever

### Git history

```
bca0b91  Merge pull request #2
5b3804b  Add players API and squad membership endpoints
32be23d  Add AGENTS.md project context document
4e0b978  Add teams CRUD endpoints
1116336  Merge pull request #1
581eb0a  Add PostgreSQL schema for the core scoring engine
5bfb348  First api
92c35d9  Initial commit
```

History was rewritten once to remove a work identity that had been committing
to this personal repo. The repo now has a local git identity
(`git config user.email`), and `~/.gitconfig` has `includeIf` rules so
personal folders select it automatically.

---

## 4. How Python projects are structured

### There is no `artisan`

Laravel scaffolds for you and enforces a layout. Python has **conventions,
not rules**. Nothing generates a controller; nothing requires a particular
folder. The layout below is the common FastAPI convention, not a mandate.

### Virtual environments

Laravel puts dependencies in `vendor/`, per project. Python's equivalent is a
**virtual environment** — a private copy of the interpreter plus its packages:

```powershell
python -m venv .venv          # create           (once)
.\.venv\Scripts\Activate.ps1  # switch into it   (every terminal)
pip install -r requirements.txt
```

| Laravel | Python |
|---|---|
| `composer.json` | `requirements.txt` (or `pyproject.toml`) |
| `composer install` | `pip install -r requirements.txt` |
| `vendor/` | `.venv/` |

Both are git-ignored. Without activating the venv, `python` is the system
interpreter and your packages are missing — the most common beginner error.

### Packages and `__init__.py`

A folder becomes an importable **package**. You will see empty `__init__.py`
files in `app/`, `app/core/`, `app/db/` — historically required to mark a
folder as a package. Modern Python does not strictly need them, but they are
kept because tooling behaves more predictably with them.

`app/db/models/__init__.py` is *not* empty — it re-exports every model:

```python
from app.db.models.player import Player
```

so other code writes `from app.db.models import Player` instead of the full
path, and so Alembic sees every model registered when it autogenerates.

### The common FastAPI layout

```
backend/
  app/
    main.py            the FastAPI app object; includes the routers
    core/
      config.py        settings from .env
    db/
      base.py          declarative Base + shared column mixins
      session.py       engine, SessionLocal, get_db()
      models/          one file per table
    schemas/           Pydantic request/response models
    api/
      routes/          one file per resource
  alembic/
    env.py
    versions/          migration scripts
  scripts/             one-off scripts (seeding, imports)
  tests/               pytest tests
  requirements.txt
  .env                 never committed
  .env.example         committed template
```

The organising principle is **one layer per folder**:

| Folder | Answers |
|---|---|
| `db/models/` | what does the data look like in the database? |
| `schemas/` | what does it look like as JSON? |
| `api/routes/` | what happens on each HTTP request? |
| `core/` | how is the app configured? |

### Two conventions you will meet elsewhere

**`src/` layout** — some projects put everything under `src/`. It prevents
accidentally importing from the working directory instead of the installed
package. Not needed here.

**`pyproject.toml`** — the modern replacement for `requirements.txt`,
declaring dependencies, build settings and tool config in one file. Worth
knowing the name; `requirements.txt` is fine for this project.

### Naming conventions

| Thing | Style | Example |
|---|---|---|
| files, folders | `snake_case` | `team_player.py` |
| classes | `PascalCase` | `TeamPlayer` |
| functions, variables | `snake_case` | `get_player_or_404` |
| constants | `UPPER_SNAKE` | `CONFLICT_MESSAGES` |
| "internal" | leading underscore | `_check_name` |

PHP uses `PascalCase` files and `camelCase` methods; Python does not. The
leading underscore is a *convention* meaning "not part of the public API" —
unlike PHP's `private`, nothing enforces it.

---

## 5. What comes next

### Step 2 — Matches API

Create a match, record the toss, name the XI in `match_players`.

This is the first place the database **cannot protect you**. A `CHECK`
constraint sees only one row in one table, so nothing stops you putting a
Warriors player in the Orcas' XI. These invariants must live in code:

- `match_players.team_id` must be one of the match's two teams
- an innings' batting/bowling team must be one of the match's two teams
- a delivery's batter, non-striker and bowler must be in `match_players`
- the bowler must be on the fielding side

Endpoints:

```
POST   /matches                     create (teams, date, format, overs)
GET    /matches                     paginated; ?status= ?team_id=
GET    /matches/{id}                with teams expanded
PATCH  /matches/{id}                record the toss, set status
POST   /matches/{id}/players        name the XI
GET    /matches/{id}/players        both XIs
```

Likely worth introducing a `app/services/` layer here, so validation that
spans tables is not buried in route functions.

### Step 3 — Scoring endpoint

`POST /innings/{id}/deliveries` — the heart of the application.

Each request must: work out the next `ball_seq`; work out `over_number` and
`ball_number` from the legal balls so far; decide whether the strike rotates
(odd runs, or end of over); record a wicket if there was one; detect the end
of the over and the end of the innings.

Also needs an undo path — `DELETE` the last delivery, with wickets cascading.
A scorer mis-taps constantly; undo is not optional.

This is the most interesting code in the project and the best interview
material, because the rules are genuinely intricate and the schema was
designed to hold them.

### Step 4 — Scorecard endpoints

Turn the aggregate queries in `scripts/seed_demo.py` into real responses:

```
GET /innings/{id}/scorecard        batting + bowling figures
GET /matches/{id}/scorecard        both innings
GET /players/{id}/statistics       career totals
```

Watch for **join fan-out**: aggregating `deliveries` joined to `wickets`
double-counts runs on any ball with two dismissals. `seed_demo.py` avoids it
with separate queries and a correlated subquery.

### Step 5 — Tests

There are none. The usual approach is pytest with a fixture that opens a
transaction per test and rolls it back afterwards, so tests never leave data
behind.

| Laravel | Python |
|---|---|
| PHPUnit | pytest |
| `RefreshDatabase` | a transactional fixture |
| `$this->postJson(...)` | `TestClient(app).post(...)` |

### Step 6 — React frontend

`frontend/` is empty. Scoring screen first: it is the only screen that has to
be fast and correct, and the rest of the app is CRUD around it.

### Deliberately deferred

Authentication and `users`; venues; tournaments and seasons; partnerships;
live scoring over WebSockets; AI analysis. Each is real work, and none is
needed to prove the scoring engine.

---

## 6. Command reference

All from `backend/` with the venv activated.

| Task | Command |
|---|---|
| Activate the venv | `.\.venv\Scripts\Activate.ps1` |
| Install dependencies | `pip install -r requirements.txt` |
| Run the API | `uvicorn app.main:app --reload` |
| Interactive docs | http://127.0.0.1:8000/docs |
| Apply migrations | `alembic upgrade head` |
| Preview SQL only | `alembic upgrade head --sql` |
| New migration | `alembic revision --autogenerate -m "..."` |
| Check models match the DB | `alembic check` |
| Roll back one | `alembic downgrade -1` |
| Load demo data | `python -m scripts.seed_demo` |
