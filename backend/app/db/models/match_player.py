from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin

if TYPE_CHECKING:
    from app.db.models.match import Match
    from app.db.models.player import Player
    from app.db.models.team import Team


class MatchPlayer(Base, IdMixin):
    """The XI (plus subs) for one match - a snapshot taken at toss time.

    A squad may have 25 registered players; this records who actually turned
    up for *this* match, and in what role.
    """

    __tablename__ = "match_players"

    match_id: Mapped[int] = mapped_column(
        sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[int] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(
        sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batting_position: Mapped[int | None] = mapped_column(sa.SmallInteger)
    is_captain: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    is_wicket_keeper: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    is_substitute: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )

    match: Mapped["Match"] = relationship(back_populates="match_players")
    team: Mapped["Team"] = relationship()
    player: Mapped["Player"] = relationship()

    __table_args__ = (
        sa.UniqueConstraint("match_id", "player_id"),
        sa.CheckConstraint(
            "batting_position IS NULL OR batting_position BETWEEN 1 AND 15",
            name="batting_position_range",
        ),
        # No two players batting at the same position for the same side.
        sa.Index(
            "uq_match_players_batting_position",
            "match_id",
            "team_id",
            "batting_position",
            unique=True,
            postgresql_where=sa.text("batting_position IS NOT NULL"),
        ),
        # One captain and one keeper per side per match.
        sa.Index(
            "uq_match_players_captain",
            "match_id",
            "team_id",
            unique=True,
            postgresql_where=sa.text("is_captain"),
        ),
        sa.Index(
            "uq_match_players_keeper",
            "match_id",
            "team_id",
            unique=True,
            postgresql_where=sa.text("is_wicket_keeper"),
        ),
    )
