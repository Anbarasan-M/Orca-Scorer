from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.models.enums import BattingStyle, BowlingStyle, PlayerRole
from app.db.types import enum_col

if TYPE_CHECKING:
    from app.db.models.team_player import TeamPlayer


class Player(Base, IdMixin, TimestampMixin):
    """A person. Deliberately has no team_id - see `team_players`, because a
    player can move between teams over their career."""

    __tablename__ = "players"

    name: Mapped[str] = mapped_column(sa.String(100), nullable=False, index=True)
    photo_url: Mapped[str | None] = mapped_column(sa.Text)
    batting_style: Mapped[BattingStyle | None] = mapped_column(
        enum_col(BattingStyle, "batting_style")
    )
    bowling_style: Mapped[BowlingStyle | None] = mapped_column(
        enum_col(BowlingStyle, "bowling_style")
    )
    player_role: Mapped[PlayerRole] = mapped_column(
        enum_col(PlayerRole, "player_role"),
        nullable=False,
        server_default=PlayerRole.BATTER.value,
    )

    team_players: Mapped[list["TeamPlayer"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    def __repr__(self) -> str:
        return f"<Player {self.name}>"
