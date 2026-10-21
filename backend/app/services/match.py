"""Business logic and cross-table validation for matches."""

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models import Match, MatchPlayer, Team, TeamPlayer
from app.db.models.enums import MatchStatus
from app.schemas.match import MatchCreate, MatchSquadCreate, MatchUpdate

# Map DB constraint names to readable client error messages
CONSTRAINT_ERROR_MESSAGES = {
    "distinct_teams": "A match cannot be played between the same team.",
    "toss_winner_is_playing": "The toss winner must be one of the two competing teams.",
    "winner_is_playing": "The match winner must be one of the two competing teams.",
    "toss_complete": "Toss winner and toss decision must be recorded together.",
    "winner_matches_result": "A winner can only be specified when result_type is WIN.",
    "overs_range": "Total overs must be between 1 and 200.",
    "uq_match_players_batting_position": "Two players cannot have the same batting position for a team.",
    "uq_match_players_captain": "A team cannot have more than one captain.",
    "uq_match_players_keeper": "A team cannot have more than one wicket keeper.",
}


def constraint_name(exc: IntegrityError) -> str | None:
    """Pull the violated constraint's name out of a psycopg/SQLAlchemy error."""
    diagnostics = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diagnostics, "constraint_name", None)


def _match_loader_options():
    """Eagerly load team relationships to avoid N+1 queries when building response."""
    return (
        selectinload(Match.team1),
        selectinload(Match.team2),
        selectinload(Match.toss_winner),
        selectinload(Match.winner_team),
    )


def get_match_or_404(db: Session, match_id: int) -> Match:
    """Fetch match by ID or raise 404."""
    stmt = (
        select(Match)
        .where(Match.id == match_id)
        .options(*_match_loader_options())
    )
    match = db.scalar(stmt)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No match with id {match_id}",
        )
    return match


def create_match(db: Session, payload: MatchCreate) -> Match:
    """Create a scheduled match after validating that both teams exist."""
    teams = list(
        db.scalars(
            select(Team).where(Team.id.in_([payload.team1_id, payload.team2_id]))
        )
    )
    found_ids = {t.id for t in teams}
    for tid in (payload.team1_id, payload.team2_id):
        if tid not in found_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team with id {tid} not found",
            )

    match = Match(**payload.model_dump())
    db.add(match)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = constraint_name(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CONSTRAINT_ERROR_MESSAGES.get(name, "Match violates a database constraint."),
        ) from exc

    # Reload with team relationships
    return get_match_or_404(db, match.id)


def list_matches(
    db: Session,
    team_id: int | None = None,
    match_status: MatchStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Match]:
    """List matches, newest date first, with pagination and optional filters."""
    stmt = (
        select(Match)
        .options(*_match_loader_options())
        .order_by(Match.match_date.desc(), Match.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if match_status:
        stmt = stmt.where(Match.status == match_status)
    if team_id:
        stmt = stmt.where((Match.team1_id == team_id) | (Match.team2_id == team_id))

    return list(db.scalars(stmt))


def update_match(db: Session, match_id: int, payload: MatchUpdate) -> Match:
    """Update match details, toss, or result with cross-table checks."""
    match = get_match_or_404(db, match_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    # Cross-table validation: toss_winner must be one of the match's teams
    toss_winner_id = changes.get("toss_winner_id")
    if toss_winner_id is not None and toss_winner_id not in (match.team1_id, match.team2_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team {toss_winner_id} is not playing in match {match_id}",
        )

    # Cross-table validation: winner_team must be one of the match's teams
    winner_team_id = changes.get("winner_team_id")
    if winner_team_id is not None and winner_team_id not in (match.team1_id, match.team2_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team {winner_team_id} is not playing in match {match_id}",
        )

    for field, value in changes.items():
        setattr(match, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = constraint_name(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CONSTRAINT_ERROR_MESSAGES.get(name, "Update violates a database constraint."),
        ) from exc

    db.expire_all()
    return get_match_or_404(db, match.id)


def set_match_squad(
    db: Session, match_id: int, payload: MatchSquadCreate
) -> list[MatchPlayer]:
    """Name or replace the playing squad/XI for a team in a match.

    Cross-table invariants checked:
    1. team_id is one of the match's teams.
    2. Every player must belong to that team's active squad (left_at IS NULL).
    3. Match cannot be finished/abandoned.
    """
    match = get_match_or_404(db, match_id)
    if match.status in (MatchStatus.COMPLETED, MatchStatus.ABANDONED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot name or modify squad for a match that is {match.status.value}",
        )

    if payload.team_id not in (match.team1_id, match.team2_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team {payload.team_id} is not playing in match {match_id}",
        )

    # Verify all submitted players are active squad members for this team
    submitted_player_ids = [p.player_id for p in payload.players]
    active_stmt = select(TeamPlayer.player_id).where(
        TeamPlayer.team_id == payload.team_id,
        TeamPlayer.is_active.is_(True),
        TeamPlayer.player_id.in_(submitted_player_ids),
    )
    active_player_ids = set(db.scalars(active_stmt))

    unaffiliated = set(submitted_player_ids) - active_player_ids
    if unaffiliated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Player IDs {sorted(unaffiliated)} are not active members of team {payload.team_id}'s squad",
        )

    # Check if deliveries have already been bowled in this match
    # (If an innings is already underway, changing players would break delivery FKs)
    if match.innings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify match squad after innings have started",
        )

    # Remove existing squad entries for this team in this match and replace
    db.execute(
        delete(MatchPlayer).where(
            MatchPlayer.match_id == match_id,
            MatchPlayer.team_id == payload.team_id,
        )
    )

    new_entries = [
        MatchPlayer(
            match_id=match_id,
            team_id=payload.team_id,
            player_id=p.player_id,
            batting_position=p.batting_position,
            is_captain=p.is_captain,
            is_wicket_keeper=p.is_wicket_keeper,
            is_substitute=p.is_substitute,
        )
        for p in payload.players
    ]
    db.add_all(new_entries)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = constraint_name(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CONSTRAINT_ERROR_MESSAGES.get(name, "Squad violates a database constraint."),
        ) from exc

    return get_match_players(db, match_id=match_id, team_id=payload.team_id)


def get_match_players(
    db: Session, match_id: int, team_id: int | None = None
) -> list[MatchPlayer]:
    """Return players named for the match, ordered by role and batting position."""
    # Ensure match exists
    get_match_or_404(db, match_id)

    stmt = (
        select(MatchPlayer)
        .options(joinedload(MatchPlayer.player))
        .where(MatchPlayer.match_id == match_id)
        .order_by(
            MatchPlayer.team_id,
            MatchPlayer.is_substitute.asc(),
            MatchPlayer.batting_position.asc().nulls_last(),
        )
    )
    if team_id is not None:
        stmt = stmt.where(MatchPlayer.team_id == team_id)

    return list(db.scalars(stmt))
