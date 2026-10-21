"""Endpoints for matches and match squads/playing XIs."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.models import Match, MatchPlayer
from app.db.models.enums import MatchStatus
from app.db.session import get_db
from app.schemas.match import (
    MatchCreate,
    MatchPlayerRead,
    MatchRead,
    MatchSquadCreate,
    MatchUpdate,
)
from app.schemas.scorecard import MatchScorecard
from app.services import match as match_service
from app.services import scorecard as scorecard_service

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchRead, status_code=status.HTTP_201_CREATED)
def create_match(
    payload: MatchCreate, db: Session = Depends(get_db)
) -> Match:
    """Schedule a match between two teams."""
    return match_service.create_match(db, payload)


@router.get("", response_model=list[MatchRead])
def list_matches(
    db: Session = Depends(get_db),
    team_id: int | None = Query(default=None, description="Filter by participating team"),
    match_status: MatchStatus | None = Query(
        default=None, alias="status", description="Filter by match status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Match]:
    """List matches, newest first. Always paginated."""
    return match_service.list_matches(
        db, team_id=team_id, match_status=match_status, limit=limit, offset=offset
    )


@router.get("/{match_id}", response_model=MatchRead)
def get_match(match_id: int, db: Session = Depends(get_db)) -> Match:
    """Fetch a single match with team information."""
    return match_service.get_match_or_404(db, match_id)


@router.patch("/{match_id}", response_model=MatchRead)
def update_match(
    match_id: int, payload: MatchUpdate, db: Session = Depends(get_db)
) -> Match:
    """Update match details, record toss result, or set match status."""
    return match_service.update_match(db, match_id, payload)


@router.post(
    "/{match_id}/players",
    response_model=list[MatchPlayerRead],
    status_code=status.HTTP_200_OK,
)
def set_match_squad(
    match_id: int, payload: MatchSquadCreate, db: Session = Depends(get_db)
) -> list[MatchPlayer]:
    """Name or update a team's playing XI and substitutes for the match.

    Cross-table validations applied:
    - Team must be participating in this match.
    - Every submitted player must be an active member of that team's squad.
    """
    return match_service.set_match_squad(db, match_id, payload)


@router.get("/{match_id}/players", response_model=list[MatchPlayerRead])
def get_match_players(
    match_id: int,
    team_id: int | None = Query(default=None, description="Filter by team"),
    db: Session = Depends(get_db),
) -> list[MatchPlayer]:
    """Get players named for the match, sorted by batting position."""
    return match_service.get_match_players(db, match_id, team_id=team_id)


@router.get("/{match_id}/scorecard", response_model=MatchScorecard)
def get_match_scorecard(
    match_id: int, db: Session = Depends(get_db)
) -> MatchScorecard:
    """Get complete scorecard for all innings in a match."""
    return scorecard_service.get_match_scorecard(db, match_id)
