"""CRUD endpoints for teams, including squad membership."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Player, Team, TeamPlayer
from app.db.session import get_db
from app.schemas.team import SquadAdd, SquadMember, TeamCreate, TeamRead, TeamUpdate

router = APIRouter(prefix="/teams", tags=["teams"])

# The database is the thing that actually guarantees uniqueness, so we let it
# refuse the write and translate its complaint into a useful HTTP error.
CONFLICT_MESSAGES = {
    "uq_teams_name": "A team with that name already exists.",
    "uq_teams_short_name": "A team with that short name already exists.",
}


def constraint_name(exc: IntegrityError) -> str | None:
    """Pull the violated constraint's name out of a psycopg error."""
    diagnostics = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diagnostics, "constraint_name", None)


def get_team_or_404(team_id: int, db: Session) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No team with id {team_id}",
        )
    return team


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreate, db: Session = Depends(get_db)) -> Team:
    """Create a team.

    FastAPI has already validated the body against TeamCreate by the time this
    function runs, so `payload` is guaranteed to be well-formed.
    """
    team = Team(**payload.model_dump())
    db.add(team)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = constraint_name(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CONFLICT_MESSAGES.get(name, "Team violates a database constraint."),
        ) from exc
    # Loads the columns PostgreSQL filled in for us: id, created_at, updated_at.
    db.refresh(team)
    return team


@router.get("", response_model=list[TeamRead])
def list_teams(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, description="Case-insensitive name match"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Team]:
    """List teams, newest first. Always paginated - never return the whole table."""
    stmt = select(Team).order_by(Team.id.desc()).limit(limit).offset(offset)
    if search:
        stmt = stmt.where(Team.name.ilike(f"%{search}%"))
    return list(db.scalars(stmt))


@router.get("/{team_id}", response_model=TeamRead)
def get_team(team_id: int, db: Session = Depends(get_db)) -> Team:
    return get_team_or_404(team_id, db)


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: int, payload: TeamUpdate, db: Session = Depends(get_db)
) -> Team:
    """Partial update. Fields the client omitted are left alone."""
    team = get_team_or_404(team_id, db)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    for field, value in changes.items():
        setattr(team, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = constraint_name(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CONFLICT_MESSAGES.get(name, "Team violates a database constraint."),
        ) from exc
    db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a team.

    Squad membership goes with it (ON DELETE CASCADE), but a team that has
    played a match cannot be deleted - those foreign keys are RESTRICT, because
    deleting a team should never silently erase match history.
    """
    team = get_team_or_404(team_id, db)
    try:
        db.delete(team)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This team is referenced by a match and cannot be deleted.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{team_id}/squad", response_model=list[SquadMember])
def team_squad(team_id: int, db: Session = Depends(get_db)):
    """The team's current players - a first taste of joining tables.

    `TeamPlayer.is_active` is the generated column from the schema, so this
    reads "players whose stint at this team has no end date".
    """
    get_team_or_404(team_id, db)
    return db.execute(
        select(Player.id, Player.name, Player.player_role, TeamPlayer.joined_at)
        .join(TeamPlayer, TeamPlayer.player_id == Player.id)
        .where(TeamPlayer.team_id == team_id, TeamPlayer.is_active)
        .order_by(func.lower(Player.name))
    ).all()


@router.post(
    "/{team_id}/squad",
    response_model=SquadMember,
    status_code=status.HTTP_201_CREATED,
)
def add_to_squad(
    team_id: int, payload: SquadAdd, db: Session = Depends(get_db)
) -> SquadMember:
    """Add a player to a team's squad, opening a new stint.

    No "is this player already in the squad?" SELECT first. Between that check
    and the INSERT another request could slip in and both would succeed. The
    partial unique index `uq_team_players_active` is the real guarantee, so we
    attempt the insert and translate its complaint instead.
    """
    get_team_or_404(team_id, db)
    player = db.get(Player, payload.player_id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No player with id {payload.player_id}",
        )

    stint = TeamPlayer(
        team_id=team_id,
        player_id=player.id,
        joined_at=payload.joined_at or date.today(),
    )
    db.add(stint)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if constraint_name(exc) == "uq_team_players_active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{player.name} is already in this squad.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Squad membership violates a database constraint.",
        ) from exc

    db.refresh(stint)
    return SquadMember(
        id=player.id,
        name=player.name,
        player_role=player.player_role,
        joined_at=stint.joined_at,
    )


@router.delete(
    "/{team_id}/squad/{player_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_from_squad(
    team_id: int, player_id: int, db: Session = Depends(get_db)
) -> Response:
    """End a player's stint at a team.

    This deliberately does NOT delete the row. Setting `left_at` closes the
    stint, so "who played for us in 2026?" stays answerable. PostgreSQL then
    flips the generated `is_active` column to false on its own, and
    GET /teams/{id}/squad stops listing them with no change to that endpoint.
    """
    get_team_or_404(team_id, db)

    stint = db.scalars(
        select(TeamPlayer).where(
            TeamPlayer.team_id == team_id,
            TeamPlayer.player_id == player_id,
            TeamPlayer.left_at.is_(None),
        )
    ).first()
    if stint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player {player_id} is not currently in this squad",
        )

    today = date.today()
    # The date_order CHECK forbids left_at < joined_at, which would otherwise
    # fire when adding and removing a player on the same day it was backdated.
    stint.left_at = max(today, stint.joined_at)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
