"""Scoring engine: ball-by-ball processing, strike rotation, over completion, and undo."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models import Delivery, Innings, Match, MatchPlayer, Wicket
from app.db.models.enums import InningsStatus, MatchStatus
from app.schemas.delivery import DeliveryCreate, DeliveryRead, ScoringStateResponse
from app.schemas.innings import InningsCreate
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
        db.commit()
        is_innings_complete = True

    display_overs = f"{new_legal_balls // 6}.{new_legal_balls % 6}"

    return ScoringStateResponse(
        delivery=DeliveryRead.model_validate(saved_delivery),
        next_striker_id=next_striker,
        next_non_striker_id=next_non_striker,
        is_over_complete=is_over_complete,
        is_innings_complete=is_innings_complete,
        current_score=current_score,
        current_wickets=current_wickets,
        overs_completed_display=display_overs,
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

    db.commit()
    return undone


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
