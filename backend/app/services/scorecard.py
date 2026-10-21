"""Scorecard and statistics aggregation services.

Computes cricket scorecard summaries (batting, bowling, extras, maidens)
while strictly avoiding join fan-out when aggregating deliveries and wickets.
"""

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from app.db.models import Delivery, Innings, Match, Player, Wicket
from app.db.models.enums import InningsStatus, WicketType
from app.schemas.match import MatchRead, TeamSummary
from app.schemas.scorecard import (
    BattingEntry,
    BattingStats,
    BowlingEntry,
    BowlingStats,
    ExtrasBreakdown,
    FieldingStats,
    InningsScorecard,
    MatchScorecard,
    PlayerStatistics,
)
from app.services.match import get_match_or_404
from app.services.scoring import get_innings_or_404


def _format_dismissal(
    wicket_type: WicketType,
    bowler_name: str,
    fielder_name: str | None = None,
) -> str:
    """Format dismissal notation according to cricket convention."""
    if wicket_type == WicketType.BOWLED:
        return f"b {bowler_name}"
    elif wicket_type == WicketType.CAUGHT:
        if fielder_name == bowler_name:
            return f"c & b {bowler_name}"
        return f"c {fielder_name or 'sub'} b {bowler_name}"
    elif wicket_type == WicketType.LBW:
        return f"lbw b {bowler_name}"
    elif wicket_type == WicketType.STUMPED:
        return f"st {fielder_name or 'sub'} b {bowler_name}"
    elif wicket_type == WicketType.RUN_OUT:
        return f"run out ({fielder_name or 'sub'})"
    elif wicket_type == WicketType.HIT_WICKET:
        return f"hit wicket b {bowler_name}"
    elif wicket_type == WicketType.RETIRED_HURT:
        return "retired hurt"
    elif wicket_type == WicketType.RETIRED_OUT:
        return "retired out"
    return f"{wicket_type.value.lower()} b {bowler_name}"


