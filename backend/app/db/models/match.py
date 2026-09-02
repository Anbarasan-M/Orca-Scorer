from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.models.enums import MatchFormat, MatchStatus, ResultType, TossDecision
from app.db.types import enum_col

if TYPE_CHECKING:
    from app.db.models.innings import Innings
    from app.db.models.match_event import MatchEvent
    from app.db.models.match_player import MatchPlayer
    from app.db.models.team import Team


class Match(Base, IdMixin, TimestampMixin):
    __tablename__ = "matches"

    team1_id: Mapped[int] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    team2_id: Mapped[int] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    match_date: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, index=True
    )
    venue: Mapped[str | None] = mapped_column(sa.String(150))
    format: Mapped[MatchFormat] = mapped_column(
        enum_col(MatchFormat, "match_format"), nullable=False
    )
    #: NULL for TEST matches, which are not overs-limited.
    total_overs: Mapped[int | None] = mapped_column(sa.SmallInteger)

    toss_winner_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="RESTRICT")
    )
    toss_decision: Mapped[TossDecision | None] = mapped_column(
        enum_col(TossDecision, "toss_decision")
    )

    winner_team_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("teams.id", ondelete="RESTRICT")
    )
    #: Distinguishes "not finished yet" from "finished, but nobody won".
    result_type: Mapped[ResultType | None] = mapped_column(
        enum_col(ResultType, "result_type")
    )
    status: Mapped[MatchStatus] = mapped_column(
        enum_col(MatchStatus, "match_status"),
        nullable=False,
        server_default=MatchStatus.SCHEDULED.value,
        index=True,
    )

    team1: Mapped["Team"] = relationship(foreign_keys=[team1_id])
    team2: Mapped["Team"] = relationship(foreign_keys=[team2_id])
    toss_winner: Mapped["Team | None"] = relationship(foreign_keys=[toss_winner_id])
    winner_team: Mapped["Team | None"] = relationship(foreign_keys=[winner_team_id])

    innings: Mapped[list["Innings"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="Innings.innings_number",
    )
    match_players: Mapped[list["MatchPlayer"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )
    events: Mapped[list["MatchEvent"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.CheckConstraint("team1_id <> team2_id", name="distinct_teams"),
        sa.CheckConstraint(
            "toss_winner_id IS NULL OR toss_winner_id IN (team1_id, team2_id)",
            name="toss_winner_is_playing",
        ),
        sa.CheckConstraint(
            "winner_team_id IS NULL OR winner_team_id IN (team1_id, team2_id)",
            name="winner_is_playing",
        ),
        # The toss is one fact: you know both halves of it, or neither.
        sa.CheckConstraint(
            "(toss_winner_id IS NULL) = (toss_decision IS NULL)",
            name="toss_complete",
        ),
        # Exactly one team wins iff the result is a WIN.
        sa.CheckConstraint(
            "(COALESCE(result_type, '') = 'WIN') = (winner_team_id IS NOT NULL)",
            name="winner_matches_result",
        ),
        sa.CheckConstraint(
            "total_overs IS NULL OR total_overs BETWEEN 1 AND 200",
            name="overs_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<Match {self.id} {self.format} {self.status}>"
