"""CRUD endpoints for players.

Mirrors teams.py. Two deliberate differences:

- There is no unique constraint on a player's name (two people really can both
  be called Anbu), so POST and PATCH have no 409 case and there is no
  CONFLICT_MESSAGES table.
- DELETE still needs IntegrityError handling, because deliveries, wickets and
  match_players reference players with ON DELETE RESTRICT. Someone who has
  faced a ball cannot be deleted without erasing match history.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Player
from app.db.models.enums import PlayerRole
from app.db.session import get_db
from app.schemas.player import PlayerCreate, PlayerRead, PlayerUpdate
from app.schemas.scorecard import PlayerStatistics
from app.services import scorecard as scorecard_service

router = APIRouter(prefix="/players", tags=["players"])


def get_player_or_404(player_id: int, db: Session) -> Player:
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No player with id {player_id}",
        )
    return player


@router.post("", response_model=PlayerRead, status_code=status.HTTP_201_CREATED)
def create_player(payload: PlayerCreate, db: Session = Depends(get_db)) -> Player:
    """Create a player.

    FastAPI has already validated the body against PlayerCreate, so `payload`
    is well-formed by the time this runs - including the enums.
    """
    player = Player(**payload.model_dump())
    db.add(player)
    db.commit()
    # Loads what PostgreSQL filled in: id, created_at, updated_at.
    db.refresh(player)
    return player


@router.get("", response_model=list[PlayerRead])
def list_players(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, description="Case-insensitive name match"),
    role: PlayerRole | None = Query(default=None, description="Filter by player role"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Player]:
    """List players, newest first. Always paginated - never return the whole table."""
    stmt = select(Player).order_by(Player.id.desc()).limit(limit).offset(offset)
    if search:
        stmt = stmt.where(Player.name.ilike(f"%{search}%"))
    if role:
        stmt = stmt.where(Player.player_role == role)
    return list(db.scalars(stmt))


@router.get("/{player_id}", response_model=PlayerRead)
def get_player(player_id: int, db: Session = Depends(get_db)) -> Player:
    return get_player_or_404(player_id, db)


@router.get("/{player_id}/statistics", response_model=PlayerStatistics)
def get_player_statistics(
    player_id: int, db: Session = Depends(get_db)
) -> PlayerStatistics:
    """Get aggregated career statistics for a player."""
    return scorecard_service.get_player_statistics(db, player_id)


@router.patch("/{player_id}", response_model=PlayerRead)
def update_player(
    player_id: int, payload: PlayerUpdate, db: Session = Depends(get_db)
) -> Player:
    """Partial update. Fields the client omitted are left alone."""
    player = get_player_or_404(player_id, db)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    for field, value in changes.items():
        setattr(player, field, value)

    db.commit()
    db.refresh(player)
    return player


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player(player_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a player.

    Squad rows in team_players go too (ON DELETE CASCADE), but a player who
    appears in a delivery, a wicket or a match XI cannot be deleted - those
    foreign keys are RESTRICT. Retiring a player should mean closing their
    squad stint, not erasing the balls they faced.
    """
    player = get_player_or_404(player_id, db)
    try:
        db.delete(player)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This player appears in a match and cannot be deleted. "
                "Remove them from the squad instead."
            ),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
