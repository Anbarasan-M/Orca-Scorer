# Orca Scorer — backend

FastAPI + SQLAlchemy 2 + Alembic on PostgreSQL 16.

## Layout

```
backend/
  app/
    core/config.py      settings from .env (pydantic-settings)
    db/base.py          declarative Base, naming convention, id/timestamp mixins
    db/session.py       engine + SessionLocal + get_db() dependency
    db/types.py         enum_col(): StrEnum -> VARCHAR + CHECK
    db/models/          the nine tables, one file each
    main.py             FastAPI app
  alembic/
    env.py              reads the URL from app.core.config, not alembic.ini
    versions/           migrations
  scripts/seed_demo.py  inserts a demo over and prints a scorecard
```

## One-time setup

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1. Fill in your PostgreSQL password
copy .env.example .env      # then edit POSTGRES_PASSWORD

# 2. Create the database
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres orca_scorer

# 3. Build the schema
alembic upgrade head
```

## Everyday commands

| What | Command |
| --- | --- |
| Run the API | `uvicorn app.main:app --reload` |
| Check the DB connection | open http://127.0.0.1:8000/health/db |
| Apply migrations | `alembic upgrade head` |
| See the SQL without running it | `alembic upgrade head --sql` |
| New migration from model changes | `alembic revision --autogenerate -m "add x"` |
| Confirm models match the DB | `alembic check` |
| Roll back one migration | `alembic downgrade -1` |
| Load demo data | `python -m scripts.seed_demo` |

`alembic revision --autogenerate` writes a *draft*. Always read it before
running it — it cannot see triggers, and it guesses badly at renames.

## Schema notes

**Nothing derivable is stored.** There is no `total_runs` on a player row.
Runs, balls faced, strike rate, economy and wickets are all queries over
`deliveries` — see `scripts/seed_demo.py` for the exact SQL.

**Extras are counters, not a type.** `wide_runs`, `no_ball_runs`, `bye_runs`,
`leg_bye_runs` and `penalty_runs` each hold the runs attributed to that
category, because a single ball can be a no-ball hit for six. A column like
`extra_type = 'NO_BALL'` cannot express that.

**Derived columns are computed by PostgreSQL**, so they cannot drift:

| Column | Definition |
| --- | --- |
| `deliveries.is_legal` | no wide and no no-ball → counts towards the over |
| `deliveries.total_runs` | every run the ball gave the batting side |
| `deliveries.runs_conceded` | runs charged to the bowler (byes excluded) |
| `deliveries.counts_as_ball_faced` | false only for wides |
| `wickets.is_bowler_credited` | false for run outs and retirements |
| `team_players.is_active` | `left_at IS NULL` |

**Ordering deliveries.** `(over_number, ball_number)` is *not* unique — a wide
repeats the same pair. `ball_seq` is the ordering key, unique per innings.

**Over notation.** `over_number` is 1-based. Cricket's "4.3" means 4 completed
overs plus 3 balls, so the UI renders `over_number - 1` before the dot.

### Invariants enforced in the application, not the database

These need to look at two tables at once, which a CHECK constraint cannot do.
They belong in the service layer:

- a `match_players.team_id` must be one of the match's two teams
- an `innings` batting/bowling team must be one of the match's two teams
- a delivery's batter, non-striker and bowler must be in `match_players`
- the bowler must be on the fielding side
- `ball_seq` must be contiguous within an innings
