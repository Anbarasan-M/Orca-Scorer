# Orca Scorer

A simple and powerful cricket scoring application.

## Vision

Fast, accurate ball-by-ball scoring with detailed
player/team analytics and AI-powered cricket insights.

## Tech Stack

- Python 3.14 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic
- PostgreSQL 16
- React (not started)
- Docker · Azure · AI (later)

## Documentation

- [docs/project-guide.md](docs/project-guide.md) — what has been built, how the
  pieces fit together, how tables get created, and what comes next
- [AGENTS.md](AGENTS.md) — project conventions and schema decisions
- [backend/README.md](backend/README.md) — backend commands and schema notes

---

## Setting up on a new machine

Three things are deliberately **not** in git and must be recreated: the
virtual environment, the `.env` file, and the database itself. Work through
these in order.

### 1. Clone

```powershell
git clone https://github.com/Anbarasan-M/Orca-Scorer.git
cd Orca-Scorer
```

### 2. Set the git identity — do this before your first commit

Your global git config may belong to a different (work) account. This repo is
personal, so set the identity **locally** on every machine you clone to:

```powershell
git config user.name "Anbarasan Muthu"
git config user.email "anbumuthu0509@gmail.com"

git config user.email          # verify before committing anything
```

`git config` without `--global` writes to `.git/config`, which affects only
this repo and leaves your other repos alone.

### 3. Create the virtual environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The venv must be activated in **every new terminal**. Without it, `python`
is the system interpreter and none of the packages are visible — the most
common cause of `ModuleNotFoundError` here.

### 4. Create the `.env` file

It holds the database password, so it is git-ignored and never transfers.

```powershell
copy .env.example .env
```

Then edit `.env` and set `POSTGRES_PASSWORD` to your local PostgreSQL
password. The other defaults (`localhost`, port `5432`, database
`orca_scorer`) are usually fine.

### 5. Install PostgreSQL and create the database

Install PostgreSQL 16 if the machine does not have it, then:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres orca_scorer
```

Or create a database named `orca_scorer` in pgAdmin.

### 6. Build the schema

```powershell
alembic upgrade head
```

This creates all nine tables. Confirm with:

```powershell
alembic check          # should say "No new upgrade operations detected"
```

### 7. Load demo data (optional)

The database contents do **not** travel with the repo — a fresh clone gives
you empty tables. To get something to look at:

```powershell
python -m scripts.seed_demo
```

That inserts two teams, eight players and one scored over, then prints a
scorecard.

### 8. Run it

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API documentation, and
http://127.0.0.1:8000/health/db to confirm the API reaches PostgreSQL.

---

## Moving between machines

Commit and push before switching:

```powershell
git add -A
git commit -m "..."
git push
```

And on the other side:

```powershell
git pull
```

If `requirements.txt` changed since you last pulled, re-run
`pip install -r requirements.txt`. If a new migration arrived, run
`alembic upgrade head`.

**Your data does not sync.** Each machine has its own PostgreSQL database, so
the teams and matches you enter on one will not appear on the other. Only the
schema travels, via migrations.
