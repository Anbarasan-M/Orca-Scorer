"""Scoring engine: ball-by-ball processing, strike rotation, over completion, and undo."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models import Delivery, Innings, Match, MatchPlayer, Player, Wicket
from app.db.models.enums import InningsStatus, MatchFormat, MatchStatus, ResultType
from app.schemas.delivery import DeliveryCreate, DeliveryRead, ScoringStateResponse
from app.schemas.innings import InningsCreate
from app.schemas.scorecard import CurrentPartnership, PartnershipBatter
from app.services.match import CONSTRAINT_ERROR_MESSAGES, constraint_name


def _delivery_loader_options():
    return (
        joinedload(Delivery.batter),
        joinedload(Delivery.non_striker),
        joinedload(Delivery.bowler),
        selectinload(Delivery.wickets).joinedload(Wicket.player_out),
        selectinload(Delivery.wickets).joinedload(Wicket.fielder),
    )


def get_innings_or_404(db: Session, innings_id: int) -> Innings:
    stmt = (
        select(Innings)
        .options(selectinload(Innings.batting_team), selectinload(Innings.bowling_team))
        .where(Innings.id == innings_id)
    )
    innings = db.scalar(stmt)
    if innings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No innings with id {innings_id}",
        )
    return innings


def create_innings(db: Session, payload: InningsCreate) -> Innings:
    """Start or schedule an innings for a match."""
    match = db.get(Match, payload.match_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No match with id {payload.match_id}",
        )

    # Validate participating teams
    match_teams = {match.team1_id, match.team2_id}
    if payload.batting_team_id not in match_teams:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batting team {payload.batting_team_id} is not part of match {match.id}",
        )
    if payload.bowling_team_id not in match_teams:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bowling team {payload.bowling_team_id} is not part of match {match.id}",
        )

    # In limited overs, default max_overs to match's total_overs if omitted
    max_overs = payload.max_overs
    if max_overs is None and match.total_overs is not None:
        max_overs = match.total_overs

    innings = Innings(
        match_id=payload.match_id,
        innings_number=payload.innings_number,
        batting_team_id=payload.batting_team_id,
        bowling_team_id=payload.bowling_team_id,
        max_overs=max_overs,
        target_runs=payload.target_runs,
        status=InningsStatus.IN_PROGRESS,
    )
    db.add(innings)

    # If match was SCHEDULED, transition to LIVE
    if match.status == MatchStatus.SCHEDULED:
        match.status = MatchStatus.LIVE

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Innings already exists for this match and innings number.",
        ) from exc

    return get_innings_or_404(db, innings.id)


def record_delivery(
    db: Session, innings_id: int, payload: DeliveryCreate
) -> ScoringStateResponse:
    """Record one delivery, compute sequences, handle dismissals & strike rotation."""
    innings = get_innings_or_404(db, innings_id)
    if innings.status in (InningsStatus.COMPLETED, InningsStatus.ABANDONED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot record deliveries for an innings that is {innings.status.value}",
        )

    # Verify players exist in match_players for appropriate sides
    match_players = list(
        db.scalars(
            select(MatchPlayer).where(MatchPlayer.match_id == innings.match_id)
        )
    )
    batting_roster = {mp.player_id for mp in match_players if mp.team_id == innings.batting_team_id}
    fielding_roster = {mp.player_id for mp in match_players if mp.team_id == innings.bowling_team_id}

    if payload.batter_id not in batting_roster:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batter {payload.batter_id} is not in the batting XI",
        )
    if payload.non_striker_id not in batting_roster:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Non-striker {payload.non_striker_id} is not in the batting XI",
        )
    if payload.bowler_id not in fielding_roster:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bowler {payload.bowler_id} is not in the fielding XI",
        )

    # Collect wickets from payload
    wicket_entries = list(payload.wickets or [])
    if payload.wicket is not None:
        wicket_entries.append(payload.wicket)

    for w in wicket_entries:
        if w.fielder_id is not None and w.fielder_id not in fielding_roster:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fielder {w.fielder_id} is not in the fielding XI",
            )

    # Calculate sequences:
    # 1. ball_seq is strictly increasing across the innings
    last_delivery = db.scalar(
        select(Delivery)
        .where(Delivery.innings_id == innings_id)
        .order_by(Delivery.ball_seq.desc())
        .limit(1)
    )
    ball_seq = (last_delivery.ball_seq + 1) if last_delivery else 1

    # 2. Legal balls determine over_number (1-based) and ball_number (1-6)
    legal_balls_so_far = db.scalar(
        select(func.count())
        .select_from(Delivery)
        .where(Delivery.innings_id == innings_id, Delivery.is_legal.is_(True))
    ) or 0

    over_number = (legal_balls_so_far // 6) + 1
    ball_number = (legal_balls_so_far % 6) + 1

    # Insert delivery
    delivery = Delivery(
        innings_id=innings_id,
        ball_seq=ball_seq,
        over_number=over_number,
        ball_number=ball_number,
        batter_id=payload.batter_id,
        non_striker_id=payload.non_striker_id,
        bowler_id=payload.bowler_id,
        runs_off_bat=payload.runs_off_bat,
        wide_runs=payload.wide_runs,
        no_ball_runs=payload.no_ball_runs,
        bye_runs=payload.bye_runs,
        leg_bye_runs=payload.leg_bye_runs,
        penalty_runs=payload.penalty_runs,
        commentary=payload.commentary,
    )
    db.add(delivery)
    db.flush()

    # Insert wickets
    for w in wicket_entries:
        wicket = Wicket(
            delivery_id=delivery.id,
            player_out_id=w.player_out_id,
            wicket_type=w.wicket_type,
            fielder_id=w.fielder_id,
        )
        db.add(wicket)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = constraint_name(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CONSTRAINT_ERROR_MESSAGES.get(name, "Delivery violates a database constraint."),
        ) from exc

    db.expire_all()

    # Re-fetch the saved delivery with loaded relationships
    saved_delivery = db.scalar(
        select(Delivery)
        .options(*_delivery_loader_options())
        .where(Delivery.id == delivery.id)
    )

    # Check legal ball and over progression
    is_legal = saved_delivery.is_legal
    new_legal_balls = legal_balls_so_far + (1 if is_legal else 0)
    is_over_complete = is_legal and (new_legal_balls % 6 == 0)

    # Strike rotation arithmetic
    # Physical runs run by batters:
    runs_run = payload.runs_off_bat + payload.bye_runs + payload.leg_bye_runs
    if payload.wide_runs > 1:
        # Any wide beyond the 1 penalty is running extras taken by batters
        runs_run += (payload.wide_runs - 1)

    striker = payload.batter_id
    non_striker = payload.non_striker_id

    dismissed_ids = {w.player_out_id for w in wicket_entries}

    if runs_run % 2 == 1:
        striker, non_striker = non_striker, striker

    if is_over_complete:
        # At end of over, batters switch ends for the next over
        striker, non_striker = non_striker, striker

    next_striker = None if striker in dismissed_ids else striker
    next_non_striker = None if non_striker in dismissed_ids else non_striker

    # Current totals
    current_score = db.scalar(
        select(func.coalesce(func.sum(Delivery.total_runs), 0)).where(
            Delivery.innings_id == innings_id
        )
    ) or 0

    current_wickets = db.scalar(
        select(func.count())
        .select_from(Wicket)
        .join(Delivery)
        .where(Delivery.innings_id == innings_id)
    ) or 0

    # End of innings checks
    is_innings_complete = False
    max_wickets = max(1, len(batting_roster) - 1) if batting_roster else 10
    all_out = current_wickets >= max_wickets
    overs_exhausted = (
        innings.max_overs is not None and new_legal_balls >= (innings.max_overs * 6)
    )
    target_chased = (
        innings.target_runs is not None and current_score >= innings.target_runs
    )

    if all_out or overs_exhausted or target_chased:
        innings.status = InningsStatus.COMPLETED
        is_innings_complete = True

        # If 2nd innings is complete, determine the match outcome
        if innings.innings_number == 2:
            match = db.get(Match, innings.match_id)
            if match and match.status != MatchStatus.COMPLETED:
                match.status = MatchStatus.COMPLETED
                if innings.target_runs is not None:
                    first_inns_runs = innings.target_runs - 1
                    if current_score >= innings.target_runs:
                        match.winner_team_id = innings.batting_team_id
                        match.result_type = ResultType.WIN
                    elif current_score < first_inns_runs:
                        match.winner_team_id = innings.bowling_team_id
                        match.result_type = ResultType.WIN
                    else:
                        match.winner_team_id = None
                        match.result_type = ResultType.TIE

        db.commit()

    display_overs = f"{new_legal_balls // 6}.{new_legal_balls % 6}"

    partnership = None
    if not all_out:
        partnership = compute_current_partnership(db, innings_id, next_striker, next_non_striker)

    return ScoringStateResponse(
        delivery=DeliveryRead.model_validate(saved_delivery),
        next_striker_id=next_striker,
        next_non_striker_id=next_non_striker,
        is_over_complete=is_over_complete,
        is_innings_complete=is_innings_complete,
        current_score=current_score,
        current_wickets=current_wickets,
        overs_completed_display=display_overs,
        current_partnership=partnership,
    )


def compute_current_partnership(
    db: Session,
    innings_id: int,
    striker_id: int | None = None,
    non_striker_id: int | None = None,
) -> CurrentPartnership | None:
    """Calculate active partnership runs, balls, and batter breakdowns since the last wicket."""
    last_wicket_seq = db.scalar(
        select(func.coalesce(func.max(Delivery.ball_seq), 0))
        .join(Wicket, Wicket.delivery_id == Delivery.id)
        .where(Delivery.innings_id == innings_id)
    ) or 0

    p_runs, p_balls = db.execute(
        select(
            func.coalesce(func.sum(Delivery.total_runs), 0),
            func.count().filter(Delivery.counts_as_ball_faced),
        ).where(
            Delivery.innings_id == innings_id,
            Delivery.ball_seq > last_wicket_seq,
        )
    ).one()

    # If batter IDs not explicitly given, derive from the latest delivery
    if striker_id is None and non_striker_id is None:
        latest_delivery = db.scalar(
            select(Delivery)
            .where(Delivery.innings_id == innings_id)
            .order_by(Delivery.ball_seq.desc())
            .limit(1)
        )
        if latest_delivery is None:
            return None

        if latest_delivery.ball_seq == last_wicket_seq:
            # Wicket fell on the latest delivery: look for surviving batter
            out_ids = set(
                db.scalars(
                    select(Wicket.player_out_id).where(Wicket.delivery_id == latest_delivery.id)
                ).all()
            )
            striker_id = (
                latest_delivery.batter_id
                if latest_delivery.batter_id not in out_ids
                else (latest_delivery.non_striker_id if latest_delivery.non_striker_id not in out_ids else None)
            )
            non_striker_id = None
        else:
            striker_id = latest_delivery.batter_id
            non_striker_id = latest_delivery.non_striker_id

    batter_ids = [b for b in (striker_id, non_striker_id) if b is not None]
    if not batter_ids and p_balls == 0 and p_runs == 0:
        return None

    batter_stats_map: dict[int, tuple[int, int]] = {}
    if batter_ids:
        stats_rows = db.execute(
            select(
                Delivery.batter_id,
                func.coalesce(func.sum(Delivery.runs_off_bat), 0).label("runs"),
                func.count().filter(Delivery.counts_as_ball_faced).label("balls"),
            )
            .where(
                Delivery.innings_id == innings_id,
                Delivery.ball_seq > last_wicket_seq,
                Delivery.batter_id.in_(batter_ids),
            )
            .group_by(Delivery.batter_id)
        ).all()
        for row in stats_rows:
            batter_stats_map[row.batter_id] = (row.runs, row.balls)

    players = db.scalars(select(Player).where(Player.id.in_(batter_ids))).all() if batter_ids else []
    name_map = {p.id: p.name for p in players}

    b1_entry = None
    if striker_id is not None:
        r, b = batter_stats_map.get(striker_id, (0, 0))
        b1_entry = PartnershipBatter(
            player_id=striker_id,
            player_name=name_map.get(striker_id, f"Player {striker_id}"),
            runs=r,
            balls=b,
        )

    b2_entry = None
    if non_striker_id is not None:
        r, b = batter_stats_map.get(non_striker_id, (0, 0))
        b2_entry = PartnershipBatter(
            player_id=non_striker_id,
            player_name=name_map.get(non_striker_id, f"Player {non_striker_id}"),
            runs=r,
            balls=b,
        )

    return CurrentPartnership(
        runs=p_runs,
        balls=p_balls,
        batter1=b1_entry,
        batter2=b2_entry,
    )


def undo_last_delivery(db: Session, innings_id: int) -> DeliveryRead:
    """Delete the last delivery recorded in this innings and cascade its wickets."""
    innings = get_innings_or_404(db, innings_id)

    last_delivery = db.scalar(
        select(Delivery)
        .options(*_delivery_loader_options())
        .where(Delivery.innings_id == innings_id)
        .order_by(Delivery.ball_seq.desc())
        .limit(1)
    )
    if last_delivery is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No deliveries recorded to undo in this innings",
        )

    # Snapshot data before deleting
    undone = DeliveryRead.model_validate(last_delivery)

    db.delete(last_delivery)

    # If innings was marked completed, reopen it
    if innings.status == InningsStatus.COMPLETED:
        innings.status = InningsStatus.IN_PROGRESS
        match = db.get(Match, innings.match_id)
        if match and match.status == MatchStatus.COMPLETED:
            match.status = MatchStatus.LIVE
            match.winner_team_id = None
            match.result_type = None

    db.commit()
    return undone


def start_next_innings(db: Session, match_id: int) -> Innings:
    """Start the next innings of a match based on the completed previous innings."""
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No match with id {match_id}",
        )

    existing_innings = list(
        db.scalars(
            select(Innings)
            .where(Innings.match_id == match_id)
            .order_by(Innings.innings_number.asc())
        )
    )
    if not existing_innings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start next innings: no previous innings exists",
        )

    last_inn = existing_innings[-1]
    if last_inn.status != InningsStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Innings {last_inn.innings_number} is still in progress",
        )

    max_allowed = 2 if match.format != MatchFormat.TEST else 4
    if last_inn.innings_number >= max_allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Match has already reached the maximum {max_allowed} innings for format {match.format.value}",
        )

    next_number = last_inn.innings_number + 1

    # Swap batting and bowling teams
    batting_team_id = last_inn.bowling_team_id
    bowling_team_id = last_inn.batting_team_id

    # Calculate target runs from 1st innings total
    prev_runs = db.scalar(
        select(func.coalesce(func.sum(Delivery.total_runs), 0)).where(
            Delivery.innings_id == last_inn.id
        )
    ) or 0
    target_runs = (prev_runs + 1) if next_number == 2 else None

    next_inn = Innings(
        match_id=match_id,
        innings_number=next_number,
        batting_team_id=batting_team_id,
        bowling_team_id=bowling_team_id,
        max_overs=last_inn.max_overs or match.total_overs,
        target_runs=target_runs,
        status=InningsStatus.IN_PROGRESS,
    )
    db.add(next_inn)
    db.commit()
    return get_innings_or_404(db, next_inn.id)


def list_deliveries(
    db: Session, innings_id: int, limit: int = 200, offset: int = 0
) -> list[Delivery]:
    """List deliveries in chronological order."""
    get_innings_or_404(db, innings_id)
    stmt = (
        select(Delivery)
        .options(*_delivery_loader_options())
        .where(Delivery.innings_id == innings_id)
        .order_by(Delivery.ball_seq.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))
