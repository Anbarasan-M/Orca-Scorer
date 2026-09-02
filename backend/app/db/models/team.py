from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.team_player import TeamPlayer


class Team(Base, IdMixin, TimestampMixin):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(sa.String(100), nullable=False, unique=True)
    short_name: Mapped[str] = mapped_column(sa.String(5), nullable=False, unique=True)
    logo_url: Mapped[str | None] = mapped_column(sa.Text)

    team_players: Mapped[list["TeamPlayer"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint("short_name = upper(short_name)", name="short_name_upper"),
        sa.CheckConstraint("length(short_name) BETWEEN 2 AND 5", name="short_name_len"),
    )

    def __repr__(self) -> str:
        return f"<Team {self.short_name}>"