def get_innings_scorecard(db: Session, innings_id: int) -> InningsScorecard:
    """Compute complete batting and bowling scorecard for an innings."""
    innings = get_innings_or_404(db, innings_id)

    # 1. Total runs and legal balls
    total_runs, legal_balls = db.execute(
        select(
            func.coalesce(func.sum(Delivery.total_runs), 0),
            func.count().filter(Delivery.is_legal),
        ).where(Delivery.innings_id == innings_id)
    ).one()

    # 2. Total wickets lost in this innings
    wickets_lost = db.scalar(
        select(func.count(Wicket.id))
        .join(Delivery, Delivery.id == Wicket.delivery_id)
        .where(Delivery.innings_id == innings_id)
    ) or 0

    # 3. Extras breakdown
    byes, leg_byes, wides, no_balls, penalty = db.execute(
        select(
            func.coalesce(func.sum(Delivery.bye_runs), 0),
            func.coalesce(func.sum(Delivery.leg_bye_runs), 0),
            func.coalesce(func.sum(Delivery.wide_runs), 0),
            func.coalesce(func.sum(Delivery.no_ball_runs), 0),
            func.coalesce(func.sum(Delivery.penalty_runs), 0),
        ).where(Delivery.innings_id == innings_id)
    ).one()

    extras = ExtrasBreakdown(
        byes=byes,
        leg_byes=leg_byes,
        wides=wides,
        no_balls=no_balls,
        penalty=penalty,
        total=(byes + leg_byes + wides + no_balls + penalty),
    )

    # 4. Dismissals in this innings
    bowler_alias = aliased(Player, name="bowler_p")
    fielder_alias = aliased(Player, name="fielder_p")
    dismissals_rows = db.execute(
        select(
            Wicket.player_out_id,
            Wicket.wicket_type,
            bowler_alias.name.label("bowler_name"),
            fielder_alias.name.label("fielder_name"),
        )
        .join(Delivery, Delivery.id == Wicket.delivery_id)
        .join(bowler_alias, bowler_alias.id == Delivery.bowler_id)
        .outerjoin(fielder_alias, fielder_alias.id == Wicket.fielder_id)
        .where(Delivery.innings_id == innings_id)
    ).all()

    dismissals_by_player = {
        row.player_out_id: _format_dismissal(
            row.wicket_type, row.bowler_name, row.fielder_name
        )
        for row in dismissals_rows
    }

    # 5. Batting figures
    batting_rows = db.execute(
        select(
            Player.id,
            Player.name,
            func.coalesce(func.sum(Delivery.runs_off_bat), 0).label("runs"),
            func.count().filter(Delivery.counts_as_ball_faced).label("balls"),
            func.count().filter(Delivery.runs_off_bat == 4).label("fours"),
            func.count().filter(Delivery.runs_off_bat == 6).label("sixes"),
            func.min(Delivery.ball_seq).label("first_ball"),
        )
        .join(Player, Player.id == Delivery.batter_id)
        .where(Delivery.innings_id == innings_id)
        .group_by(Player.id, Player.name)
        .order_by(func.min(Delivery.ball_seq))
    ).all()

    batting_entries = []
    seen_batter_ids = set()
    for row in batting_rows:
        seen_batter_ids.add(row.id)
        is_out = row.id in dismissals_by_player
        d_text = dismissals_by_player.get(row.id, "not out")
        sr = round((row.runs / row.balls * 100), 2) if row.balls else 0.0
        batting_entries.append(
            BattingEntry(
                player_id=row.id,
                player_name=row.name,
                runs=row.runs,
                balls_faced=row.balls,
                fours=row.fours,
                sixes=row.sixes,
                strike_rate=sr,
                is_out=is_out,
                dismissal_text=d_text,
            )
        )

    # Any non-striker who got run out without facing a ball
    for player_id, d_text in dismissals_by_player.items():
        if player_id not in seen_batter_ids:
            player_obj = db.get(Player, player_id)
            if player_obj:
                batting_entries.append(
                    BattingEntry(
                        player_id=player_id,
                        player_name=player_obj.name,
                        runs=0,
                        balls_faced=0,
                        fours=0,
                        sixes=0,
                        strike_rate=0.0,
                        is_out=True,
                        dismissal_text=d_text,
                    )
                )

    # 6. Bowling figures
    # Correlated subquery to avoid double counting wickets
    wickets_taken = (
        select(func.count(Wicket.id))
        .where(Wicket.delivery_id == Delivery.id, Wicket.is_bowler_credited)
        .scalar_subquery()
    )

    bowling_rows = db.execute(
        select(
            Player.id,
            Player.name,
            func.count().filter(Delivery.is_legal).label("legal_balls"),
            func.coalesce(func.sum(Delivery.runs_conceded), 0).label("conceded"),
            func.coalesce(func.sum(wickets_taken), 0).label("wickets"),
            func.count().filter(Delivery.runs_conceded == 0).label("dots"),
            func.count().filter(Delivery.wide_runs > 0).label("wides"),
            func.count().filter(Delivery.no_ball_runs > 0).label("no_balls"),
            func.min(Delivery.ball_seq).label("first_ball"),
        )
        .join(Player, Player.id == Delivery.bowler_id)
        .where(Delivery.innings_id == innings_id)
        .group_by(Player.id, Player.name)
        .order_by(func.min(Delivery.ball_seq))
    ).all()

    # Calculate maidens per bowler (completed over of 6 legal balls with 0 runs conceded)
    maidens_query = db.execute(
        select(
            Delivery.bowler_id,
            Delivery.over_number,
            func.count().filter(Delivery.is_legal).label("legal_count"),
            func.sum(Delivery.runs_conceded).label("runs"),
        )
        .where(Delivery.innings_id == innings_id)
        .group_by(Delivery.bowler_id, Delivery.over_number)
    ).all()

    maidens_by_bowler: dict[int, int] = {}
    for m in maidens_query:
        if m.legal_count == 6 and m.runs == 0:
            maidens_by_bowler[m.bowler_id] = maidens_by_bowler.get(m.bowler_id, 0) + 1

    bowling_entries = []
    for row in bowling_rows:
        maidens = maidens_by_bowler.get(row.id, 0)
        overs_str = f"{row.legal_balls // 6}.{row.legal_balls % 6}"
        overs_float = (row.legal_balls // 6) + ((row.legal_balls % 6) / 6)
        econ = round((row.conceded / overs_float), 2) if overs_float > 0 else 0.0
        bowling_entries.append(
            BowlingEntry(
                player_id=row.id,
                player_name=row.name,
                overs=overs_str,
                maidens=maidens,
                runs_conceded=row.conceded,
                wickets=row.wickets,
                economy_rate=econ,
                dots=row.dots,
                wides=row.wides,
                no_balls=row.no_balls,
            )
        )

    overs_display = f"{legal_balls // 6}.{legal_balls % 6}"
    overs_float = (legal_balls // 6) + ((legal_balls % 6) / 6)
    run_rate = round((total_runs / overs_float), 2) if overs_float > 0 else 0.0

    return InningsScorecard(
        innings_id=innings.id,
        innings_number=innings.innings_number,
        status=innings.status,
        batting_team=TeamSummary.model_validate(innings.batting_team),
        bowling_team=TeamSummary.model_validate(innings.bowling_team),
        total_runs=total_runs,
        wickets_lost=wickets_lost,
        overs=overs_display,
        run_rate=run_rate,
        batting=batting_entries,
        bowling=bowling_entries,
        extras=extras,
    )


def get_match_scorecard(db: Session, match_id: int) -> MatchScorecard:
    """Assemble full match scorecard across all innings."""
    match = get_match_or_404(db, match_id)
    innings_list = (
        db.scalars(
            select(Innings)
            .where(Innings.match_id == match_id)
            .order_by(Innings.innings_number)
        )
        .all()
    )

    innings_scorecards = [
        get_innings_scorecard(db, inn.id) for inn in innings_list
    ]

    summary = None
    if match.result_type and match.status == InningsStatus.COMPLETED:
        if match.winner_team:
            summary = f"{match.winner_team.name} won"
        else:
            summary = f"Match ended in a {match.result_type.value.lower()}"

    return MatchScorecard(
        match=MatchRead.model_validate(match),
        innings=innings_scorecards,
        summary_text=summary,
    )


def get_player_statistics(db: Session, player_id: int) -> PlayerStatistics:
    """Compute career totals (batting, bowling, fielding) for a player."""
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No player with id {player_id}",
        )

    # 1. Batting statistics
    # Scores per innings to calculate 50s, 100s, highest score
    per_innings_batting = db.execute(
        select(
            Delivery.innings_id,
            func.sum(Delivery.runs_off_bat).label("runs"),
            func.count().filter(Delivery.counts_as_ball_faced).label("balls"),
            func.count().filter(Delivery.runs_off_bat == 4).label("fours"),
            func.count().filter(Delivery.runs_off_bat == 6).label("sixes"),
        )
        .where(Delivery.batter_id == player_id)
        .group_by(Delivery.innings_id)
    ).all()

    dismissals_count = db.scalar(
        select(func.count(Wicket.id)).where(Wicket.player_out_id == player_id)
    ) or 0

    total_bat_innings = len(per_innings_batting)
    total_runs = sum(row.runs for row in per_innings_batting)
    total_balls = sum(row.balls for row in per_innings_batting)
    total_fours = sum(row.fours for row in per_innings_batting)
    total_sixes = sum(row.sixes for row in per_innings_batting)
    highest_score = max((row.runs for row in per_innings_batting), default=0)
    fifties = sum(1 for row in per_innings_batting if 50 <= row.runs < 100)
    hundreds = sum(1 for row in per_innings_batting if row.runs >= 100)
    not_outs = max(0, total_bat_innings - dismissals_count)

    bat_avg = (
        round(total_runs / dismissals_count, 2)
        if dismissals_count > 0
        else (float(total_runs) if total_bat_innings > 0 else None)
    )
    sr = round((total_runs / total_balls * 100), 2) if total_balls > 0 else 0.0

    batting_stats = BattingStats(
        innings=total_bat_innings,
        runs=total_runs,
        balls_faced=total_balls,
        highest_score=highest_score,
        average=bat_avg,
        strike_rate=sr,
        fours=total_fours,
        sixes=total_sixes,
        not_outs=not_outs,
        fifties=fifties,
        hundreds=hundreds,
    )

    # 2. Bowling statistics
    wickets_subquery = (
        select(func.count(Wicket.id))
        .where(Wicket.delivery_id == Delivery.id, Wicket.is_bowler_credited)
        .scalar_subquery()
    )

    per_innings_bowling = db.execute(
        select(
            Delivery.innings_id,
            func.count().filter(Delivery.is_legal).label("legal_balls"),
            func.coalesce(func.sum(Delivery.runs_conceded), 0).label("conceded"),
            func.coalesce(func.sum(wickets_subquery), 0).label("wickets"),
        )
        .where(Delivery.bowler_id == player_id)
        .group_by(Delivery.innings_id)
    ).all()

    total_bowl_innings = len(per_innings_bowling)
    total_legal_balls = sum(row.legal_balls for row in per_innings_bowling)
    total_conceded = sum(row.conceded for row in per_innings_bowling)
    total_wickets = sum(row.wickets for row in per_innings_bowling)

    bowl_avg = round(total_conceded / total_wickets, 2) if total_wickets > 0 else None
    bowl_overs_float = (total_legal_balls // 6) + ((total_legal_balls % 6) / 6)
    bowl_econ = (
        round(total_conceded / bowl_overs_float, 2) if bowl_overs_float > 0 else 0.0
    )
    bowl_sr = (
        round(total_legal_balls / total_wickets, 2) if total_wickets > 0 else None
    )

    # Find best bowling performance (most wickets, then fewest runs conceded)
    best_bowling_row = sorted(
        per_innings_bowling, key=lambda r: (-r.wickets, r.conceded)
    )
    best_bowling_str = (
        f"{best_bowling_row[0].wickets}/{best_bowling_row[0].conceded}"
        if best_bowling_row and best_bowling_row[0].wickets > 0
        else None
    )

    # Maidens across all matches
    maidens_count = db.execute(
        select(
            Delivery.innings_id,
            Delivery.over_number,
            func.count().filter(Delivery.is_legal).label("legal_count"),
            func.sum(Delivery.runs_conceded).label("runs"),
        )
        .where(Delivery.bowler_id == player_id)
        .group_by(Delivery.innings_id, Delivery.over_number)
    ).all()
    total_maidens = sum(1 for m in maidens_count if m.legal_count == 6 and m.runs == 0)

    bowling_stats = BowlingStats(
        innings=total_bowl_innings,
        overs=f"{total_legal_balls // 6}.{total_legal_balls % 6}",
        maidens=total_maidens,
        runs_conceded=total_conceded,
        wickets=total_wickets,
        average=bowl_avg,
        economy=bowl_econ,
        strike_rate=bowl_sr,
        best_bowling=best_bowling_str,
    )

    # 3. Fielding statistics
    catches = db.scalar(
        select(func.count(Wicket.id)).where(
            Wicket.fielder_id == player_id, Wicket.wicket_type == WicketType.CAUGHT
        )
    ) or 0
    stumpings = db.scalar(
        select(func.count(Wicket.id)).where(
            Wicket.fielder_id == player_id, Wicket.wicket_type == WicketType.STUMPED
        )
    ) or 0
    run_outs = db.scalar(
        select(func.count(Wicket.id)).where(
            Wicket.fielder_id == player_id, Wicket.wicket_type == WicketType.RUN_OUT
        )
    ) or 0

    fielding_stats = FieldingStats(
        catches=catches,
        stumpings=stumpings,
        run_outs=run_outs,
    )

    return PlayerStatistics(
        player_id=player.id,
        player_name=player.name,
        batting=batting_stats,
        bowling=bowling_stats,
        fielding=fielding_stats,
    )
