"""Insert a small demo match, then read a scorecard back out of it.

Run with:  python -m scripts.seed_demo

The point is to prove two things:
 1. the constraints accept legal cricket and reject illegal cricket, and
 2. batting/bowling statistics never need to be stored - they are queries.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Delivery,
    Innings,
    Match,
    MatchPlayer,
    Player,
    Team,
    TeamPlayer,
    Wicket,
)
from app.db.models.enums import (
    InningsStatus,
    MatchFormat,
    MatchStatus,
    PlayerRole,
    TossDecision,
    WicketType,
)
from app.db.session import SessionLocal

ORCAS_SQUAD = ["Anbu", "Gokul", "Mohan", "Vishnu"]
WARRIORS_SQUAD = ["Rahul", "Karthik", "Suresh", "Dinesh"]


def build_demo(db) -> Innings:
    orcas = Team(name="Orcas", short_name="ORC")
    warriors = Team(name="Warriors", short_name="WAR")
    db.add_all([orcas, warriors])
    db.flush()

    squads: dict[Team, list[Player]] = {}
    for team, names in ((orcas, ORCAS_SQUAD), (warriors, WARRIORS_SQUAD)):
        players = [Player(name=n, player_role=PlayerRole.ALL_ROUNDER) for n in names]
        db.add_all(players)
        db.flush()
        db.add_all(
            TeamPlayer(team_id=team.id, player_id=p.id) for p in players
        )
        squads[team] = players

    match = Match(
        team1_id=orcas.id,
        team2_id=warriors.id,
        match_date=datetime.now(UTC),
        venue="Chepauk",
        format=MatchFormat.T20,
        total_overs=20,
        toss_winner_id=orcas.id,
        toss_decision=TossDecision.BAT,
        status=MatchStatus.LIVE,
    )
    db.add(match)
    db.flush()

    for team in (orcas, warriors):
        for position, player in enumerate(squads[team], start=1):
            db.add(
                MatchPlayer(
                    match_id=match.id,
                    team_id=team.id,
                    player_id=player.id,
                    batting_position=position,
                    is_captain=(position == 1),
                )
            )

    innings = Innings(
        match_id=match.id,
        innings_number=1,
        batting_team_id=orcas.id,
        bowling_team_id=warriors.id,
        max_overs=20,
        status=InningsStatus.IN_PROGRESS,
    )
    db.add(innings)
    db.flush()

    anbu, gokul, _mohan, _vishnu = squads[orcas]
    rahul, _karthik, _suresh, dinesh = squads[warriors]

    def ball(seq, over, num, striker, non_striker, **kw):
        d = Delivery(
            innings_id=innings.id,
            ball_seq=seq,
            over_number=over,
            ball_number=num,
            batter_id=striker.id,
            non_striker_id=non_striker.id,
            bowler_id=rahul.id,
            **kw,
        )
        db.add(d)
        db.flush()
        return d

    # A first over containing every awkward case at once.
    ball(1, 1, 1, anbu, gokul, runs_off_bat=1)             # single, strike swaps
    ball(2, 1, 2, gokul, anbu, runs_off_bat=4)             # boundary
    ball(3, 1, 3, gokul, anbu, wide_runs=1)                # wide: not a legal ball
    ball(4, 1, 3, gokul, anbu, no_ball_runs=1, runs_off_bat=6)  # no-ball hit for six
    ball(5, 1, 3, gokul, anbu, leg_bye_runs=2)             # 2 leg byes, off the bowler's figures
    out = ball(6, 1, 4, gokul, anbu)                       # caught
    db.add(
        Wicket(
            delivery_id=out.id,
            player_out_id=gokul.id,
            wicket_type=WicketType.CAUGHT,
            fielder_id=dinesh.id,
        )
    )
    ball(7, 1, 5, anbu, gokul, runs_off_bat=0)
    ball(8, 1, 6, anbu, gokul, runs_off_bat=2)

    db.commit()
    return innings


def report(db, innings: Innings) -> None:
    # Deliveries and wickets are aggregated separately. Joining them first and
    # summing would double-count the runs on any ball that took two wickets -
    # the classic join fan-out bug.
    total, legal = db.execute(
        select(
            func.coalesce(func.sum(Delivery.total_runs), 0),
            func.count().filter(Delivery.is_legal),
        ).where(Delivery.innings_id == innings.id)
    ).one()
    wickets = db.scalar(
        select(func.count(Wicket.id))
        .join(Delivery, Delivery.id == Wicket.delivery_id)
        .where(Delivery.innings_id == innings.id)
    )
    print(f"\nScore: {total}/{wickets} after {legal // 6}.{legal % 6} overs")

    print("\nBatting")
    batting = db.execute(
        select(
            Player.name,
            func.sum(Delivery.runs_off_bat).label("runs"),
            func.count().filter(Delivery.counts_as_ball_faced).label("balls"),
            func.count().filter(Delivery.runs_off_bat == 4).label("fours"),
            func.count().filter(Delivery.runs_off_bat == 6).label("sixes"),
        )
        .join(Player, Player.id == Delivery.batter_id)
        .where(Delivery.innings_id == innings.id)
        .group_by(Player.name)
        .order_by(func.sum(Delivery.runs_off_bat).desc())
    ).all()
    for name, runs, balls, fours, sixes in batting:
        sr = runs / balls * 100 if balls else 0
        print(f"  {name:<8} {runs:>3} ({balls})  4s={fours} 6s={sixes}  SR={sr:.1f}")

    print("\nBowling")
    # Wickets come from a correlated subquery for the same fan-out reason.
    wickets_taken = (
        select(func.count(Wicket.id))
        .where(Wicket.delivery_id == Delivery.id, Wicket.is_bowler_credited)
        .scalar_subquery()
    )
    bowling = db.execute(
        select(
            Player.name,
            func.count().filter(Delivery.is_legal).label("legal_balls"),
            func.sum(Delivery.runs_conceded).label("conceded"),
            func.sum(wickets_taken).label("wickets"),
        )
        .join(Player, Player.id == Delivery.bowler_id)
        .where(Delivery.innings_id == innings.id)
        .group_by(Player.name)
    ).all()
    for name, legal_balls, conceded, wkts in bowling:
        overs = f"{legal_balls // 6}.{legal_balls % 6}"
        econ = conceded / (legal_balls / 6) if legal_balls else 0
        print(f"  {name:<8} {overs}-{conceded}-{wkts}  econ={econ:.2f}")


def check_constraints(db, innings: Innings) -> None:
    """Each of these should be rejected by PostgreSQL, not by Python."""
    anbu, gokul, *_ = db.scalars(select(Player).order_by(Player.id)).all()
    illegal = [
        ("runs off the bat on a wide", dict(wide_runs=1, runs_off_bat=4)),
        ("byes and leg byes together", dict(bye_runs=1, leg_bye_runs=1)),
        ("no-ball penalty of 2", dict(no_ball_runs=2)),
    ]
    print("\nConstraint checks")
    for label, kwargs in illegal:
        savepoint = db.begin_nested()
        try:
            db.add(
                Delivery(
                    innings_id=innings.id,
                    ball_seq=900 + len(label),
                    over_number=9,
                    ball_number=1,
                    batter_id=anbu.id,
                    non_striker_id=gokul.id,
                    bowler_id=gokul.id,
                    **kwargs,
                )
            )
            db.flush()
        except IntegrityError as exc:
            name = str(exc.__cause__).split('"')[1] if '"' in str(exc.__cause__) else "?"
            print(f"  rejected: {label:<28} by {name}")
        else:
            print(f"  ACCEPTED (bug!): {label}")
        finally:
            savepoint.rollback()
    db.rollback()


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count(Team.id))):
            print("Database already has teams; skipping seed.")
            innings = db.scalars(select(Innings).order_by(Innings.id)).first()
            if innings is None:
                return
        else:
            innings = build_demo(db)
        report(db, innings)
        check_constraints(db, innings)


if __name__ == "__main__":
    main()
