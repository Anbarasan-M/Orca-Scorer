from datetime import date
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin

if TYPE_CHECKING:
    from app.db.models.player import Player
    from app.db.models.team import Team


class TeamPlayer(Base, IdMixin):
    """A player's stint at a team. Open-ended while `left_at` is NULL."""

    __tablename__ = "team_players"

    team_id: Mapped[int] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(
        sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    joined_at: Mapped[date] = mapped_column(
        sa.Date, nullable=False, server_default=sa.func.current_date()
    )
    left_at: Mapped[date | None] = mapped_column(sa.Date)

    # Derived, not stored by hand: `is_active` can never drift from `left_at`.
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, sa.Computed("left_at IS NULL", persisted=True)
    )

    team: Mapped["Team"] = relationship(back_populates="team_players")
    player: Mapped["Player"] = relationship(back_populates="team_players")

    __table_args__ = (
        sa.CheckConstraint("left_at IS NULL OR left_at >= joined_at", name="date_order"),
        # A player may rejoin a team later, but can only have one open stint.
        sa.Index(
            "uq_team_players_active",
            "team_id",
            "player_id",
            unique=True,
            postgresql_where=sa.text("left_at IS NULL"),
        ),
    )
