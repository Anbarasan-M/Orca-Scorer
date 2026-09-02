from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.models.enums import InningsStatus
from app.db.types import enum_col

if TYPE_CHECKING:
    from app.db.models.delivery import Delivery
    from app.db.models.match import Match
    from app.db.models.team import Team


class Innings(Base, IdMixin, TimestampMixin):
    __tablename__ = "innings"

    match_id: Mapped[int] = mapped_column(
        sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    #: 1-2 for limited overs, up to 4 for a Test match.
    innings_number: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    batting_team_id: Mapped[int] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    bowling_team_id: Mapped[int] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    #: May be lower than the match total_overs after a rain reduction.
    max_overs: Mapped[int | None] = mapped_column(sa.SmallInteger)
    #: Runs needed to win. NULL when batting first.
    target_runs: Mapped[int | None] = mapped_column(sa.Integer)
    status: Mapped[InningsStatus] = mapped_column(
        enum_col(InningsStatus, "innings_status"),
        nullable=False,
        server_default=InningsStatus.NOT_STARTED.value,
    )

    match: Mapped["Match"] = relationship(back_populates="innings")
    batting_team: Mapped["Team"] = relationship(foreign_keys=[batting_team_id])
    bowling_team: Mapped["Team"] = relationship(foreign_keys=[bowling_team_id])
    deliveries: Mapped[list["Delivery"]] = relationship(
        back_populates="innings",
        cascade="all, delete-orphan",
        order_by="Delivery.ball_seq",
    )

    __table_args__ = (
        sa.UniqueConstraint("match_id", "innings_number"),
        sa.CheckConstraint("innings_number BETWEEN 1 AND 4", name="innings_number_range"),
        sa.CheckConstraint("batting_team_id <> bowling_team_id", name="distinct_teams"),
        sa.CheckConstraint("target_runs IS NULL OR target_runs > 0", name="target_positive"),
        sa.CheckConstraint(
            "max_overs IS NULL OR max_overs BETWEEN 1 AND 200", name="overs_range"
        ),
    )

    def __repr__(self) -> str:
        return f"<Innings match={self.match_id} no={self.innings_number}>"
